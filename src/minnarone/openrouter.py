"""Provider LLM reale via OpenRouter (API Chat Completions OpenAI-compatibile).

Endpoint, header e shape del body sono quelli documentati da OpenRouter:
`POST https://openrouter.ai/api/v1/chat/completions`, auth
`Authorization: Bearer <OPENROUTER_API_KEY>`, body `{"model", "messages": [...]}`.
La risposta segue lo schema OpenAI: il testo è in
`choices[0].message.content`; i metadati di caching in
`usage.prompt_tokens_details.cached_tokens`.

Caching: per Grok e DeepSeek il prompt caching è AUTOMATICO (implicito) lato
OpenRouter — non serve `cache_control`. L'unico requisito è che il prefisso
stabile sia in testa e byte-identico tra le chiamate: lo garantisce il
PromptBuilder, e questo provider passa il prompt VERBATIM senza riscriverlo,
così il prefisso resta invariato.

Il trasporto HTTP è iniettabile (`transport`): in produzione usa stdlib
`urllib.request` eseguito fuori dall'event loop con `asyncio.to_thread`, così
NON aggiungiamo dipendenze runtime. Nei test si inietta un fake (no rete).
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .llm import LLMError, LLMProvider, LLMResult, LLMTimeout

if TYPE_CHECKING:
    from .config import Config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default timeout (secondi) per la chiamata HTTP. Sovrascrivibile da llm_params.
_DEFAULT_TIMEOUT = 30.0

# Slug di modello di default per provider logico. Sono valori di CONFIG con
# esempi documentati come default: la versione esatta ("Grok 4.3" /
# "DeepSeek V4 Flash") può cambiare lato OpenRouter, quindi è sovrascrivibile
# via `llm_params.model` senza toccare il codice.
_DEFAULT_MODELS: dict[str, str] = {
    "grok": "x-ai/grok-4.3",
    "deepseek": "deepseek/deepseek-chat",
}


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Risposta HTTP grezza restituita dal transport."""

    status: int
    body: bytes


class TransportError(Exception):
    """Fallimento di rete/HTTP a livello di trasporto (tradotto in LLMError)."""


class TransportTimeout(TransportError):
    """Timeout a livello di trasporto (tradotto in LLMTimeout)."""


# Firma del transport: chiamato con keyword-only e ritorna una HttpResponse.
Transport = Callable[..., HttpResponse]


def _validate_timeout(value: object) -> float:
    """Coerce e valida il timeout: deve essere numerico e strettamente > 0.

    Un timeout non numerico o non positivo è una mis-configurazione: solleva
    `LLMError` con un messaggio chiaro invece di crashare con ValueError nudo.
    """
    try:
        timeout = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise LLMError(
            f"timeout non valido: {value!r} (deve essere un numero > 0)"
        ) from None
    if not timeout > 0:
        raise LLMError(f"timeout non valido: {timeout!r} (deve essere > 0)")
    return timeout


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disabilita il follow dei redirect: per l'endpoint HTTPS fisso non vogliamo
    re-inviare l'header Authorization (Bearer token) a un host di redirect.
    urllib altrimenti seguirebbe i 3xx propagando il token cross-host."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


# Opener costruito senza follow-redirect attivo: un 3xx torna come HTTPError e
# viene mappato a status, non seguito.
_no_redirect_opener = urllib.request.build_opener(_NoRedirect())


