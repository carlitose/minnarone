"""Entrypoint CLI dell'app di riferimento: `python -m minnarone <config.yaml>`.

Carica e valida la `Config` dal file YAML, poi costruisce l'agente. Con
`--check` si ferma dopo il build (dry-run: nessun loop bloccante, nessuna rete,
nessun device) — utile per validare un config e in CI/test. Senza `--check`
avvia il loop di reazione live (il loop di PERCEZIONE — cattura audio/schermo —
è il passo manuale documentato nel README: richiede permessi macOS e
`OPENROUTER_API_KEY`).

Un config mancante o invalido produce un errore CHIARO su stderr e un exit code
!= 0 (riusa `ConfigError`).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from .app import build_agent
from .config import Config, ConfigError
from .live_tui import (
    LiveTuiDependencyError,
    ensure_live_tui_available,
    run_live_tui,
)
from .output_sink import MinnaroneOutputStream
from .replay import run_replay_tui
from .run_artifacts import DEFAULT_RUNS_ROOT, RunSession, create_run_session
from .twitch_stream import TwitchStreamRuntimeError


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="minnarone",
        description="Avvia l'agente Minnarone da un file di configurazione.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        help="percorso del file di config YAML",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="valida il config e costruisci l'agente senza avviare il loop",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="avvia il runtime live con la dashboard TUI di osservabilità",
    )
    parser.add_argument(
        "--replay",
        metavar="RUN_OR_JSONL",
        help="apri una run o un perceptions.jsonl in dashboard replay offline",
    )
    args = parser.parse_args(list(argv))
    if args.replay is None and args.config is None:
        parser.error("config richiesto a meno di usare --replay")
    return args


def _create_live_run_session(config: Config) -> RunSession:
    workspace_root = Path(config.facts_dir).resolve().parent
    channel = config.twitch.channel if config.twitch is not None else None
    return create_run_session(
        root=workspace_root / DEFAULT_RUNS_ROOT,
        channel=channel,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Punto d'ingresso CLI. Ritorna l'exit code (0 = ok)."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw_args)

    if args.replay is not None:
        try:
            ensure_live_tui_available()
            run_replay_tui(args.replay)
        except LiveTuiDependencyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"errore replay: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        config = Config.load(args.config)
        run_session = None
        if args.tui and not args.check:
            ensure_live_tui_available()
            run_session = _create_live_run_session(config)
        try:
            agent = (
                build_agent(
                    config,
                    run_session=run_session,
                    minnarone_output=MinnaroneOutputStream(),
                )
                if run_session is not None
                else build_agent(config)
            )
        except Exception:
            if run_session is not None:
                with suppress(Exception):
                    run_session.mark_completed()
            raise
    except ConfigError as exc:
        print(f"errore di config: {exc}", file=sys.stderr)
        return 2
    except LiveTuiDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        print(
            f"ok: agente '{config.agent_name}' costruito "
            f"(mode={config.mode.value}, provider={config.llm_provider})"
        )
        return 0

    # Avvio del loop di reazione live. La cattura di percezione (audio/schermo)
    # è il passo manuale documentato: richiede device e permessi macOS.
    try:
        if args.tui:
            run_live_tui(agent)
        else:
            asyncio.run(agent.run())
    except TwitchStreamRuntimeError as exc:
        print(f"errore runtime Twitch: {exc}", file=sys.stderr)
        return 1
    except LiveTuiDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("arresto richiesto.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
