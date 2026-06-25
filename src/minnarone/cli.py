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

from .app import build_agent
from .config import Config, ConfigError


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="minnarone",
        description="Avvia l'agente Minnarone da un file di configurazione.",
    )
    parser.add_argument("config", help="percorso del file di config YAML")
    parser.add_argument(
        "--check",
        action="store_true",
        help="valida il config e costruisci l'agente senza avviare il loop",
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    """Punto d'ingresso CLI. Ritorna l'exit code (0 = ok)."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw_args)

    try:
        config = Config.load(args.config)
        agent = build_agent(config)
    except ConfigError as exc:
        print(f"errore di config: {exc}", file=sys.stderr)
        return 2

    if args.check:
        print(
            f"ok: agente '{config.agent_name}' costruito "
            f"(mode={config.mode.value}, provider={config.llm_provider})"
        )
        return 0

    # Avvio del loop di reazione live. La cattura di percezione (audio/schermo)
    # è il passo manuale documentato: richiede device e permessi macOS.
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("arresto richiesto.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