def _open_request(
    opener: urllib.request.OpenerDirector,
    *,
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout: float,
) -> HttpResponse:
    """Esegue un POST con l'`opener` dato e mappa l'esito su `HttpResponse` /
    `TransportError` / `TransportTimeout`. Condiviso dal transport remoto
    (OpenRouter) e da quello locale (llama.cpp): cambia solo l'opener, non il
    contratto di errore. Un 3xx torna come status (non seguito) se l'opener ha
    il `_NoRedirect` installato."""
    req = urllib.request.Request(url, data=body, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return HttpResponse(status=resp.status, body=resp.read())
    except urllib.error.HTTPError as exc:  # risposta HTTP con status di errore (incl. 3xx)
        return HttpResponse(status=exc.code, body=exc.read())
    except TimeoutError as exc:  # urlopen timeout
        raise TransportTimeout(str(exc)) from exc
    except urllib.error.URLError as exc:
        # socket.timeout viene incapsulato in URLError.reason
        if isinstance(exc.reason, TimeoutError):
            raise TransportTimeout(str(exc)) from exc
        raise TransportError(str(exc)) from exc


def _urllib_transport(
    *, url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> HttpResponse:
    """Transport reale basato su stdlib `urllib.request` (nessuna dipendenza).

    Non segue redirect (vedi `_NoRedirect`): un 3xx diventa un HTTPError e viene
    restituito col suo status, così non re-inviamo il Bearer token cross-host.
    """
    return _open_request(
        _no_redirect_opener, url=url, headers=headers, body=body, timeout=timeout
    )


class OpenRouterProvider(LLMProvider):
    """`LLMProvider` reale che chiama OpenRouter Chat Completions.

    Endpoint (`_url`) ed etichetta nei messaggi d'errore (`_LABEL`) sono
    parametrizzati a livello di classe: i provider OpenAI-compatibili con host
    diverso (es. `LlamaCppProvider`) li specializzano riusando trasporto,
    parsing e mapping degli errori senza duplicare il flusso HTTP.
    """

    # Etichetta usata nei messaggi d'errore (specializzata dalle sottoclassi).
    _LABEL = "OpenRouter"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        transport: Transport | None = None,
        params: Mapping[str, object] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._url = OPENROUTER_URL
        self._transport = transport or _urllib_transport
        # Parametri di tuning passati nel body (temperature, max_tokens, …).
        self._params = dict(params or {})
        # Chiavi riservate: il prompt e il modello sono fissati dal provider e
        # non possono essere sovrascritti da llm_params arbitrari (romperebbero
        # il pass-through verbatim e il prefisso stabile cacheabile).
        for reserved in ("messages", "model"):
            self._params.pop(reserved, None)
        raw_timeout = self._params.pop("timeout", timeout)
        self._timeout = _validate_timeout(raw_timeout)

    def _resolve_api_key(self) -> str:
        key = self._api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise LLMError(
                "OPENROUTER_API_KEY mancante: imposta la variabile d'ambiente "
                "o passa api_key al provider"
            )
        return key

    def _build_request(self, prompt: str) -> tuple[dict[str, str], bytes]:
        api_key = self._resolve_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # Prompt passato VERBATIM come unico messaggio user: il prefisso stabile
        # in testa resta byte-identico tra chiamate (caching automatico).
        # Tuning params PRIMA, chiavi fisse (model/messages) DOPO: anche se una
        # chiave riservata sfuggisse, le fisse vincono sempre. Difesa in
        # profondità oltre al filtro nel costruttore.
        payload: dict[str, object] = {
            **self._params,
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = json.dumps(payload).encode("utf-8")
        return headers, body

    async def complete(self, prompt: str) -> LLMResult:
        headers, body = self._build_request(prompt)

        def _call() -> HttpResponse:
            return self._transport(
                url=self._url,
                headers=headers,
                body=body,
                timeout=self._timeout,
            )

        try:
            response = await asyncio.to_thread(_call)
        except TransportTimeout as exc:
            raise LLMTimeout(str(exc)) from exc
        except TransportError as exc:
            raise LLMError(str(exc)) from exc
        except OSError as exc:  # errore di rete a basso livello (socket, ecc.)
            # Messaggio FISSO: non interpoliamo il testo dell'eccezione, che
            # potrebbe echeggiare header (incl. il Bearer token). La causa
            # resta disponibile via chaining.
            raise LLMError(f"errore trasporto {self._LABEL}") from exc

        return self._parse_response(response)

    @classmethod
    def _parse_response(cls, response: HttpResponse) -> LLMResult:
        if response.status != 200:
            raise LLMError(
                f"{cls._LABEL} ha risposto con status {response.status}: "
                f"{response.body[:200]!r}"
            )
        try:
            data = json.loads(response.body.decode("utf-8"))
            message = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"risposta {cls._LABEL} malformata: {exc}") from exc

        if not isinstance(message, str):
            raise LLMError(f"contenuto del messaggio {cls._LABEL} non testuale")

        return LLMResult(message=message, meta=_extract_meta(data))


def _extract_meta(data: Mapping[str, object]) -> dict[str, object]:
    """Estrae metadati utili (modello, token, quota in cache) se presenti."""
    meta: dict[str, object] = {}
    model = data.get("model")
    if model is not None:
        meta["model"] = model
    usage = data.get("usage")
    if isinstance(usage, Mapping):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key in usage:
                meta[key] = usage[key]
        for key in ("cost", "total_cost"):
            if key in usage:
                meta["cost"] = usage[key]
                break
        details = usage.get("prompt_tokens_details")
        if isinstance(details, Mapping):
            if "cached_tokens" in details:
                meta["cached_tokens"] = details["cached_tokens"]
            if "cache_write_tokens" in details:
                meta["cache_write_tokens"] = details["cache_write_tokens"]
    for key in ("cost", "total_cost"):
        if "cost" not in meta and key in data:
            meta["cost"] = data[key]
            break
    return meta


def build_provider(
    config: "Config",
    *,
    transport: Transport | None = None,
) -> OpenRouterProvider:
    """Costruisce il provider reale dalla `Config`.

    `llm_provider` ("grok" | "deepseek") seleziona lo slug di modello di
    default; `llm_params.model` lo può sovrascrivere; gli altri `llm_params`
    (es. `temperature`, `max_tokens`) sono passati come tuning nel body.
    Cambiare provider in config cambia il modello senza modifiche al codice.

    `llm_provider: llamacpp` instrada invece verso il `LlamaCppProvider`
    locale (`llamacpp.base_url`, nessuna API key): il server serve un solo
    modello, quindi un eventuale `llm_params.model` viene ignorato.
    """
    params = dict(config.llm_params)
    model_override = params.pop("model", None)

    if config.llm_provider == "llamacpp":
        # Import locale per evitare il ciclo openrouter <-> llamacpp (il
        # modulo llamacpp riusa da qui trasporto e parsing condivisi).
        from .llamacpp import LlamaCppProvider

        return LlamaCppProvider(
            base_url=config.llamacpp.base_url,
            transport=transport,
            params=params,
        )

    if model_override is not None:
        model = str(model_override)
    else:
        model = _DEFAULT_MODELS.get(config.llm_provider)
        if model is None:
            raise LLMError(
                f"llm_provider sconosciuto: {config.llm_provider!r} "
                f"(ammessi: {sorted([*_DEFAULT_MODELS, 'llamacpp'])} "
                "o specifica llm_params.model)"
            )

    return OpenRouterProvider(model=model, transport=transport, params=params)
