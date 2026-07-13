"""Test del provider reale OpenRouter e del factory che lo seleziona da config.

Il trasporto HTTP è iniettato (fake) — i test non toccano la rete. L'unico
percorso non esercitato è la chiamata live (no credenziali/rete AFK): il codice
è strutturato perché quel percorso passi per lo stesso `transport` iniettabile.

Le parti async sono eseguite con `asyncio.run` (niente plugin pytest-asyncio).
"""

import asyncio
import json

import pytest

from minnarone.config import Config, OsCaptureConfig
from minnarone.llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from minnarone.openrouter import (
    OPENROUTER_URL,
    HttpResponse,
    OpenRouterProvider,
    TransportError,
    TransportTimeout,
    build_provider,
)
from minnarone.output import OutputMode


def _ok_response(message="ciao dal modello", *, cached=0, prompt_tokens=100):
    body = {
        "choices": [{"message": {"role": "assistant", "content": message}}],
        "model": "x-ai/grok-test",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 5,
            "total_tokens": prompt_tokens + 5,
            "prompt_tokens_details": {"cached_tokens": cached, "cache_write_tokens": 0},
        },
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


# --- contratto e costruzione richiesta -------------------------------------


def test_provider_is_llm_provider():
    provider = OpenRouterProvider(
        model="x-ai/grok", api_key="k", transport=lambda **_kw: _ok_response()
    )
    assert isinstance(provider, LLMProvider)


def test_builds_correct_request_url_auth_and_body():
    transport = RecordingTransport(_ok_response())
    provider = OpenRouterProvider(
        model="x-ai/grok-4.3", api_key="secret-key", transport=transport
    )
    asyncio.run(provider.complete("PROMPT TESTO"))

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == OPENROUTER_URL
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["headers"]["Content-Type"] == "application/json"

    sent = json.loads(call["body"].decode("utf-8"))
    assert sent["model"] == "x-ai/grok-4.3"
    assert isinstance(sent["messages"], list) and len(sent["messages"]) == 1
    assert sent["messages"][0]["role"] == "user"
    assert sent["messages"][0]["content"] == "PROMPT TESTO"


