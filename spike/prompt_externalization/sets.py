"""Contratto concreto del prompt-set "original-chat" (i 2 prompt rappresentativi).

Definisce QUALI file il set deve contenere e i loro vincoli. Nel loader reale
(ticket 03) questo diventerà la definizione del set original-chat completo.
"""

from __future__ import annotations

from .loader import PromptSetSpec, PromptSpec

# I 6 trigger (source × kind) provati dallo spike.
SITUATION_KEYS = frozenset(
    {
        "idle",
        "chat_mention",
        "chat_continuation",
        "audio_mention",
        "audio_continuation",
        "fallback",
    }
)

ORIGINAL_CHAT_SET = PromptSetSpec(
    specs=(
        # PROSA: persona/regole. Canale e lingua sono placeholder del loader.
        PromptSpec(
            filename="rules.md",
            allowed_placeholders=frozenset({"channel", "language"}),
            required_placeholders=frozenset({"channel"}),
        ),
        # A CHIAVI: le 6 situazioni. #end_conv deve sopravvivere; le sezioni
        # citano ancore strutturali ([CONVERSAZIONE RECENTE], ...) cablate.
        PromptSpec(
            filename="situations.md",
            allowed_placeholders=frozenset({"user", "mention", "reason"}),
            required_tokens=("#end_conv",),
            keyed=True,
            required_keys=SITUATION_KEYS,
        ),
        # Contratto RE/MSG: accoppiato al parser dell'output → token obbligatori.
        PromptSpec(
            filename="format.md",
            required_tokens=("RE:", "MSG:", "#end_conv"),
        ),
    )
)

DEFAULT_PKG = "prompt_externalization.default_prompts"
