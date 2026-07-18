"""Test del provider locale llama.cpp e del suo cablaggio (config/factory/CLI).

Il trasporto HTTP e la probe di readiness sono iniettati (fake) — i test non
toccano MAI la rete. Il contratto verso `llama-server` è quello verificato
empiricamente nei ticket 03/04: `POST {base_url}/v1/chat/completions`
OpenAI-compatibile, `GET /health` → 200 solo a modello caricato, 503 mentre
carica, errori come `{"error": {...}}`.

Le parti async sono eseguite con `asyncio.run` (niente plugin pytest-asyncio).
"""

import asyncio
import http.client
import json
import textwrap
from pathlib import Path

import pytest

import minnarone.cli as cli
import minnarone.llamacpp as llamacpp_module
from minnarone.cli import main
from minnarone.config import Config, ConfigError, LlamaCppConfig, OsCaptureConfig
from minnarone.llamacpp import (
    DEFAULT_BASE_URL,
    LLAMA_SERVER_COMMAND,
    LlamaCppProvider,
    LlamaCppServerNotReady,
    check_server_ready,
    ensure_llamacpp_ready,
)
from minnarone.llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from minnarone.openrouter import (
    HttpResponse,
    OpenRouterProvider,
    TransportTimeout,
    build_provider,
)
from minnarone.output import OutputMode


def _ok_response(message="ciao dal modello locale", *, cached=0, prompt_tokens=100):
    # Shape verificata sul llama-server reale (ticket 03): OpenAI-compatibile,
    # `usage.prompt_tokens_details.cached_tokens` popolato, nessun `cost`,
    # campo extra `timings` presente ma ignorabile.
    body = {
        "choices": [{"message": {"role": "assistant", "content": message}}],
        "model": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 7,
            "total_tokens": prompt_tokens + 7,
            "prompt_tokens_details": {"cached_tokens": cached},
        },
        "timings": {"predicted_per_second": 75.0},
    }
    return HttpResponse(status=200, body=json.dumps(body).encode("utf-8"))


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


# --- richiesta verso il server locale ---------------------------------------


def test_provider_is_llm_provider():
    provider = LlamaCppProvider(transport=RecordingTransport(_ok_response()))
    assert isinstance(provider, LLMProvider)


def test_complete_posts_to_local_endpoint_without_auth_and_without_model():
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(base_url="http://127.0.0.1:8080", transport=transport)

    asyncio.run(provider.complete("PROMPT TESTO"))

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    # Niente Bearer token: il server locale non richiede auth.
    assert "Authorization" not in call["headers"]
    assert call["headers"]["Content-Type"] == "application/json"
    sent = json.loads(call["body"].decode("utf-8"))
    # Il server ignora `model` (un solo modello caricato): non va inviato.
    assert "model" not in sent
    assert sent["messages"] == [{"role": "user", "content": "PROMPT TESTO"}]


def test_complete_works_without_openrouter_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(transport=transport)

    result = asyncio.run(provider.complete("p"))

    assert isinstance(result, LLMResult)
    assert result.message == "ciao dal modello locale"


def test_base_url_trailing_slash_is_normalized():
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(base_url="http://127.0.0.1:9001/", transport=transport)
    asyncio.run(provider.complete("p"))
    assert transport.calls[0]["url"] == "http://127.0.0.1:9001/v1/chat/completions"


def test_prompt_passed_through_verbatim_preserving_prefix():
    # Il prefisso stabile del PromptBuilder deve arrivare byte-identico nel
    # body: nessuna riscrittura da parte del provider.
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(transport=transport)
    prompt = "## IDENTITÀ\nSono minnarone\n\n## SITUAZIONE\nx"

    asyncio.run(provider.complete(prompt))

    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["messages"][0]["content"] == prompt
    assert sent["messages"][0]["content"].startswith("## IDENTITÀ\n")


# --- mapping llm_params ------------------------------------------------------


def test_thinking_param_is_dropped_other_params_pass():
    # `thinking` è un parametro dei provider cloud: per llama.cpp il reasoning
    # si spegne server-side (`--reasoning off`), quindi il provider lo droppa.
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(
        transport=transport,
        params={"thinking": "low", "temperature": 0.4, "max_tokens": 128},
    )

    asyncio.run(provider.complete("p"))

    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert "thinking" not in sent
    assert sent["temperature"] == 0.4
    assert sent["max_tokens"] == 128


