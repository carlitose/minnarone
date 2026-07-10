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
import os
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


def load_dotenv_file(path: Path) -> list[str]:
    """Carica un file `.env` in `os.environ`, ritorna i nomi delle chiavi caricate.

    Loader minimale a zero dipendenze per la comodità dell'operatore: evita di
    riesportare i segreti (OPENROUTER_API_KEY, TWITCH_*) in ogni terminale.

    Regole:
    - file assente → no-op (lista vuota);
    - righe `KEY=VALUE`, con `KEY` alfanumerico/underscore; supporta il prefisso
      `export ` e le virgolette (singole o doppie) attorno al valore;
    - righe vuote o che iniziano con `#` ignorate; righe malformate saltate;
    - una chiave viene impostata SOLO se non già presente in `os.environ`
      (l'ambiente del terminale vince sul file — semantica dotenv standard).

    Non stampa né ritorna MAI i valori (sono segreti), solo i nomi delle chiavi.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    loaded: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded


def _load_env_files(config_path: str | None) -> None:
    """Carica i `.env` prima di leggere i segreti: dir del config, poi cwd.

    Il primo che definisce una chiave vince (config-dir ha precedenza sul cwd),
    coerente con `load_dotenv_file` che non sovrascrive chiavi già presenti.
    Così i segreti possono stare accanto ai config locali (es. `.local/.env`)
    oppure nella root del repo (`.env`).
    """
    if config_path is not None:
        load_dotenv_file(Path(config_path).resolve().parent / ".env")
    load_dotenv_file(Path(".env"))


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

    # Carica i segreti da .env (dir del config, poi cwd) prima di leggerli.
    _load_env_files(args.config)

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
