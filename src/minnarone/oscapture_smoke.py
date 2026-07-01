"""Runner di smoke capture-only per la cattura del SO.

Specularmente allo smoke Twitch (`run_twitch_smoke`), ma la sorgente è la
cattura audio/video della macchina locale (es. una call Teams) invece di uno
stream remoto. Costruisce gli adapter di canale abilitati (`os_audio_capture` /
`os_screen_capture`) dalle sorgenti device iniettate e delega la scrittura degli
artifact bounded al writer esistente (`capture_twitch_smoke`), che è già
generico rispetto alla lista di `SourceAdapter`.

Iniettabilità del device. Le sorgenti (`audio_source` / `video_source`) sono
`Captured` (iterabili sync o async di `AudioChunk` / `VideoFrame`). Quando non
iniettate, si costruiscono LAZILY dai backend device reali
(`make_device_capture_source` / `make_device_screen_capture_source`): la loro
costruzione NON tocca l'hardware, l'apertura del device avviene alla prima
iterazione (innescata da `start()` del pump). Così il runner è testabile
offline con liste in-memory.

Capture-only: nessun ASR/VLM. L'unica eccezione è il percorso VAD diagnostico
(come nello smoke Twitch), che segmenta l'audio e riporta conteggi/durate senza
trascrivere.

Riuso del writer. Il writer di artifact `capture_twitch_smoke` accetta già una
`Sequence[SourceAdapter]` neutra: viene riusato così com'è, senza duplicare la
logica di scrittura (nessun R0801). Solo il naming del modulo conserva il
prefisso storico "twitch".
"""

from __future__ import annotations

from pathlib import Path

from .audio import Vad
from .capture import (
    Captured,
    make_device_capture_source,
    make_device_screen_capture_source,
    os_audio_capture,
    os_screen_capture,
)
from .source import SourceAdapter
from .twitch_audio import pcm_chunk_size_bytes
from .twitch_smoke import _build_streaming_vad
from .twitch_smoke_artifacts import SmokeStats, capture_twitch_smoke
from .twitch_video import validate_video_fps


async def run_oscapture_smoke(
    *,
    output_dir: str | Path,
    duration: float,
    enable_audio: bool = True,
    enable_video: bool = True,
    sample_rate: int = 16_000,
    audio_chunk_seconds: float = 1.0,
    monitor: int = 1,
    video_fps: float = 1.0,
    max_audio_samples: int = 3,
    max_video_frames: int = 3,
    enable_vad_diagnostic: bool = False,
    vad_mode: int = 2,
    vad_frame_ms: int = 30,
    vad_padding_ms: int = 300,
    vad_max_utterance_seconds: float = 30.0,
    audio_source: Captured | None = None,
    video_source: Captured | None = None,
    vad: Vad | None = None,
) -> SmokeStats:
    """Costruisce gli adapter di canale abilitati e scrive gli artifact smoke.

    Args:
        output_dir: directory degli artifact (raw/audio/*.pcm, raw/video/*.jpg,
            stats.json).
        duration: durata bounded della cattura in secondi.
        enable_audio / enable_video: quali canali abilitare.
        sample_rate / audio_chunk_seconds: parametri della sorgente audio device
            (usati solo se `audio_source` non è iniettata).
        monitor / video_fps: parametri della sorgente video device (usati solo se
            `video_source` non è iniettata).
        max_audio_samples / max_video_frames: cap sugli artifact raw salvati.
        enable_vad_diagnostic + vad_*: segmentazione VAD diagnostica (senza ASR).
        audio_source / video_source: sorgenti device iniettate (`AudioChunk` /
            `VideoFrame`); se None, si usano i backend device reali lazily.
        vad: VAD diagnostico iniettato; se None e la diagnostica è attiva, se ne
            costruisce uno WebRTC dai parametri.

    Returns:
        `SmokeStats` con i conteggi degli eventi catturati e le failure.
    """
    adapters: list[SourceAdapter] = []
    vad_diagnostic: Vad | None = None
    if enable_audio:
        pcm_chunk_size_bytes(audio_chunk_seconds)
        source = (
            audio_source
            if audio_source is not None
            else make_device_capture_source(
                sample_rate=sample_rate,
                chunk_seconds=audio_chunk_seconds,
            )
        )
        adapters.append(os_audio_capture(source))
        if enable_vad_diagnostic:
            vad_diagnostic = vad or _build_streaming_vad(
                mode=vad_mode,
                frame_ms=vad_frame_ms,
                padding_ms=vad_padding_ms,
                max_utterance_seconds=vad_max_utterance_seconds,
            )
    elif enable_vad_diagnostic:
        raise ValueError("diagnostica VAD richiede audio abilitato")
    if enable_video:
        validate_video_fps(video_fps)
        frame_source = (
            video_source
            if video_source is not None
            else make_device_screen_capture_source(
                monitor=monitor,
                fps=video_fps,
            )
        )
        adapters.append(os_screen_capture(frame_source))
    return await capture_twitch_smoke(
        adapters,
        output_dir=output_dir,
        duration=duration,
        max_audio_samples=max_audio_samples,
        max_video_frames=max_video_frames,
        vad=vad_diagnostic,
    )
