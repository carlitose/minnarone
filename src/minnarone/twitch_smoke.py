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

from .twitch_chat import run_twitch_chat_smoke


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="minnarone-twitch-chat-smoke",
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


def _missing_twitch_env() -> list[str]:
    required = ["TWITCH_BOT_USERNAME", "TWITCH_OAUTH_TOKEN"]
    return [name for name in required if not os.environ.get(name)]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the manual chat-only Twitch smoke and return a process exit code."""
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