def test_params_cannot_override_prompt_messages():
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(
        transport=transport,
        params={"messages": [{"role": "user", "content": "HIJACKED"}]},
    )
    asyncio.run(provider.complete("PROMPT VERO"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["messages"] == [{"role": "user", "content": "PROMPT VERO"}]


def test_model_param_is_not_sent_in_body():
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(transport=transport, params={"model": "qualsiasi-slug"})
    asyncio.run(provider.complete("p"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert "model" not in sent


def test_timeout_param_stays_client_side():
    transport = RecordingTransport(_ok_response())
    provider = LlamaCppProvider(transport=transport, params={"timeout": 12})
    asyncio.run(provider.complete("p"))
    call = transport.calls[0]
    assert call["timeout"] == 12.0
    assert "timeout" not in json.loads(call["body"].decode("utf-8"))


# --- parsing risposta e meta -------------------------------------------------


def test_success_parses_message_and_meta():
    transport = RecordingTransport(
        _ok_response("bella lì", cached=80, prompt_tokens=100)
    )
    provider = LlamaCppProvider(transport=transport)

    result = asyncio.run(provider.complete("p"))

    assert isinstance(result, LLMResult)
    assert result.message == "bella lì"
    # `model` viene dallo slug della risposta (il server conosce il modello).
    assert result.meta["model"] == "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
    assert result.meta["prompt_tokens"] == 100
    assert result.meta["cached_tokens"] == 80
    # llama-server non espone `cost`: la dashboard tollera l'assenza.
    assert "cost" not in result.meta


def test_503_while_loading_raises_llm_error():
    # Contratto verificato (ticket 03): 503 con body {"error": {...}} mentre
    # il modello sta caricando.
    body = json.dumps(
        {
            "error": {
                "code": 503,
                "message": "Loading model",
                "type": "unavailable_error",
            }
        }
    ).encode("utf-8")
    transport = RecordingTransport(HttpResponse(status=503, body=body))
    provider = LlamaCppProvider(transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_transport_timeout_raises_llm_timeout():
    transport = RecordingTransport(raises=TransportTimeout("slow"))
    provider = LlamaCppProvider(transport=transport)
    with pytest.raises(LLMTimeout):
        asyncio.run(provider.complete("p"))


def test_malformed_response_raises_llm_error():
    transport = RecordingTransport(HttpResponse(status=200, body=b'{"choices": []}'))
    provider = LlamaCppProvider(transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_error_message_names_llama_server_not_openrouter():
    transport = RecordingTransport(HttpResponse(status=500, body=b"{}"))
    provider = LlamaCppProvider(transport=transport)
    with pytest.raises(LLMError) as exc_info:
        asyncio.run(provider.complete("p"))
    assert "llama-server" in str(exc_info.value)
    assert "OpenRouter" not in str(exc_info.value)


# --- config: blocco llamacpp -------------------------------------------------


def test_llamacpp_config_default_base_url():
    assert LlamaCppConfig().base_url == "http://127.0.0.1:8080"
    assert DEFAULT_BASE_URL == "http://127.0.0.1:8080"


def test_llamacpp_config_rejects_non_url():
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url="non-un-url")
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url="ftp://127.0.0.1:8080")
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url="")
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url=8080)  # type: ignore[arg-type]


def test_llamacpp_config_rejects_invalid_port():
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url="http://127.0.0.1:porta")


def test_llamacpp_config_requires_explicit_port():
    # llama-server non gira mai sulle porte standard 80/443: un base_url senza
    # porta è quasi certamente un refuso e va segnalato al --check.
    with pytest.raises(ConfigError) as exc_info:
        LlamaCppConfig(base_url="http://127.0.0.1")
    assert "porta" in str(exc_info.value)


def test_llamacpp_config_normalizes_trailing_slash():
    cfg = LlamaCppConfig(base_url="http://127.0.0.1:8080/")
    assert cfg.base_url == "http://127.0.0.1:8080"


def test_llamacpp_config_rejects_base_url_with_path():
    # Convenzione tipica dei client OpenAI: base_url che finisce in `/v1`.
    # Qui è un errore: il provider aggiunge da sé `/v1/chat/...` e il probe
    # `/health`, quindi un path porterebbe a `/v1/v1/...` e `/v1/health` (404).
    with pytest.raises(ConfigError) as exc_info:
        LlamaCppConfig(base_url="http://127.0.0.1:8080/v1")
    assert "path" in str(exc_info.value)
    with pytest.raises(ConfigError):
        LlamaCppConfig(base_url="http://127.0.0.1:8080?x=1")


def test_llamacpp_config_rejects_port_zero():
    # urlsplit().port su ':0' restituisce 0 (falsy ma non None): va rifiutato
    # come porta mancante, non lasciato passare fino al fallimento a runtime.
    with pytest.raises(ConfigError) as exc_info:
        LlamaCppConfig(base_url="http://127.0.0.1:0")
    assert "porta" in str(exc_info.value)


def test_config_from_dict_parses_llamacpp_block():
    config = Config.from_dict(
        {
            "mode": "public",
            "soul_path": "soul.md",
            "facts_dir": "facts",
            "adapter": "os_capture",
            "llm_provider": "llamacpp",
            "os_capture": {"audio": False, "video": True},
            "llamacpp": {"base_url": "http://127.0.0.1:9090"},
        }
    )
    assert config.llamacpp.base_url == "http://127.0.0.1:9090"


def test_config_llamacpp_block_defaults_when_absent():
    config = Config.from_dict(
        {
            "mode": "public",
            "soul_path": "soul.md",
            "facts_dir": "facts",
            "adapter": "os_capture",
            "llm_provider": "llamacpp",
            "os_capture": {"audio": False, "video": True},
        }
    )
    assert config.llamacpp.base_url == DEFAULT_BASE_URL


def test_config_llamacpp_block_rejects_unknown_keys():
    with pytest.raises(ConfigError) as exc_info:
        Config.from_dict(
            {
                "mode": "public",
                "soul_path": "soul.md",
                "facts_dir": "facts",
                "adapter": "os_capture",
                "llm_provider": "llamacpp",
                "os_capture": {"audio": False, "video": True},
                "llamacpp": {"base_url": "http://127.0.0.1:8080", "model": "x"},
            }
        )
    assert "model" in str(exc_info.value)


def test_llamacpp_example_yaml_is_valid_config():
    # Stessa garanzia degli altri esempi: il file di examples/ deve caricare
    # come Config valida (esegui dal root del repo, come gli altri doc-test).
    cfg = Config.load(Path("examples/llamacpp-local.example.yaml"))
    assert cfg.llm_provider == "llamacpp"
    assert cfg.llamacpp.base_url == "http://127.0.0.1:8080"


# --- factory -----------------------------------------------------------------


def _config(provider="llamacpp", *, params=None, llamacpp=None):
    return Config(
        mode=OutputMode.PUBLIC,
        soul_path="soul.md",
        facts_dir="facts",
        adapter="os_capture",
        llm_provider=provider,
        llm_params=dict(params or {}),
        os_capture=OsCaptureConfig(),
        llamacpp=llamacpp or LlamaCppConfig(),
    )


def test_factory_routes_llamacpp_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    transport = RecordingTransport(_ok_response())
    provider = build_provider(
        _config(llamacpp=LlamaCppConfig(base_url="http://127.0.0.1:9001")),
        transport=transport,
    )

    assert isinstance(provider, LlamaCppProvider)
    result = asyncio.run(provider.complete("p"))
    assert result.message == "ciao dal modello locale"
    assert transport.calls[0]["url"] == "http://127.0.0.1:9001/v1/chat/completions"


def test_factory_llamacpp_drops_thinking_and_model_from_llm_params(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    transport = RecordingTransport(_ok_response())
    cfg = _config(params={"thinking": "low", "model": "x", "temperature": 0.2})
    provider = build_provider(cfg, transport=transport)

    asyncio.run(provider.complete("p"))

    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert "thinking" not in sent
    assert "model" not in sent
    assert sent["temperature"] == 0.2


def test_factory_cloud_providers_unchanged(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    provider = build_provider(
        _config("grok"), transport=RecordingTransport(_ok_response())
    )
    assert isinstance(provider, OpenRouterProvider)
    assert not isinstance(provider, LlamaCppProvider)


# --- health-check all'avvio live ----------------------------------------------


class RecordingProbe:
    """Probe fake di GET /health: registra le chiamate, risponde o solleva."""

    def __init__(self, status=200, *, raises=None):
        self._status = status
        self._raises = raises
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append({"url": url, "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return self._status


def test_check_server_ready_ok_on_200():
    probe = RecordingProbe(status=200)
    check_server_ready("http://127.0.0.1:8080", probe=probe)
    assert probe.calls == [{"url": "http://127.0.0.1:8080/health", "timeout": 5.0}]


def test_check_server_ready_503_loading_is_actionable():
    probe = RecordingProbe(status=503)
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_server_ready("http://127.0.0.1:8080", probe=probe)
    message = str(exc_info.value)
    assert "caricando" in message
    assert LLAMA_SERVER_COMMAND in message


def test_check_server_ready_connection_refused_is_actionable():
    probe = RecordingProbe(raises=OSError("connection refused"))
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_server_ready("http://127.0.0.1:8080", probe=probe)
    message = str(exc_info.value)
    assert "http://127.0.0.1:8080" in message
    assert LLAMA_SERVER_COMMAND in message


def test_check_server_ready_unexpected_status_is_actionable():
    probe = RecordingProbe(status=404)
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_server_ready("http://127.0.0.1:8080", probe=probe)
    assert "404" in str(exc_info.value)


def test_check_server_ready_http_exception_is_actionable():
    # Porta che punta a un servizio non-HTTP: urllib solleva
    # http.client.BadStatusLine (HTTPException, NON OSError e non incapsulata in
    # URLError). Deve diventare l'errore azionabile, non un traceback nudo.
    probe = RecordingProbe(raises=http.client.BadStatusLine("\x15\x03"))
    with pytest.raises(LlamaCppServerNotReady) as exc_info:
        check_server_ready("http://127.0.0.1:8080", probe=probe)
    assert LLAMA_SERVER_COMMAND in str(exc_info.value)


def test_ensure_llamacpp_ready_probes_configured_base_url():
    probe = RecordingProbe(status=200)
    ensure_llamacpp_ready(
        _config(llamacpp=LlamaCppConfig(base_url="http://127.0.0.1:9001")),
        probe=probe,
    )
    assert probe.calls[0]["url"] == "http://127.0.0.1:9001/health"


def test_ensure_llamacpp_ready_is_noop_for_cloud_providers():
    probe = RecordingProbe(status=200)
    ensure_llamacpp_ready(_config("grok"), probe=probe)
    assert probe.calls == []


# --- CLI: --check senza rete, health-check solo sul percorso live -------------


def _llamacpp_yaml_config(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: llamacpp
            agent_name: minnarone
            os_capture:
              audio: false
              video: true
            llamacpp:
              base_url: http://127.0.0.1:8080
            """
        ),
        encoding="utf-8",
    )
    return cfg


def _forbid_network_probe(url, timeout):
    raise AssertionError(f"--check non deve toccare la rete (probe su {url})")


def test_cli_check_llamacpp_passes_without_network(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(llamacpp_module, "_urllib_health_probe", _forbid_network_probe)

    code = main([str(_llamacpp_yaml_config(tmp_path)), "--check"])

    assert code == 0
    assert "llamacpp" in capsys.readouterr().out


def test_cli_live_llamacpp_server_down_returns_clear_error(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class ForbiddenAgent:
        async def run(self):
            raise AssertionError("il loop live non deve partire senza server")

    monkeypatch.setattr(cli, "build_agent", lambda _config: ForbiddenAgent())
    monkeypatch.setattr(
        llamacpp_module,
        "_urllib_health_probe",
        RecordingProbe(raises=OSError("connection refused")),
    )

    code = main([str(_llamacpp_yaml_config(tmp_path))])

    assert code == 1
    err = capsys.readouterr().err
    assert "llama-server" in err
    assert LLAMA_SERVER_COMMAND in err


def test_cli_live_llamacpp_server_ready_starts_agent(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ran = []

    class FakeAgent:
        async def run(self):
            ran.append(True)

    monkeypatch.setattr(cli, "build_agent", lambda _config: FakeAgent())
    monkeypatch.setattr(
        llamacpp_module, "_urllib_health_probe", RecordingProbe(status=200)
    )

    code = main([str(_llamacpp_yaml_config(tmp_path))])

    assert code == 0
    assert ran == [True]
