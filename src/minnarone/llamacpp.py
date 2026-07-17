"""Provider LLM locale via llama.cpp (`llama-server`, API OpenAI-compatibile).

Il server è avviato A MANO dall'utente (decisione del grilling 02: minnarone
non gestisce il processo); questo modulo parla solo HTTP con
`POST {base_url}/v1/chat/completions` e verifica la readiness con
`GET {base_url}/health` (200 solo a modello caricato — mai `/v1/models`,
che risponde anche mentre il modello sta ancora caricando).

Contratto verificato empiricamente (ticket 03/04):
- risposta OpenAI-compatibile: testo in `choices[0].message.content`,
  `usage.prompt_tokens_details.cached_tokens` popolato (stesso shape di
  OpenRouter), nessun campo `cost`;
- errori: status != 200 con body `{"error": {code, message, type}}`, 503
  mentre carica il modello, connection refused a server giù;
- il campo `model` nel body è ignorato (un solo modello caricato): non lo
  inviamo; lo slug reale arriva nella risposta e finisce in `meta["model"]`;
- `thinking` (llm_param dei provider cloud) va droppato: il reasoning si
  spegne server-side con `--reasoning off`, non è affare del provider.

Riusa da `openrouter.py` trasporto urllib, parsing ed estrazione meta
(nessuna dipendenza runtime nuova); qui cambiano solo endpoint, header
(niente Bearer token) e body (niente `model`).
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import TYPE_CHECKING, Callable

from .openrouter import (
    _DEFAULT_TIMEOUT,
    HttpResponse,
    OpenRouterProvider,
    Transport,
    _NoRedirect,
    _open_request,
)

if TYPE_CHECKING:
    from .config import Config

#: Base URL di default del `llama-server` locale (decisione del grilling 02).
DEFAULT_BASE_URL = "http://127.0.0.1:8080"

#: Opener dedicato al server LOCALE: proxy DISABILITATO (`ProxyHandler({})`) e
#: nessun redirect (`_NoRedirect`). Il default opener di urllib onora
#: `HTTP(S)_PROXY`: su una macchina aziendale con proxy configurato e senza
#: `127.0.0.1` in `NO_PROXY`, le richieste a localhost verrebbero instradate al
#: proxy (timeout/errore) — qui le teniamo dirette. Condiviso da probe di
#: readiness e transport di completamento, così i due path non divergono.
_local_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _NoRedirect()
)


def _local_transport(
    *, url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> HttpResponse:
    """Transport di default del provider locale: stessa logica del transport
    OpenRouter (`_open_request`) ma con l'opener no-proxy/no-redirect, così un
    proxy aziendale non intercetta le chiamate a localhost."""
    return _open_request(
        _local_opener, url=url, headers=headers, body=body, timeout=timeout
    )

#: Comando di riferimento per avviare il server (argomenti pinnati dal
#: wayfinder: offload totale, ctx 4096, reasoning spento, una richiesta alla
#: volta). Incluso nei messaggi d'errore azionabili del health-check.
LLAMA_SERVER_COMMAND = (
    "llama-server -m <modello.gguf> --port <porta> -ngl 99 -c 4096 "
    "--reasoning off --parallel 1"
)

#: Comando di riferimento per il server MULTIMODALE (captioner `vlm.backend:
#: llamacpp`): oltre al modello serve il proiettore `--mmproj`; `--parallel 2`
#: per servire testo e visione in concorrenza (decisione del grilling, ticket
#: 02/03). Incluso nei messaggi d'errore del health-check vision.
LLAMA_SERVER_MULTIMODAL_COMMAND = (
    "llama-server -m <modello.gguf> --mmproj <mmproj.gguf> --port <porta> "
    "-ngl 99 -c 4096 --reasoning off --parallel 2"
)

#: Timeout (secondi) della probe di readiness: locale, deve rispondere subito.
_HEALTH_TIMEOUT = 5.0

#: llm_params dei provider cloud senza significato per llama-server: droppati
#: (il server ignora i parametri sconosciuti, ma non inviarli è esplicito).
_DROPPED_PARAMS = ("thinking",)


class LlamaCppProvider(OpenRouterProvider):
    """`LLMProvider` che chiama il `llama-server` locale (senza auth).

    Specializza `OpenRouterProvider` su endpoint locale, header senza Bearer
    token e body senza `model`; eredita invariati trasporto, timeout
    client-side, parsing della risposta e mapping `LLMError`/`LLMTimeout`.
    """

    _LABEL = "llama-server"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        params: Mapping[str, object] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        cleaned = dict(params or {})
        for key in _DROPPED_PARAMS:
            cleaned.pop(key, None)
        # `model` qui è solo un'etichetta di osservabilità (log/dashboard):
        # lo slug reale del modello caricato arriva in `meta["model"]`.
        super().__init__(
            model="llamacpp",
            transport=transport or _local_transport,
            params=cleaned,
            timeout=timeout,
        )
        self.base_url = base_url.rstrip("/")
        self._url = f"{self.base_url}/v1/chat/completions"

    def _build_request(self, prompt: str) -> tuple[dict[str, str], bytes]:
        # Niente Authorization: il server locale non richiede credenziali.
        headers = {"Content-Type": "application/json"}
        # Prompt passato VERBATIM come unico messaggio user (prefisso stabile
        # invariato). Niente `model` nel body: il server serve il solo modello
        # caricato e ignorerebbe comunque il campo. Tuning params PRIMA, chiavi
        # fisse DOPO (stessa difesa in profondità del provider OpenRouter).
        payload: dict[str, object] = {
            **self._params,
            "messages": [{"role": "user", "content": prompt}],
        }
        return headers, json.dumps(payload).encode("utf-8")


class LlamaCppServerNotReady(Exception):
    """Il `llama-server` locale non è raggiungibile o non ha caricato il modello."""


#: Firma della probe di readiness: `probe(url, timeout) -> status HTTP`.
#: Può sollevare `OSError` (connessione rifiutata, DNS, ...). Iniettabile nei
#: test; il default è la probe urllib reale.
HealthProbe = Callable[[str, float], int]


def _urllib_health_probe(url: str, timeout: float) -> int:
    """Probe reale di `GET /health` con stdlib urllib (nessuna dipendenza).

    Usa l'opener locale (no proxy, no redirect), così una richiesta a localhost
    non viene instradata a un proxy aziendale e un 3xx non viene seguito — il
    probe di readiness e il transport di completamento restano coerenti.
    """
    req = urllib.request.Request(url, method="GET")
    try:
        with _local_opener.open(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:  # status di errore (es. 503 in load)
        with exc:  # HTTPError è file-like: chiudiamo il socket sottostante
            return exc.code


def check_server_ready(
    base_url: str,
    *,
    probe: HealthProbe | None = None,
    timeout: float = _HEALTH_TIMEOUT,
) -> None:
    """Verifica che il server sia su E col modello caricato (`GET /health`).

    200 = pronto; qualsiasi altro esito solleva `LlamaCppServerNotReady` con
    un messaggio azionabile in italiano che include il comando per avviare
    `llama-server` a mano.
    """
    url = f"{base_url.rstrip('/')}/health"
    probe = probe or _urllib_health_probe
    try:
        status = probe(url, timeout)
    except (OSError, http.client.HTTPException) as exc:
        # OSError = connessione rifiutata/DNS/timeout; http.client.HTTPException
        # (es. BadStatusLine) = risposta non-HTTP, tipica di una porta che punta
        # a un altro servizio locale. urllib NON incapsula HTTPException in
        # URLError, quindi senza questo ramo sfuggirebbe come traceback nudo.
        raise LlamaCppServerNotReady(
            f"llama-server non raggiungibile su {base_url}: il server locale "
            f"va avviato a mano prima di minnarone, ad esempio con:\n"
            f"  {LLAMA_SERVER_COMMAND}"
        ) from exc
    if status == 503:
        raise LlamaCppServerNotReady(
            f"llama-server su {base_url} sta ancora caricando il modello "
            f"(HTTP 503): riprova tra qualche secondo. Se non è avviato:\n"
            f"  {LLAMA_SERVER_COMMAND}"
        )
    if status != 200:
        raise LlamaCppServerNotReady(
            f"llama-server su {base_url} ha risposto {status} a /health "
            f"(atteso 200): verifica che all'indirizzo ci sia un llama-server, "
            f"ad esempio avviato con:\n  {LLAMA_SERVER_COMMAND}"
        )


#: Firma della probe di `/props`: `probe(url, timeout) -> props JSON parsato`.
#: Può sollevare `OSError`/`HTTPException` (server giù, non-HTTP, ...) o
#: `HTTPError` (status di errore). Iniettabile nei test; il default è la probe
#: urllib reale.
VisionProbe = Callable[[str, float], object]


def _urllib_vision_probe(url: str, timeout: float) -> object:
    """Probe reale di `GET /props` con stdlib urllib (nessuna dipendenza).

    Ritorna il JSON parsato di `/props`. Usa l'opener locale (no proxy, no
    redirect), coerente con readiness e transport di completamento.
    """
    req = urllib.request.Request(url, method="GET")
    with _local_opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _props_report_vision(props: object) -> bool:
    """True se `/props` dichiara `modalities.vision == true`.

    Difensivo su shape inattese: un server non multimodale (senza `--mmproj`)
    espone `modalities.vision == false` o non espone affatto `modalities`.
    """
    if not isinstance(props, Mapping):
        return False
    modalities = props.get("modalities")
    if not isinstance(modalities, Mapping):
        return False
    return modalities.get("vision") is True


def check_vision_ready(
    base_url: str,
    *,
    probe: VisionProbe | None = None,
    timeout: float = _HEALTH_TIMEOUT,
) -> None:
    """Verifica che il `llama-server` esponga la visione (`GET /props`).

    Richiesto dal backend di captioning `vlm.backend: llamacpp`: l'istanza deve
    essere stata avviata con `--mmproj`, altrimenti `modalities.vision` è falso
    (o assente) e i frame non verrebbero mai descritti. Solleva
    `LlamaCppServerNotReady` con un messaggio azionabile in italiano che ricorda
    `--mmproj` nel comando di `llama-server`.
    """
    url = f"{base_url.rstrip('/')}/props"
    probe = probe or _urllib_vision_probe
    try:
        props = probe(url, timeout)
    except (OSError, http.client.HTTPException) as exc:
        # HTTPError (status di errore) è sottoclasse di OSError: un 503 in
        # caricamento o un 404 finiscono qui come "non raggiungibile".
        raise LlamaCppServerNotReady(
            f"llama-server non raggiungibile su {base_url} per il check vision "
            f"(GET /props): avvia l'istanza multimodale a mano, ad esempio con:\n"
            f"  {LLAMA_SERVER_MULTIMODAL_COMMAND}"
        ) from exc
    if not _props_report_vision(props):
        raise LlamaCppServerNotReady(
            f"llama-server su {base_url} non espone la visione "
            f"(modalities.vision != true): il modello è stato caricato senza "
            f"proiettore multimodale. Riavvialo aggiungendo --mmproj <mmproj.gguf>, "
            f"ad esempio:\n  {LLAMA_SERVER_MULTIMODAL_COMMAND}"
        )


def ensure_llamacpp_ready(
    config: "Config",
    *,
    probe: HealthProbe | None = None,
    vision_probe: VisionProbe | None = None,
) -> None:
    """Health-check d'avvio del loop live: no-op per i provider cloud.

    Chiamato dalla CLI SOLO sul percorso live (mai in `--check`, che resta un
    dry-run senza rete). Solleva `LlamaCppServerNotReady` se il server locale
    non è pronto, con istruzioni per avviarlo.

    Due controlli indipendenti sulla stessa istanza `llama-server` locale:
    - `llm_provider: llamacpp` → readiness testo (`GET /health`);
    - `vlm.backend: llamacpp` → capacità vision (`GET /props`), anche con LLM
      cloud (il captioner riusa comunque `llamacpp.base_url`).
    """
    if config.llm_provider == "llamacpp":
        check_server_ready(config.llamacpp.base_url, probe=probe)
    if config.vlm.backend == "llamacpp":
        check_vision_ready(config.llamacpp.base_url, probe=vision_probe)
