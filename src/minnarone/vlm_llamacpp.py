"""Backend di captioning VLM via `llama-server` multimodale locale.

Alternativa a `Qwen2VlCaptioner` (`vlm.py`, runtime torch): invia il frame come
immagine JPEG base64 all'istanza multimodale `llama-server` e ritorna una
caption. Riusa il preprocessing di `vlm.py` (`frame_to_pil_image`,
`downscale_image_for_vlm`, `_normalize_caption`) e il trasporto locale di
`llamacpp.py` (`_local_transport`: opener no-proxy/no-redirect). Endpoint
OpenAI-compatibile `POST {base_url}/v1/chat/completions` con l'immagine in un
content-part `image_url` (contratto validato nello spike, ticket 04).

Contratto errore best-effort: `caption` ritorna "" (salta il frame) su errore
di trasporto/HTTP o risposta malformata, loggando l'evento. Diverge DI PROPOSITO
da `Qwen2VlCaptioner`, che SOLLEVA: un captioner live e' best-effort e non deve
uccidere il canale video per un errore di rete transitorio.

Questo modulo NON importa mai torch/transformers: il path llamacpp resta
leggero (solo Pillow, gia' lazy negli helper di `vlm.py`), cosi' l'installazione
solo-llama.cpp non trascina l'extra `vlm`.
"""

from __future__ import annotations

import base64
import http.client
import json
import logging
from io import BytesIO

from .llamacpp import DEFAULT_BASE_URL, _local_transport
from .openrouter import Transport, TransportError
from .video import VideoFrame
from .vlm import (
    QwenVlConfig,
    _normalize_caption,
    downscale_image_for_vlm,
    frame_to_pil_image,
)

_logger = logging.getLogger(__name__)


class LlamaCppCaptioner:
    """Descrive un `VideoFrame` via `llama-server` multimodale locale."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        config: QwenVlConfig,
        transport: Transport | None = None,
        image_module: object | None = None,
        timeout: float | None = None,
    ) -> None:
        self._config = config
        self._base_url = base_url.rstrip("/")
        self._url = f"{self._base_url}/v1/chat/completions"
        # Trasporto iniettabile (fake nei test); default = opener locale
        # no-proxy/no-redirect condiviso col provider LLM llama.cpp.
        self._transport = transport or _local_transport
        # `image_module` iniettabile per i test (fake PIL); a None l'helper di
        # `vlm.py` importa Pillow in modo lazy.
        self._image_module = image_module
        self._timeout = timeout if timeout is not None else config.timeout_seconds

    def caption(self, frame: VideoFrame) -> str:
        """Ritorna una caption per `frame`, o "" su errore (best-effort)."""
        try:
            data_uri = self._frame_to_jpeg_data_uri(frame)
            headers, body = self._build_request(data_uri)
            response = self._transport(
                url=self._url,
                headers=headers,
                body=body,
                timeout=self._timeout,
            )
        except (TransportError, OSError, http.client.HTTPException) as exc:
            # TransportTimeout e' sottoclasse di TransportError. OSError copre
            # connessione rifiutata/DNS a sessione avviata. http.client.HTTPException
            # (es. IncompleteRead/BadStatusLine quando il server chiude a meta'
            # risposta) NON e' incapsulata da urllib e sfuggirebbe a _open_request:
            # la catturiamo qui come fanno check_server_ready/check_vision_ready.
            # Best-effort: salta il frame senza contarlo come fallimento opaco.
            _logger.warning("llama-server caption: errore di trasporto: %s", exc)
            return ""
        raw = self._extract_caption(response)
        if raw is None:
            return ""
        return _normalize_caption(raw, self._config)

    def _frame_to_jpeg_data_uri(self, frame: VideoFrame) -> str:
        image = frame_to_pil_image(frame, image_module=self._image_module)
        image = downscale_image_for_vlm(
            image,
            max_edge=self._config.max_image_edge,
            max_pixels=self._config.max_image_pixels,
            image_module=self._image_module,
        )
        buffer = BytesIO()
        image.save(buffer, format="JPEG")  # type: ignore[union-attr]
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _build_request(self, data_uri: str) -> tuple[dict[str, str], bytes]:
        # Niente Authorization: il server locale non richiede credenziali.
        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._config.prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "max_tokens": self._config.max_new_tokens,
        }
        return headers, json.dumps(payload).encode("utf-8")

    def _extract_caption(self, response: object) -> str | None:
        status = getattr(response, "status", None)
        if status != 200:
            _logger.warning("llama-server caption: HTTP %s inatteso", status)
            return None
        try:
            payload = json.loads(response.body)  # type: ignore[union-attr]
            content = payload["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            _logger.warning("llama-server caption: risposta malformata: %s", exc)
            return None
        if not isinstance(content, str):
            _logger.warning("llama-server caption: content non testuale")
            return None
        return content
