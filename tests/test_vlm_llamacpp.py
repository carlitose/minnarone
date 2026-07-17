"""Test fake-transport del backend di captioning `LlamaCppCaptioner`.

Il trasporto HTTP e' iniettato (fake): i test NON toccano mai la rete. Il
contratto verso `llama-server` e' quello validato nello spike (ticket 04):
`POST {base_url}/v1/chat/completions` OpenAI-compatibile con un content-part
`image_url` (data-URI JPEG base64), risposta in `choices[0].message.content`.
Contratto errore best-effort: caption "" su fallimento trasporto/HTTP.

Coprono anche il routing di `build_captioner` sul backend selezionato in config,
la validazione di `vlm.backend` e l'health-check vision (`GET /props`).
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys

import pytest

from minnarone.app import _build_default_video_perceiver
from minnarone.config import Config, ConfigError, LlamaCppConfig, OsCaptureConfig
from minnarone.llamacpp import (
    LlamaCppServerNotReady,
    check_vision_ready,
    ensure_llamacpp_ready,
)
from minnarone.openrouter import HttpResponse, TransportError, TransportTimeout
from minnarone.output import OutputMode
from minnarone.store import PerceptionStore
from minnarone.video import VideoFrame
from minnarone.vlm import DEFAULT_QWEN_VL_PROMPT, QwenVlConfig
from minnarone.vlm_llamacpp import LlamaCppCaptioner

# --- fakes -------------------------------------------------------------------


class _FakeImage:
    """Immagine PIL-like minimale: convert/save senza dipendere da Pillow."""

    def __init__(self, size=(64, 64)):
        self.size = size
        self.saved_format = None

    def convert(self, _mode):
        return self

    def resize(self, size, *, resample):  # pragma: no cover - path no-resize
        return _FakeImage(size=size)

    def save(self, fp, *, format):
        self.saved_format = format
        fp.write(b"JPEGDATA")


class _FakeImageModule:
    class Image:
        pass


class RecordingTransport:
    """Cattura la richiesta e restituisce una risposta predefinita (o solleva)."""

    def __init__(self, response=None, *, raises=None):
        self._response = response
        self._raises = raises
        self.calls = []

    def __call__(self, *, url, headers, body, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "body": body, "timeout": timeout}
        )
        if self._raises is not None:
            raise self._raises
        return self._response


def _caption_response(text="A player fights a boss on stream."):
    body = {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "model": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
        "usage": {"prompt_tokens": 256, "completion_tokens": 12},
    }
    return HttpResponse(status=200, body=json.dumps(body).encode("utf-8"))


def _frame():
    return VideoFrame(pixels=_FakeImage(), source_label="screen", ts=3.0)


def _captioner(transport, *, config=None):
    return LlamaCppCaptioner(
        base_url="http://127.0.0.1:8080",
        config=config or QwenVlConfig(),
        transport=transport,
        image_module=_FakeImageModule(),
    )


# --- caption: percorso felice ------------------------------------------------


def test_caption_posts_image_url_content_part_and_returns_normalized_text():
    transport = RecordingTransport(_caption_response("  A player fights a boss.  "))
    captioner = _captioner(transport, config=QwenVlConfig(max_new_tokens=32))

    caption = captioner.caption(_frame())

    assert caption == "A player fights a boss."
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert call["headers"]["Content-Type"] == "application/json"
    assert "Authorization" not in call["headers"]
    sent = json.loads(call["body"].decode("utf-8"))
    assert sent["max_tokens"] == 32
    content = sent["messages"][0]["content"]
    text_part = next(p for p in content if p["type"] == "text")
    image_part = next(p for p in content if p["type"] == "image_url")
    assert text_part["text"] == DEFAULT_QWEN_VL_PROMPT
    expected_uri = "data:image/jpeg;base64," + base64.b64encode(b"JPEGDATA").decode(
        "ascii"
    )
    assert image_part["image_url"]["url"] == expected_uri


def test_caption_truncates_to_max_caption_chars():
    transport = RecordingTransport(_caption_response("abcdefghijklmnop"))
    captioner = _captioner(transport, config=QwenVlConfig(max_caption_chars=10))

    assert captioner.caption(_frame()) == "abcdefghij"


# --- caption: contratto errore best-effort ("") ------------------------------


def test_caption_returns_empty_on_malformed_response():
    transport = RecordingTransport(HttpResponse(status=200, body=b'{"choices": []}'))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_non_json_body():
    transport = RecordingTransport(HttpResponse(status=200, body=b"not json"))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_http_error_status():
    transport = RecordingTransport(HttpResponse(status=500, body=b"{}"))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_transport_error():
    transport = RecordingTransport(raises=TransportError("boom"))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_transport_timeout():
    transport = RecordingTransport(raises=TransportTimeout("slow"))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_os_error():
    transport = RecordingTransport(raises=OSError("connection refused"))
    assert _captioner(transport).caption(_frame()) == ""


def test_caption_returns_empty_on_http_exception():
    # IncompleteRead/BadStatusLine (server che chiude a meta' risposta) sono
    # http.client.HTTPException, NON OSError e non incapsulate da urllib: senza
    # il catch esplicito sfuggirebbero a caption() violando il best-effort.
    import http.client

    transport = RecordingTransport(raises=http.client.IncompleteRead(b"partial"))
    assert _captioner(transport).caption(_frame()) == ""


# --- import senza torch (il path llamacpp non deve tirare torch) -------------


def test_llamacpp_captioner_module_imports_without_torch():
    snippet = (
        "import sys\n"
        "sys.modules['torch'] = None\n"
        "from minnarone.vlm_llamacpp import LlamaCppCaptioner\n"
        "from minnarone.vlm import QwenVlConfig\n"
        "LlamaCppCaptioner(base_url='http://127.0.0.1:8080', config=QwenVlConfig())\n"
        "assert 'torch' not in {k for k, v in sys.modules.items() if v is not None}\n"
        "print('ok-no-torch')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ok-no-torch" in result.stdout


# --- config: vlm.backend -----------------------------------------------------


def test_vlm_backend_defaults_to_qwen():
    assert QwenVlConfig().backend == "qwen"


def test_vlm_backend_accepts_llamacpp():
    assert QwenVlConfig(backend="llamacpp").backend == "llamacpp"


def test_vlm_backend_rejects_unknown_value():
    with pytest.raises(Exception) as exc_info:
        QwenVlConfig(backend="ollama")
    assert "backend" in str(exc_info.value)


def _base_config_dict(**vlm):
    data = {
        "mode": "public",
        "soul_path": "soul.md",
        "facts_dir": "facts",
        "adapter": "os_capture",
        "llm_provider": "grok",
        "os_capture": {"audio": False, "video": True},
    }
    if vlm:
        data["vlm"] = vlm
    return data


def test_config_from_dict_parses_vlm_backend():
    config = Config.from_dict(_base_config_dict(backend="llamacpp"))
    assert config.vlm.backend == "llamacpp"


def test_config_from_dict_defaults_backend_qwen():
    config = Config.from_dict(_base_config_dict())
    assert config.vlm.backend == "qwen"


def test_config_from_dict_rejects_invalid_backend():
    with pytest.raises(ConfigError) as exc_info:
        Config.from_dict(_base_config_dict(backend="nope"))
    assert "backend" in str(exc_info.value)


# --- build_captioner: routing sul backend ------------------------------------


class _RecordingCaptioner:
    def __init__(self, label):
        self.label = label

    def caption(self, _frame):
        return f"caption-{self.label}"


def _routing_config(backend, base_url="http://127.0.0.1:8080"):
    return Config(
        mode=OutputMode.PUBLIC,
        soul_path="soul.md",
        facts_dir="facts",
        adapter="os_capture",
        llm_provider="grok",
        llm_params={},
        os_capture=OsCaptureConfig(),
        vlm=QwenVlConfig(backend=backend),
        llamacpp=LlamaCppConfig(base_url=base_url),
    )


def test_build_captioner_routes_to_llamacpp_backend(tmp_path):
    store = PerceptionStore(tmp_path / "p.jsonl")
    chosen = []

    perceiver = _build_default_video_perceiver(
        _routing_config("llamacpp"),
        store,
        qwen_captioner_factory=lambda _c: chosen.append("qwen")
        or _RecordingCaptioner("qwen"),
        llamacpp_captioner_factory=lambda _c: chosen.append("llamacpp")
        or _RecordingCaptioner("llamacpp"),
    )
    perceiver.perceive_frame(VideoFrame(pixels=b"frame-bytes", ts=1.0))

    assert chosen == ["llamacpp"]


def test_build_captioner_routes_to_qwen_backend_by_default(tmp_path):
    store = PerceptionStore(tmp_path / "p.jsonl")
    chosen = []

    perceiver = _build_default_video_perceiver(
        _routing_config("qwen"),
        store,
        qwen_captioner_factory=lambda _c: chosen.append("qwen")
        or _RecordingCaptioner("qwen"),
        llamacpp_captioner_factory=lambda _c: chosen.append("llamacpp")
        or _RecordingCaptioner("llamacpp"),
    )
    perceiver.perceive_frame(VideoFrame(pixels=b"frame-bytes", ts=1.0))

    assert chosen == ["qwen"]


def test_build_captioner_default_llamacpp_uses_llamacpp_base_url(tmp_path):
    store = PerceptionStore(tmp_path / "p.jsonl")
    captured = {}

    def factory(config):
        captured["base_url"] = config.llamacpp.base_url
        captured["backend"] = config.vlm.backend
        return _RecordingCaptioner("llamacpp")

    perceiver = _build_default_video_perceiver(
        _routing_config("llamacpp", base_url="http://127.0.0.1:9099"),
        store,
        llamacpp_captioner_factory=factory,
    )
    perceiver.perceive_frame(VideoFrame(pixels=b"frame-bytes", ts=1.0))

    assert captured == {"base_url": "http://127.0.0.1:9099", "backend": "llamacpp"}


# --- health-check vision (GET /props) ----------------------------------------


class RecordingVisionProbe:
    """Probe fake di GET /props: registra le chiamate, risponde o solleva."""

    def __init__(self, props=None, *, raises=None):
        self._props = props
        self._raises = raises
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append({"url": url, "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return self._props


def test_check_vision_ready_ok_when_vision_true():
    probe = RecordingVisionProbe({"modalities": {"vision": True, "audio": False}})
    check_vision_ready("http://127.0.0.1:8080", probe=probe)
    assert probe.calls == [{"url": "http://127.0.0.1:8080/props", "timeout": 5.0}]


def test_check_vision_ready_raises_when_vision_missing_is_actionable():
    probe = RecordingVisionProbe({"modalities": {"vision": False}})
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_vision_ready("http://127.0.0.1:8080", probe=probe)
    assert "--mmproj" in str(exc_info.value)


def test_check_vision_ready_raises_when_modalities_absent():
    probe = RecordingVisionProbe({"model_path": "x.gguf"})
    with pytest.raises(LlamaCppServerNotReady):
        check_vision_ready("http://127.0.0.1:8080", probe=probe)


def test_check_vision_ready_raises_when_server_unreachable():
    probe = RecordingVisionProbe(raises=OSError("connection refused"))
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_vision_ready("http://127.0.0.1:8080", probe=probe)
    assert "http://127.0.0.1:8080" in str(exc_info.value)


def _ensure_config(*, llm_provider, backend):
    return Config(
        mode=OutputMode.PUBLIC,
        soul_path="soul.md",
        facts_dir="facts",
        adapter="os_capture",
        llm_provider=llm_provider,
        llm_params={},
        os_capture=OsCaptureConfig(),
        vlm=QwenVlConfig(backend=backend),
        llamacpp=LlamaCppConfig(base_url="http://127.0.0.1:8080"),
    )


def test_ensure_llamacpp_ready_runs_vision_check_for_llamacpp_backend_cloud_llm():
    # Backend VLM llamacpp con LLM cloud: la vision-check gira comunque (usa
    # llamacpp.base_url) e il health-check testo NON deve girare.
    vision_probe = RecordingVisionProbe({"modalities": {"vision": True}})

    def forbidden_health(url, timeout):
        raise AssertionError("health-check testo non atteso con LLM cloud")

    ensure_llamacpp_ready(
        _ensure_config(llm_provider="grok", backend="llamacpp"),
        probe=forbidden_health,
        vision_probe=vision_probe,
    )
    assert vision_probe.calls[0]["url"] == "http://127.0.0.1:8080/props"


def test_ensure_llamacpp_ready_skips_vision_check_for_qwen_backend():
    vision_probe = RecordingVisionProbe({"modalities": {"vision": True}})
    ensure_llamacpp_ready(
        _ensure_config(llm_provider="grok", backend="qwen"),
        vision_probe=vision_probe,
    )
    assert vision_probe.calls == []


# --- CLI: --check senza rete, vision-check solo sul percorso live -------------


def _vlm_llamacpp_yaml_config(tmp_path):
    import textwrap

    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    # LLM cloud + backend VLM llamacpp: isola la vision-check (niente health
    # testo). OPENROUTER_API_KEY assente e' irrilevante al --check.
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: grok
            agent_name: minnarone
            os_capture:
              audio: false
              video: true
            vlm:
              backend: llamacpp
            llamacpp:
              base_url: http://127.0.0.1:8080
            """
        ),
        encoding="utf-8",
    )
    return cfg


