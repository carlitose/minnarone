"""Script dimostrativo end-to-end dello spike (leggibile a occhio).

    uv run python spike/prompt_externalization/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompt_externalization.loader import PromptError, PromptSet, language_name
from prompt_externalization.sets import DEFAULT_PKG, ORIGINAL_CHAT_SET

_SPIKE_DIR = Path(__file__).resolve().parent


def _load(override: str | None = None) -> PromptSet:
    return PromptSet(
        ORIGINAL_CHAT_SET,
        default_pkg=DEFAULT_PKG,
        override_dir=str(_SPIKE_DIR / override) if override else None,
    )


def _hr(title: str) -> None:
    print(f"\n{'=' * 8} {title} {'=' * 8}")


def main() -> None:
    _hr("1. SET DEFAULT (italiano) via importlib.resources")
    ps = _load()
    print(ps.text("rules.md", channel="enkk", language=language_name("it")))
    print("[situazione chat_mention]")
    print(ps.section("situations.md", "chat_mention", user="mario", mention="@mario"))

    _hr("2. OVERRIDE PARZIALE (solo rules.md) — precedenza per-file")
    ps = _load("override_partial")
    print(ps.text("rules.md", channel="enkk", language=language_name("it")))
    print("[situations.md cade sul default:]")
    print(ps.section("situations.md", "idle"))

    _hr("3. SWAP LINGUA: prompts_dir -> override_en (inglese, gratis)")
    ps = _load("override_en")
    print(ps.text("rules.md", channel="enkk", language=language_name("en")))
    print("[situazione chat_continuation]")
    print(
        ps.section(
            "situations.md", "chat_continuation", user="mario", mention="@mario"
        )
    )

    _hr("4. VALIDAZIONE fail-fast (set rotto)")
    try:
        _load("broken_set")
    except PromptError as exc:
        print(f"PromptError (atteso): {exc}")


if __name__ == "__main__":
    main()
