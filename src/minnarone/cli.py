"""Entrypoint CLI dell'app di riferimento: `python -m minnarone <config.yaml>`.

Carica e valida la `Config` dal file YAML, poi costruisce l'agente. Con
`--check` si ferma dopo il build (dry-run: nessun loop bloccante, nessuna rete,
nessun device) — utile per validare un config e in CI/test. Senza `--check`
avvia il loop di reazione live (il loop di PERCEZIONE — cattura audio/schermo —
è il passo manuale documentato nel README: richiede permessi macOS). Il
provider LLM cloud (`grok`/`deepseek`) richiede `OPENROUTER_API_KEY`; il
provider locale `llamacpp` no — al suo posto fa un health-check del llama-server
avviato a mano.

Un config mancante o invalido produce un errore CHIARO su stderr e un exit code
!= 0 (riusa `ConfigError`).

Sottocomando `minnarone validate-prompts [--prompts-dir DIR | --config FILE]`:
valida TUTTI i prompt-set (original-chat + summarizer) — default impacchettati
più eventuale override — senza costruire l'agente. OK → exit 0 con riepilogo;
problemi → una riga per file rotto su stderr ed exit != 0.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

import yaml

from .app import build_agent
from .config import Config, ConfigError
from .dotenv import (
    load_dotenv_file as load_dotenv_file,
)
from .dotenv import (
    load_env_files as _load_env_files,
)
from .live_tui import (
    LiveTuiDependencyError,
    ensure_live_tui_available,
    run_live_tui,
)
from .llamacpp import LlamaCppServerNotReady, ensure_llamacpp_ready
from .output_sink import MinnaroneOutputStream
from .prompt_source import (
    DEFAULT_PROMPTS_PKG,
    ORIGINAL_CHAT_SET,
    SUMMARIZER_SET,
    PromptError,
    PromptSet,
    PromptSetSpec,
    load_prompt_set,
    load_summarizer_prompt_set,
)
from .replay import run_replay_tui
from .run_artifacts import DEFAULT_RUNS_ROOT, RunSession, create_run_session
from .twitch_auth import TwitchTokenValidationError
from .twitch_stream import TwitchStreamRuntimeError


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="minnarone",
        description="Avvia l'agente Minnarone da un file di configurazione.",
        epilog=(
            "Sottocomando: `minnarone validate-prompts "
            "[--prompts-dir DIR | --config FILE]` valida i prompt-set "
            "senza avviare l'app."
        ),
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


# --- sottocomando validate-prompts -----------------------------------------

# I set validati dal sottocomando: gli STESSI contratti usati dall'app.
_PROMPT_SETS_TO_VALIDATE: tuple[tuple[str, PromptSetSpec], ...] = (
    ("original-chat", ORIGINAL_CHAT_SET),
    ("summarizer", SUMMARIZER_SET),
)


def _parse_validate_prompts_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="minnarone validate-prompts",
        description=(
            "Valida i prompt-set (original-chat + summarizer): default "
            "impacchettati più eventuale directory di override."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--prompts-dir",
        metavar="DIR",
        help="directory di override dei prompt (come `prompts_dir` in config)",
    )
    group.add_argument(
        "--config",
        metavar="FILE",
        help="config YAML da cui leggere `prompts_dir`",
    )
    return parser.parse_args(list(argv))


def _prompts_dir_from_config(config_path: str) -> str | None:
    """Legge SOLO `prompts_dir` dal config YAML (percorso leggero).

    Di proposito NON usa `Config.load`: quel percorso valida l'INTERO config
    (provider, twitch, capture, ...) mentre qui serve solo la directory dei
    prompt. La risoluzione relativa alla dir del config rispecchia
    `Config._with_config_relative_memory_paths`.
    """
    p = Path(config_path)
    if not p.is_file():
        raise ConfigError(f"file di config non trovato: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"config illeggibile: {p}: {exc}") from exc
    if data is None:
        raise ConfigError(f"file di config vuoto: {p}")
    if not isinstance(data, dict):
        raise ConfigError("la radice del file di config deve essere una mappa")
    prompts_dir = data.get("prompts_dir")
    if prompts_dir is None:
        return None
    if not isinstance(prompts_dir, str) or not prompts_dir:
        raise ConfigError("prompts_dir deve essere una stringa non vuota")
    path = Path(prompts_dir)
    if not path.is_absolute():
        path = p.resolve().parent / path
    return str(path)


def _validate_prompts_main(argv: Sequence[str]) -> int:
    """Esegue `validate-prompts`. Ritorna l'exit code (0 = tutti i set validi)."""
    args = _parse_validate_prompts_args(argv)
    try:
        prompts_dir = (
            _prompts_dir_from_config(args.config)
            if args.config is not None
            else args.prompts_dir
        )
    except ConfigError as exc:
        print(f"errore di config: {exc}", file=sys.stderr)
        return 2

    override_dir = Path(prompts_dir) if prompts_dir else None
    problems: list[str] = []
    checked: list[tuple[str, str, str]] = []  # (set, file, origine)
    for set_name, set_spec in _PROMPT_SETS_TO_VALIDATE:
        for spec in set_spec.specs:
            origin = (
                "override"
                if override_dir is not None and (override_dir / spec.filename).is_file()
                else "default"
            )
            try:
                # PromptSet mono-file: stessa lettura+validazione del loader
                # reale ma per-file, così si riportano TUTTI i file rotti (la
                # validazione DENTRO un file resta fail-fast: primo problema).
                PromptSet(
                    PromptSetSpec(specs=(spec,)),
                    default_pkg=DEFAULT_PROMPTS_PKG,
                    override_dir=override_dir,
                )
            except PromptError as exc:
                problems.append(f"errore prompt [{set_name}]: {exc}")
            else:
                checked.append((set_name, spec.filename, origin))

    if not problems:
        # Conferma di parità col percorso reale dell'app: i factory caricano i
        # set COMPLETI (oggi equivale al giro per-file, ma resta il contratto
        # che l'avvio dell'app eserciterà davvero).
        try:
            load_prompt_set(prompts_dir)
            load_summarizer_prompt_set(prompts_dir)
        except PromptError as exc:
            problems.append(f"errore prompt: {exc}")

    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        label = "problema" if len(problems) == 1 else "problemi"
        print(
            f"validazione fallita: {len(problems)} {label}.",
            file=sys.stderr,
        )
        return 1

    where = (
        f"override: {override_dir}" if override_dir else "solo default impacchettati"
    )
    print(f"ok: {len(checked)} file di prompt validati ({where})")
    for set_name, filename, origin in checked:
        print(f"  [{set_name}] {filename}: {origin}")
    # Decisione FU-02 (niente strict-set bloccante): il fallback per-file resta,
    # ma un override PARZIALE va reso visibile — un set inglese a metà (corpi
    # override + resto default italiano) è legittimo solo se intenzionale.
    n_override = sum(1 for _, _, origin in checked if origin == "override")
    n_default = len(checked) - n_override
    if override_dir is not None and 0 < n_override < len(checked):
        print(
            f"nota: override parziale — {n_override} file da override, "
            f"{n_default} dal default impacchettato (possibile mix di lingue: "
            "verifica che sia voluto)"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Punto d'ingresso CLI. Ritorna l'exit code (0 = ok)."""
    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Dispatch del sottocomando PRIMA del parser principale: il parser storico
    # ha un positional `config` e i due non convivono bene in argparse.
    if raw_args and raw_args[0] == "validate-prompts":
        return _validate_prompts_main(raw_args[1:])

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

    # Health-check del llama-server locale SOLO sul percorso live: `--check`
    # resta un dry-run senza rete. Il server è avviato a mano dall'utente,
    # quindi un server assente/in caricamento è un errore azionabile, non un
    # loop che parte e salta tutti i turni.
    try:
        ensure_llamacpp_ready(config)
    except LlamaCppServerNotReady as exc:
        # Come il percorso di fallimento di build_agent (sopra): un run_session
        # già creato (--tui) va marcato completato, altrimenti resta 'attivo' su
        # disco e la retention non lo pota mai (orfano a ogni avvio fallito).
        if run_session is not None:
            with suppress(Exception):
                run_session.mark_completed()
        print(f"errore llama-server: {exc}", file=sys.stderr)
        return 1

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
    except TwitchTokenValidationError as exc:
        print(f"errore credenziali Twitch: {exc}", file=sys.stderr)
        return 1
    except LiveTuiDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("arresto richiesto.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
