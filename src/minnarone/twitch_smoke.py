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

from .audio import Vad
from .dotenv import load_env_files
from .source import SourceAdapter
from .twitch_audio import ProcessRunner, TwitchAudioReader, pcm_chunk_size_bytes
from .twitch_chat import TwitchChatReader, capture_chat_smoke
from .twitch_smoke_artifacts import SmokeStats, capture_twitch_smoke
from .twitch_video import TwitchVideoReader, validate_video_fps
from .vad import StreamingVad, VadConfig, WebRtcVadDetector


def add_common_smoke_arguments(parser: argparse.ArgumentParser) -> None:
    """Aggiunge gli argomenti comuni agli smoke Twitch e cattura SO.

    Fattorizza i flag audio/VAD/video condivisi (`--audio-chunk-seconds`,
    `--max-audio-samples`, la famiglia `--vad-*`, `--video-fps`,
    `--max-video-frames`) per evitare duplicazione tra le due CLI (no R0801).
    """
    parser.add_argument(
        "--audio-chunk-seconds",
        type=float,
        default=1.0,
        help="duration of each PCM audio chunk",
    )
    parser.add_argument(
        "--max-audio-samples",
        type=int,
        default=3,
        help="maximum number of .pcm samples to save",
    )
    parser.add_argument(
        "--vad-diagnostic",
        action="store_true",
        help="segment audio with VAD and report counts/durations without ASR",
    )
    parser.add_argument(
        "--vad-mode",
        type=int,
        default=2,
        help="WebRTC VAD aggressiveness: 0 least aggressive, 3 most aggressive",
    )
    parser.add_argument(
        "--vad-frame-ms",
        type=int,
        default=30,
        help="VAD frame duration in ms: 10, 20, or 30",
    )
    parser.add_argument(
        "--vad-padding-ms",
        type=int,
        default=300,
        help="VAD padding/hangover in milliseconds",
    )
    parser.add_argument(
        "--vad-max-utterance-seconds",
        type=float,
        default=30.0,
        help="maximum VAD utterance duration before flush",
    )
    parser.add_argument(
        "--video-fps",
        type=float,
        default=1.0,
        help="video frames per second to sample",
    )
    parser.add_argument(
        "--max-video-frames",
        type=int,
        default=3,
        help="maximum number of .jpg frames to save",
    )


def _parse_args(argv: Sequence[str], *, prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Read-only Twitch capture to local smoke artifacts.",
    )
    parser.add_argument("--channel", required=True, help="Twitch channel to read")
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
        help="enable raw audio capture through Streamlink/FFmpeg",
    )
    parser.add_argument(
        "--no-chat",
        action="store_true",
        help="disable IRC chat capture",
    )
    parser.add_argument(
        "--strict-chat",
        action="store_true",
        help=("treat zero chat events as a failure even when audio/video succeeded"),
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="enable raw video capture through Streamlink/FFmpeg",
    )
    parser.add_argument(
        "--quality",
        default="best",
        help="Streamlink quality to use for raw media",
    )
    add_common_smoke_arguments(parser)
    return parser.parse_args(list(argv))


def _parse_chat_args(argv: Sequence[str], *, prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Read-only Twitch chat capture to a perceptions JSONL file.",
    )
    parser.add_argument("--channel", required=True, help="Twitch channel to read")
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="capture duration in seconds",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="path of the perceptions.jsonl file to write",
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
        print("--duration must be > 0", file=sys.stderr)
        return 2

    load_env_files()
    missing = _missing_twitch_env()
    if missing:
        print(
            "missing Twitch credentials: export " + ", ".join(missing),
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
        print(f"invalid Twitch configuration: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Twitch smoke failed: connection error ({exc})", file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print(f"Twitch smoke failed: operational timeout ({exc})", file=sys.stderr)
        return 1

    if count == 0:
        print(
            "Twitch smoke failed: no chat perceptions were written",
            file=sys.stderr,
        )
        return 1

    print(f"ok: wrote {count} chat perceptions to {args.output}")
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
    enable_vad_diagnostic: bool = False,
    vad_mode: int = 2,
    vad_frame_ms: int = 30,
    vad_padding_ms: int = 300,
    vad_max_utterance_seconds: float = 30.0,
    video_fps: float = 1.0,
    max_video_frames: int = 3,
    chat_adapter: SourceAdapter | None = None,
    audio_adapter: SourceAdapter | None = None,
    video_adapter: SourceAdapter | None = None,
    vad: Vad | None = None,
    audio_process_runner: ProcessRunner | None = None,
    video_process_runner: ProcessRunner | None = None,
) -> SmokeStats:
    """Build enabled Twitch readers and write bounded smoke artifacts."""
    adapters: list[SourceAdapter] = []
    vad_diagnostic = None
    if enable_chat:
        if username is None or oauth_token is None:
            raise ValueError("missing Twitch chat credentials")
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
        vad=vad_diagnostic,
    )