def test_llm_params_passed_through_to_body():
    transport = RecordingTransport(_ok_response())
    provider = OpenRouterProvider(
        model="x-ai/grok",
        api_key="k",
        transport=transport,
        params={"temperature": 0.4, "max_tokens": 256},
    )
    asyncio.run(provider.complete("p"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["temperature"] == 0.4
    assert sent["max_tokens"] == 256


def test_llm_params_cannot_override_prompt_messages():
    # Una chiave 'messages' stray in llm_params NON deve sovrascrivere il prompt
    # reale: rompe il pass-through verbatim e il prefisso stabile cacheabile.
    transport = RecordingTransport(_ok_response())
    provider = OpenRouterProvider(
        model="x-ai/grok",
        api_key="k",
        transport=transport,
        params={"messages": [{"role": "user", "content": "HIJACKED"}]},
    )
    asyncio.run(provider.complete("PROMPT VERO"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["messages"] == [{"role": "user", "content": "PROMPT VERO"}]


def test_llm_params_cannot_override_model():
    # Una chiave 'model' stray in llm_params non deve sovrascrivere il modello
    # selezionato top-level.
    transport = RecordingTransport(_ok_response())
    provider = OpenRouterProvider(
        model="x-ai/grok-vero",
        api_key="k",
        transport=transport,
        params={"model": "x-ai/grok-hijack"},
    )
    asyncio.run(provider.complete("p"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["model"] == "x-ai/grok-vero"


# --- estrazione risultato e meta -------------------------------------------


def test_complete_extracts_message_and_meta():
    transport = RecordingTransport(_ok_response("bella clip", cached=80, prompt_tokens=100))
    provider = OpenRouterProvider(model="x-ai/grok", api_key="k", transport=transport)
    result = asyncio.run(provider.complete("p"))

    assert isinstance(result, LLMResult)
    assert result.message == "bella clip"
    assert result.meta["model"] == "x-ai/grok-test"
    assert result.meta["prompt_tokens"] == 100
    assert result.meta["cached_tokens"] == 80


def test_complete_extracts_cost_when_available():
    body = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
            "cost": 0.00042,
        },
    }
    transport = RecordingTransport(
        HttpResponse(status=200, body=json.dumps(body).encode("utf-8"))
    )
    provider = OpenRouterProvider(model="x-ai/grok", api_key="k", transport=transport)

    result = asyncio.run(provider.complete("p"))

    assert result.meta["cost"] == 0.00042


# --- gestione errori --------------------------------------------------------


def test_timeout_raises_llm_timeout():
    transport = RecordingTransport(raises=TransportTimeout("slow"))
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMTimeout):
        asyncio.run(provider.complete("p"))


def test_http_error_raises_llm_error():
    transport = RecordingTransport(raises=TransportError("boom"))
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_redirect_status_raises_llm_error_not_followed():
    # Un 3xx non deve "riuscire" silenziosamente né essere seguito: il transport
    # stdlib non segue redirect, quindi un 3xx arriva al parser e mappa a LLMError.
    # Così il Bearer token non viene re-inviato cross-host.
    redirect = HttpResponse(status=302, body=b'{"location":"http://evil.example"}')
    transport = RecordingTransport(redirect)
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_transport_exception_text_not_leaked_into_llm_error():
    # Un transport che echeggia header (incl. il token) nel testo dell'eccezione
    # non deve far finire quel testo nel messaggio dell'LLMError.
    secret = "sk-or-SUPERSECRET-TOKEN"
    transport = RecordingTransport(raises=OSError(f"Authorization: Bearer {secret}"))
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMError) as exc_info:
        asyncio.run(provider.complete("p"))
    assert secret not in str(exc_info.value)
    # La causa resta disponibile via chaining.
    assert isinstance(exc_info.value.__cause__, OSError)


def test_non_numeric_timeout_raises_llm_error():
    with pytest.raises(LLMError):
        OpenRouterProvider(
            model="m",
            api_key="k",
            transport=RecordingTransport(_ok_response()),
            timeout="non-un-numero",  # type: ignore[arg-type]
        )


def test_non_positive_timeout_raises_llm_error():
    with pytest.raises(LLMError):
        OpenRouterProvider(
            model="m",
            api_key="k",
            transport=RecordingTransport(_ok_response()),
            timeout=0,
        )
    with pytest.raises(LLMError):
        OpenRouterProvider(
            model="m",
            api_key="k",
            transport=RecordingTransport(_ok_response()),
            params={"timeout": -5},
        )


def test_non_200_status_raises_llm_error():
    bad = HttpResponse(status=401, body=b'{"error":"no auth"}')
    transport = RecordingTransport(bad)
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_malformed_body_raises_llm_error():
    bad = HttpResponse(status=200, body=b"not json at all")
    transport = RecordingTransport(bad)
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


def test_missing_api_key_raises_llm_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # api_key non passato e env assente => costruire la richiesta deve fallire pulito
    provider = OpenRouterProvider(model="m", transport=RecordingTransport(_ok_response()))
    with pytest.raises(LLMError):
        asyncio.run(provider.complete("p"))


# --- factory / selezione da config -----------------------------------------


def _config(provider, params=None):
    return Config(
        mode=OutputMode.PUBLIC,
        soul_path="soul.md",
        facts_dir="facts",
        adapter="os_capture",
        llm_provider=provider,
        llm_params=params or {},
        os_capture=OsCaptureConfig(),
    )


def test_factory_selects_grok_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    provider = build_provider(_config("grok"), transport=RecordingTransport(_ok_response()))
    assert isinstance(provider, OpenRouterProvider)
    assert "grok" in provider.model


def test_factory_selects_deepseek_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    provider = build_provider(_config("deepseek"), transport=RecordingTransport(_ok_response()))
    assert "deepseek" in provider.model


def test_factory_switch_changes_model_no_code_change(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    grok = build_provider(_config("grok"), transport=RecordingTransport(_ok_response()))
    deepseek = build_provider(_config("deepseek"), transport=RecordingTransport(_ok_response()))
    assert grok.model != deepseek.model


def test_factory_model_id_override_via_params(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    cfg = _config("grok", params={"model": "x-ai/grok-custom-slug"})
    provider = build_provider(cfg, transport=RecordingTransport(_ok_response()))
    assert provider.model == "x-ai/grok-custom-slug"


def test_factory_passes_tuning_params_excluding_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    transport = RecordingTransport(_ok_response())
    cfg = _config("grok", params={"temperature": 0.2, "model": "x-ai/grok-x"})
    provider = build_provider(cfg, transport=transport)
    asyncio.run(provider.complete("p"))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["temperature"] == 0.2
    # 'model' non deve finire dentro i tuning params del body (è il campo top-level)
    assert sent["model"] == "x-ai/grok-x"


def test_factory_unknown_provider_raises():
    with pytest.raises(LLMError):
        build_provider(_config("mistral-unknown"), transport=RecordingTransport(_ok_response()))


# --- invarianza prefisso stabile (caching) ---------------------------------


def test_prompt_passed_through_verbatim_preserving_prefix():
    # Il provider non deve riscrivere/riordinare il prompt: il prefisso stabile
    # in testa (costruito dal PromptBuilder) deve arrivare byte-identico nel body,
    # così il caching automatico di OpenRouter (Grok/DeepSeek) lo riusa.
    transport = RecordingTransport(_ok_response())
    provider = OpenRouterProvider(model="m", api_key="k", transport=transport)
    prompt = "## IDENTITÀ\nSono Minnarone.\n\n## FATTI\n...\n\n## SITUAZIONE\nx"
    asyncio.run(provider.complete(prompt))
    sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
    assert sent["messages"][0]["content"] == prompt
    assert sent["messages"][0]["content"].startswith("## IDENTITÀ\n")
