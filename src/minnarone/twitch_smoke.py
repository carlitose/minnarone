"""Manual Twitch chat smoke command.

This entrypoint is intentionally separate from the main agent CLI: it validates
capture-only Twitch chat ingestion without involving the LLM, reactor, or output
routing.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .source import SourceAdapter
from .twitch_audio import ProcessRunner, TwitchAudioReader, pcm_chunk_size_bytes
from .twitch_chat import TwitchChatReader, capture_chat_smoke
from .twitch_smoke_artifacts import SmokeStats, capture_twitch_smoke
from .twitch_video import TwitchVideoReader, validate_video_fps


def _parse_args(argv: Sequence[str], *, prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Cattura Twitch in sola lettura su artifact smoke locali.",
    )
    parser.add_argument("--channel", required=True, help="canale Twitch da leggere")
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="durata della cattura in secondi",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="directory degli artifact smoke da scrivere",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="abilita cattura audio raw via Streamlink/FFmpeg",
    )
    parser.add_argument(
        "--no-chat",
        action="store_true",
        help="disabilita la cattura chat IRC",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="abilita cattura video raw via Streamlink/FFmpeg",
    )
    parser.add_argument(
        "--quality",
        default="best",
        help="qualità Streamlink da usare per media raw",
    )
    parser.add_argument(
        "--audio-chunk-seconds",
        type=float,
        default=1.0,
        help="durata di ogni chunk PCM audio",
    )
    parser.add_argument(
        "--max-audio-samples",
        type=int,
        default=3,
        help="numero massimo di sample .pcm da salvare",
    )
    parser.add_argument(
        "--video-fps",
        type=float,
        default=1.0,
        help="frame al secondo da campionare per il video",
    )
    parser.add_argument(
        "--max-video-frames",
        type=int,
        default=3,
        help="numero massimo di frame .jpg da salvare",
    )
    return parser.parse_args(list(argv))


def _parse_chat_args(argv: Sequence[str], *, prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Cattura chat Twitch in sola lettura su un JSONL di percezioni.",
    )
    parser.add_argument("--channel", required=True, help="canale Twitch da leggere")
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="durata della cattura in secondi",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="percorso del file perceptions.jsonl da scrivere",
    )
    return parser.parse_args(list(argv))


def chat_main(argv: Sequence[str] | None = None) -> int:
    """Legacy chat-only smoke command: `--output` is a JSONL file path."""
    try:
        args = _parse_chat_args(
            sys.argv[1:] if argv is None else argv,
            prog="minnarone-twitch-chat-smoke",
        )
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    if not math.isfinite(args.duration) or args.duration <= 0:
        print("--duration deve essere > 0", file=sys.stderr)
        return 2

    missing = _missing_twitch_env()
    if missing:
        print(
            "credenziali Twitch mancanti: esporta " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    try:
        count = asyncio.run(
            run_twitch_chat_smoke(
                channel=args.channel,
                username=os.environ["TWITCH_BOT_USERNAME"],
                oauth_token=os.environ["TWITCH_OAUTH_TOKEN"],
                output_path=args.output,
                duration=args.duration,
            )
        )
    except ValueError as exc:
        print(f"configurazione Twitch non valida: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"smoke Twitch fallito: errore di connessione ({exc})", file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print(f"smoke Twitch fallito: timeout operativo ({exc})", file=sys.stderr)
        return 1

    if count == 0:
        print(
            "smoke Twitch fallito: nessuna percezione chat scritta",
            file=sys.stderr,
        )
        return 1

    print(f"ok: scritte {count} percezioni chat in {args.output}")
    return 0


def _missing_twitch_env() -> list[str]:
    required = ["TWITCH_BOT_USERNAME", "TWITCH_OAUTH_TOKEN"]
    return [name for name in required if not os.environ.get(name)]


async def run_twitch_smoke(
    *,
    channel: str,
    output_dir: str | Path,
    duration: float,
    enable_chat: bool = True,
    enable_audio: bool = False,
    enable_video: bool = False,
    username: str | None = None,
    oauth_token: str | None = None,
    quality: str = "audio_only",
    audio_chunk_seconds: float = 1.0,
    max_audio_samples: int = 3,
    video_fps: float = 1.0,
    max_video_frames: int = 3,
    chat_adapter: SourceAdapter | None = None,
    audio_adapter: SourceAdapter | None = None,
    video_adapter: SourceAdapter | None = None,
    audio_process_runner: ProcessRunner | None = None,
    video_process_runner: ProcessRunner | None = None,
) -> SmokeStats:
    """Build enabled Twitch readers and write bounded smoke artifacts."""
    adapters: list[SourceAdapter] = []
    if enable_chat:
        if username is None or oauth_token is None:
            raise ValueError("credenziali Twitch chat mancanti")
        adapters.append(
            chat_adapter
            or TwitchChatReader(
                channel=channel,
                username=username,
                oauth_token=oauth_token,
            )
        )
    if enable_audio:
        pcm_chunk_size_bytes(audio_chunk_seconds)
        adapters.append(
            audio_adapter
            or TwitchAudioReader(
                channel=channel,
                quality=quality,
                chunk_seconds=audio_chunk_seconds,
                process_runner=audio_process_runner,
            )
        )
    if enable_video:
        validate_video_fps(video_fps)
        adapters.append(
            video_adapter
            or TwitchVideoReader(
                channel=channel,
                quality=quality,
                fps=video_fps,
                process_runner=video_process_runner,
            )
        )
    return await capture_twitch_smoke(
        adapters,
        output_dir=output_dir,
        duration=duration,
        max_audio_samples=max_audio_samples,
        max_video_frames=max_video_frames,
    )


async def run_twitch_chat_smoke(
    *,
    channel: str,
    username: str,
    oauth_token: str,
    output_path: str | Path,
    duration: float,
) -> int:
    """Backwards-compatible chat-only wrapper used by issue-01 tests."""
    reader = TwitchChatReader(
        channel=channel,
        username=username,
        oauth_token=oauth_token,
    )
    return await capture_chat_smoke(reader, output_path=output_path, duration=duration)


def _smoke_failures(
    stats: SmokeStats, *, enable_chat: bool, enable_audio: bool, enable_video: bool
) -> list[str]:
    failures = list(stats.failures)
    if enable_chat and stats.chat_events == 0:
        failures.append("chat: nessun evento catturato")
    if enable_audio and stats.audio_events == 0:
        failures.append("audio: nessun evento catturato")
    if enable_video and stats.video_events == 0:
        failures.append("video: nessun evento catturato")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    """Run the manual Twitch smoke and return a process exit code."""
    try:
        prog = Path(sys.argv[0]).name if argv is None else "minnarone-twitch-smoke"
        args = _parse_args(sys.argv[1:] if argv is None else argv, prog=prog)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    if not math.isfinite(args.duration) or args.duration <= 0:
        print("--duration deve essere > 0", file=sys.stderr)
        return 2
    if not math.isfinite(args.audio_chunk_seconds) or args.audio_chunk_seconds <= 0:
        print("--audio-chunk-seconds deve essere > 0", file=sys.stderr)
        return 2
    if not math.isfinite(args.video_fps) or args.video_fps <= 0:
        print("--video-fps deve essere > 0", file=sys.stderr)
        return 2
    if args.max_audio_samples < 0:
        print("--max-audio-samples deve essere >= 0", file=sys.stderr)
        return 2
    if args.max_video_frames < 0:
        print("--max-video-frames deve essere >= 0", file=sys.stderr)
        return 2

    enable_chat = not args.no_chat
    enable_audio = bool(args.audio)
    enable_video = bool(args.video)
    if not enable_chat and not enable_audio and not enable_video:
        print("abilita almeno chat, audio o video", file=sys.stderr)
        return 2

    missing = _missing_twitch_env() if enable_chat else []
    if missing:
        print(
            "credenziali Twitch mancanti: esporta " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    try:
        stats = asyncio.run(
            run_twitch_smoke(
                channel=args.channel,
                username=os.environ.get("TWITCH_BOT_USERNAME"),
                oauth_token=os.environ.get("TWITCH_OAUTH_TOKEN"),
                output_dir=args.output,
                duration=args.duration,
                enable_chat=enable_chat,
                enable_audio=enable_audio,
                enable_video=enable_video,
                quality=args.quality,
                audio_chunk_seconds=args.audio_chunk_seconds,
                max_audio_samples=args.max_audio_samples,
                video_fps=args.video_fps,
                max_video_frames=args.max_video_frames,
            )
        )
    except ValueError as exc:
        print(f"configurazione Twitch non valida: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"smoke Twitch fallito: errore di connessione ({exc})", file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print(f"smoke Twitch fallito: timeout operativo ({exc})", file=sys.stderr)
        return 1

    failures = _smoke_failures(
        stats,
        enable_chat=enable_chat,
        enable_audio=enable_audio,
        enable_video=enable_video,
    )
    if failures:
        print(
            "smoke Twitch fallito: " + "; ".join(failures),
            file=sys.stderr,
        )
        return 1

    print(
        "ok: "
        f"chat={stats.chat_events}, "
        f"audio={stats.audio_events}, "
        f"audio_samples={stats.audio_samples_saved}, "
        f"video={stats.video_events}, "
        f"video_frames={stats.video_frames_saved}, "
        f"stats={Path(args.output) / 'stats.json'}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