def _build_streaming_vad(
    *,
    mode: int,
    frame_ms: int,
    padding_ms: int,
    max_utterance_seconds: float,
) -> StreamingVad:
    config = VadConfig(
        mode=mode,
        frame_ms=frame_ms,
        padding_ms=padding_ms,
        max_utterance_seconds=max_utterance_seconds,
    )
    return StreamingVad(config=config, detector=WebRtcVadDetector(config))


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
    stats: SmokeStats,
    *,
    enable_chat: bool,
    enable_audio: bool,
    enable_video: bool,
    strict_chat: bool = False,
) -> list[str]:
    failures = list(stats.failures)
    successful_media = (enable_audio and stats.audio_events > 0) or (
        enable_video and stats.video_events > 0
    )
    if enable_chat and stats.chat_events == 0 and (strict_chat or not successful_media):
        failures.append("chat: no events captured")
    if enable_audio and stats.audio_events == 0:
        failures.append("audio: no events captured")
    if enable_video and stats.video_events == 0:
        failures.append("video: no events captured")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    """Run the manual Twitch smoke and return a process exit code."""
    try:
        prog = Path(sys.argv[0]).name if argv is None else "minnarone-twitch-smoke"
        args = _parse_args(sys.argv[1:] if argv is None else argv, prog=prog)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    if not math.isfinite(args.duration) or args.duration <= 0:
        print("--duration must be > 0", file=sys.stderr)
        return 2
    if not math.isfinite(args.audio_chunk_seconds) or args.audio_chunk_seconds <= 0:
        print("--audio-chunk-seconds must be > 0", file=sys.stderr)
        return 2
    if not math.isfinite(args.video_fps) or args.video_fps <= 0:
        print("--video-fps must be > 0", file=sys.stderr)
        return 2
    if args.max_audio_samples < 0:
        print("--max-audio-samples must be >= 0", file=sys.stderr)
        return 2
    if args.vad_mode not in {0, 1, 2, 3}:
        print("--vad-mode must be 0, 1, 2, or 3", file=sys.stderr)
        return 2
    if args.vad_frame_ms not in {10, 20, 30}:
        print("--vad-frame-ms must be 10, 20, or 30", file=sys.stderr)
        return 2
    if args.vad_padding_ms <= 0:
        print("--vad-padding-ms must be > 0", file=sys.stderr)
        return 2
    if (
        not math.isfinite(args.vad_max_utterance_seconds)
        or args.vad_max_utterance_seconds <= 0
    ):
        print("--vad-max-utterance-seconds must be > 0", file=sys.stderr)
        return 2
    if args.max_video_frames < 0:
        print("--max-video-frames must be >= 0", file=sys.stderr)
        return 2

    load_env_files()
    enable_chat = not args.no_chat
    enable_audio = bool(args.audio or args.vad_diagnostic)
    enable_video = bool(args.video)
    if not enable_chat and not enable_audio and not enable_video:
        print("enable at least chat, audio, or video", file=sys.stderr)
        return 2

    missing = _missing_twitch_env() if enable_chat else []
    if missing:
        print(
            "missing Twitch credentials: export " + ", ".join(missing),
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
                enable_vad_diagnostic=args.vad_diagnostic,
                vad_mode=args.vad_mode,
                vad_frame_ms=args.vad_frame_ms,
                vad_padding_ms=args.vad_padding_ms,
                vad_max_utterance_seconds=args.vad_max_utterance_seconds,
                video_fps=args.video_fps,
                max_video_frames=args.max_video_frames,
            )
        )
    except ValueError as exc:
        print(f"invalid Twitch configuration: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Twitch smoke failed: connection error ({exc})", file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print(f"Twitch smoke failed: operational timeout ({exc})", file=sys.stderr)
        return 1

    failures = _smoke_failures(
        stats,
        enable_chat=enable_chat,
        enable_audio=enable_audio,
        enable_video=enable_video,
        strict_chat=args.strict_chat,
    )
    if failures:
        print(
            "Twitch smoke failed: " + "; ".join(failures),
            file=sys.stderr,
        )
        return 1

    if enable_chat and stats.chat_events == 0:
        print(
            "note: chat was quiet during the window; requested audio/video "
            "succeeded (use --strict-chat to make zero chat events fail)"
        )

    print(
        "ok: "
        f"chat={stats.chat_events}, "
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
