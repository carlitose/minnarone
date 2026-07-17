"""Preview del prompt di reazione con un prompt-set scelto (default o override).

Script di supporto della skill `.claude/skills/prompts/` (modalita' TRY).

Uso (dalla radice del repo):

    uv run python .claude/skills/prompts/preview_prompt.py [PROMPTS_DIR]

Senza argomento usa SOLO i default impacchettati (`src/minnarone/prompts/`).
Con PROMPTS_DIR applica la precedenza per-file: i file presenti nella dir
vincono, il resto viene dal default — lo stesso identico percorso di
`prompts_dir` in config. Fail-fast: se il set e' rotto, `load_prompt_set`
solleva `PromptError` PRIMA di costruire il builder (stesso comportamento
dell'avvio dell'app).
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