def test_cli_check_llamacpp_vlm_passes_without_network(tmp_path, capsys, monkeypatch):
    import minnarone.llamacpp as llamacpp_module
    from minnarone.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def forbid(url, timeout):
        raise AssertionError(f"--check non deve toccare la rete (probe su {url})")

    monkeypatch.setattr(llamacpp_module, "_urllib_vision_probe", forbid)

    code = main([str(_vlm_llamacpp_yaml_config(tmp_path)), "--check"])

    assert code == 0
    assert "ok" in capsys.readouterr().out


def test_cli_live_llamacpp_vlm_without_vision_returns_clear_error(
    tmp_path, capsys, monkeypatch
):
    import minnarone.cli as cli
    import minnarone.llamacpp as llamacpp_module
    from minnarone.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    class ForbiddenAgent:
        async def run(self):
            raise AssertionError("il loop live non deve partire senza visione")

    monkeypatch.setattr(cli, "build_agent", lambda _config: ForbiddenAgent())
    monkeypatch.setattr(
        llamacpp_module,
        "_urllib_vision_probe",
        RecordingVisionProbe({"modalities": {"vision": False}}),
    )

    code = main([str(_vlm_llamacpp_yaml_config(tmp_path))])

    assert code == 1
    assert "--mmproj" in capsys.readouterr().err
