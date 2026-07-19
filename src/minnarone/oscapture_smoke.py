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

import argparse
import asyncio
import math
import sys
from collections.abc import Sequence
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
from .twitch_smoke import _build_streaming_vad, add_common_smoke_arguments
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
        raise ValueError("VAD diagnostics require audio to be enabled")
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


def _parse_args(argv: Sequence[str], *, prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Capture local OS audio/video to bounded smoke artifacts.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="capture duration in seconds",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="smoke artifact directory to write",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="enable audio capture from the loopback device",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="enable screen capture from the selected monitor",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=1,
        help="index of the monitor to capture (>= 1)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16_000,
        help="sample rate of the audio device source",
    )
    add_common_smoke_arguments(parser)
    return parser.parse_args(list(argv))


def _validate_args(args: argparse.Namespace) -> str | None:
    """Valida gli argomenti; ritorna un messaggio d'errore o None se validi."""
    if not math.isfinite(args.duration) or args.duration <= 0:
        return "--duration must be > 0"
    if not math.isfinite(args.audio_chunk_seconds) or args.audio_chunk_seconds <= 0:
        return "--audio-chunk-seconds must be > 0"
    if not math.isfinite(args.video_fps) or args.video_fps <= 0:
        return "--video-fps must be > 0"
    if args.monitor < 1:
        return "--monitor must be >= 1"
    if args.sample_rate <= 0:
        return "--sample-rate must be > 0"
    if args.max_audio_samples < 0:
        return "--max-audio-samples must be >= 0"
    if args.max_video_frames < 0:
        return "--max-video-frames must be >= 0"
    if args.vad_mode not in {0, 1, 2, 3}:
        return "--vad-mode must be 0, 1, 2, or 3"
    if args.vad_frame_ms not in {10, 20, 30}:
        return "--vad-frame-ms must be 10, 20, or 30"
    if args.vad_padding_ms <= 0:
        return "--vad-padding-ms must be > 0"
    if (
        not math.isfinite(args.vad_max_utterance_seconds)
        or args.vad_max_utterance_seconds <= 0
    ):
        return "--vad-max-utterance-seconds must be > 0"
    return None


def _smoke_failures(
    stats: SmokeStats, *, enable_audio: bool, enable_video: bool
) -> list[str]:
    failures = list(stats.failures)
    if enable_audio and stats.audio_events == 0:
        failures.append("audio: no events captured")
    if enable_video and stats.video_events == 0:
        failures.append("video: no events captured")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    """Esegue lo smoke di cattura SO e ritorna il codice di uscita del processo."""
    try:
        prog = Path(sys.argv[0]).name if argv is None else "minnarone-oscapture-smoke"
        args = _parse_args(sys.argv[1:] if argv is None else argv, prog=prog)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    error = _validate_args(args)
    if error is not None:
        print(error, file=sys.stderr)
        return 2

    enable_audio = bool(args.audio or args.vad_diagnostic)
    enable_video = bool(args.video)
    if not enable_audio and not enable_video:
        print("enable at least audio or video", file=sys.stderr)
        return 2

    try:
        stats = asyncio.run(
            run_oscapture_smoke(
                output_dir=args.output,
                duration=args.duration,
                enable_audio=enable_audio,
                enable_video=enable_video,
                sample_rate=args.sample_rate,
                audio_chunk_seconds=args.audio_chunk_seconds,
                monitor=args.monitor,
                video_fps=args.video_fps,
                max_audio_samples=args.max_audio_samples,
                max_video_frames=args.max_video_frames,
                enable_vad_diagnostic=args.vad_diagnostic,
                vad_mode=args.vad_mode,
                vad_frame_ms=args.vad_frame_ms,
                vad_padding_ms=args.vad_padding_ms,
                vad_max_utterance_seconds=args.vad_max_utterance_seconds,
            )
        )
    except ValueError as exc:
        print(f"invalid OS capture configuration: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(
            f"OS capture smoke failed: device error ({exc})",
            file=sys.stderr,
        )
        return 1
    except TimeoutError as exc:
        print(
            f"OS capture smoke failed: operational timeout ({exc})",
            file=sys.stderr,
        )
        return 1

    failures = _smoke_failures(
        stats,
        enable_audio=enable_audio,
        enable_video=enable_video,
    )
    if failures:
        print("OS capture smoke failed: " + "; ".join(failures), file=sys.stderr)
        return 1

    print(
        "ok: "
        f"audio={stats.audio_events}, "
        f"audio_samples={stats.audio_samples_saved}, "
        f"vad_utterances={stats.vad_utterances}, "
        "vad_durations_ms="
        f"{','.join(str(value) for value in stats.vad_utterance_durations_ms)}, "
        f"video={stats.video_events}, "
        f"video_frames={stats.video_frames_saved}, "
        f"stats={Path(args.output) / 'stats.json'}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
