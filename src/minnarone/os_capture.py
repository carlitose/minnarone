"""`OsCaptureAdapter`: cattura del SO come unico `SourceAdapter`.

Modulo profondo che, data una `OsCaptureConfig` e le sorgenti device iniettate
(audio/video), costruisce i `StreamCaptureAdapter` di canale (via i costruttori
ergonomici `os_audio_capture` / `os_screen_capture`) e li compone in un unico
stream `RawEvent` bounded tramite `MergingSourceAdapter` (motore neutro già
testato). Osserva l'output audio/video della macchina locale (es. una call
Teams) invece di uno stream remoto.

Iniettabilità del device. Il *come* si arriva ai campioni (audio o frame) è un
dettaglio del SO (soundcard / mss / ...) e vive altrove: qui le sorgenti sono
INIETTATE come `Captured` (un iterabile sincrono o asincrono di `AudioChunk` o
`VideoFrame`). Così il modulo resta neutro rispetto al device reale e testabile
offline con liste in-memory. Il contratto lazy dello `StreamCaptureAdapter` è
preservato: le sorgenti non vengono iterate prima di `start()`.

Il merge/backpressure NON è reimplementato: è delegato interamente a
`MergingSourceAdapter`. Qui vive solo la parte OS-specifica: selezione dei
canali attivi dalla config e costruzione dei reader di canale con il controllo
della sorgente mancante (specularmente a come Twitch controlla le credenziali).
`channels()/start()/stop()/events()/stats()` sono delegati al merger.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .capture import Captured, os_audio_capture, os_screen_capture
from .config import OsCaptureConfig
from .merge import MergeStats, MergingSourceAdapter
from .source import RawEvent, SourceAdapter


class OsCaptureAdapter(SourceAdapter):
    """Compone i reader di cattura audio/video del SO in un unico source adapter.

    Args:
        config: quali canali abilitare (audio/video) e i relativi parametri.
        audio_source: sorgente device audio iniettata (`AudioChunk`). Obbligatoria
            se `config.audio` è attivo.
        video_source: sorgente device video iniettata (`VideoFrame`). Obbligatoria
            se `config.video` è attivo.
        queue_size / cleanup_timeout: passthrough al `MergingSourceAdapter`.
    """

    def __init__(
        self,
        config: OsCaptureConfig,
        *,
        audio_source: Captured | None = None,
        video_source: Captured | None = None,
        queue_size: int = 100,
        cleanup_timeout: float = 5.0,
    ) -> None:
        readers = self._build_readers(
            config,
            audio_source=audio_source,
            video_source=video_source,
        )
        # Nessun canale prioritario: la cattura del SO non ha una chat da
        # proteggere, quindi audio e video sono paritari sotto pressione.
        self._merger = MergingSourceAdapter(
            readers=readers,
            priority_channels=(),
            queue_size=queue_size,
            cleanup_timeout=cleanup_timeout,
        )

    def channels(self) -> set[str]:
        return self._merger.channels()

    async def start(self) -> None:
        await self._merger.start()

    async def stop(self) -> None:
        await self._merger.stop()

    def events(self) -> AsyncIterator[RawEvent]:
        # Nessuna traduzione di errore OS-specifica: lo stream del motore neutro
        # è già la superficie attesa dai chiamanti della cattura del SO.
        return self._merger.events()

    def stats(self) -> MergeStats:
        # `MergeStats` è già la forma che TUI/osservabilità leggono; non serve
        # riavvolgerla (a differenza di Twitch, che conserva un nome storico).
        return self._merger.stats()

    @staticmethod
    def _build_readers(
        config: OsCaptureConfig,
        *,
        audio_source: Captured | None,
        video_source: Captured | None,
    ) -> dict[str, SourceAdapter]:
        readers: dict[str, SourceAdapter] = {}
        if config.audio:
            if audio_source is None:
                raise ValueError(
                    "os_capture.audio is enabled but audio_source is missing"
                )
            readers["audio"] = os_audio_capture(audio_source)
        if config.video:
            if video_source is None:
                raise ValueError(
                    "os_capture.video is enabled but video_source is missing"
                )
            readers["video"] = os_screen_capture(video_source)
        return readers
