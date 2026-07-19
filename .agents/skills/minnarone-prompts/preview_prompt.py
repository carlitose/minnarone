"""Preview the reaction prompt with a chosen prompt-set (default or override).

Support script for the `minnarone-prompts` skill (TRY mode).

Usage (from the repo root):

    uv run python .claude/skills/minnarone-prompts/preview_prompt.py [PROMPTS_DIR]

With no argument it uses ONLY the packaged defaults (`src/minnarone/prompts/`).
With PROMPTS_DIR it applies per-file precedence: files present in the dir win,
the rest come from the default — the exact same path as `prompts_dir` in config.
Fail-fast: if the set is broken, `load_prompt_set` raises `PromptError` BEFORE
building the builder (same behavior as app startup).
"""

import sys

from minnarone.memory import MemoryBlocks
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.prompt_source import load_prompt_set
from minnarone.senser import Trigger

prompts_dir = sys.argv[1] if len(sys.argv) > 1 else None
prompt_set = load_prompt_set(prompts_dir)

builder = PromptBuilder(
    MemoryBlocks(soul="Sono Minnarone.", facts="enkk ama il trap."),
    prompt_set=prompt_set,
    channel="canale-di-prova",
)
recent = [
    Perception(ts=1.0, source=Source.CHAT, type="msg", text="ciao", speaker="tizio"),
    Perception(
        ts=2.0,
        source=Source.AUDIO,
        type="speech",
        text="oggi ranked",
        speaker="streamer",
    ),
]
trigger = Trigger(
    reason="mention",
    perception=Perception(
        ts=3.0, source=Source.CHAT, type="msg", text="ehi minnarone", speaker="tizio"
    ),
)
print(builder.build(recent=recent, trigger=trigger, summary="Riassunto fake."))
