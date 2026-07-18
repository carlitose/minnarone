# SPIKE — Esternalizzazione dei prompt (ticket 02)

**QUESTO È CODICE THROWAWAY.** Non è cablato nella produzione, non tocca
`prompt.py`/`summarizer.py` e non sposta le regole di sicurezza. Serve solo a
**provare il contratto di prompt-source** deciso nel ticket 02 prima di
scrivere il loader reale (ticket 03).

## Cosa prova

1. **Formato**: markdown-only. Un prompt-set = una directory. Un `.md` per
   prompt di prosa; i set "a chiavi" (le 6 situazioni) sono un unico `.md` con
   sezioni `## <chiave>` parsate in un dict.
2. **Templating**: sostituzione sicura `{{nome}}` (doppia graffa). Le graffe
   singole letterali sopravvivono; il valore sostituito NON viene ri-scansionato
   (niente injection). `{language}` → placeholder `{{language}}` risolto dal
   loader dal codice lingua di config.
3. **Packaging + override**: default impacchettati come sotto-package
   (`default_prompts/`, letto via `importlib.resources`) + directory di override
   da config (`prompts_dir`). Precedenza per-file: override se il file esiste lì,
   altrimenti il default impacchettato.
4. **Validazione**: fail-fast su file mancante / placeholder mancante o ignoto /
   token di controllo mancante (`#end_conv`, `#nothing`, `RE:`, `MSG:`) /
   contenuto vuoto. Mai vuoto silenzioso per contenuto obbligatorio.
5. **Multi-lingua**: il set inglese (`override_en/`) è servito solo puntandoci
   `prompts_dir`. Stesso codice, nessun motore i18n.

## Come eseguire la demo

```bash
uv run pytest spike/prompt_externalization/test_spike.py -v
# oppure lo script dimostrativo:
uv run python spike/prompt_externalization/demo.py
```

## Layout

```
spike/prompt_externalization/
├── __init__.py
├── loader.py               # il loader spike (PromptSet + templating + validazione)
├── demo.py                 # script dimostrativo end-to-end
├── test_spike.py           # pytest: 5 scenari (default/override/render/validazione/lingua)
├── default_prompts/        # SET DEFAULT (italiano) — package, letto via importlib.resources
│   ├── __init__.py
│   ├── rules.md            # prosa: persona/regole, {{channel}} + {{language}}
│   ├── situations.md       # a chiavi: 6 varianti ## <source>_<kind>
│   └── format.md           # contratto RE/MSG (#end_conv)
├── override_en/            # SET INGLESE completo (override via path) — prova multi-lingua
│   ├── rules.md
│   ├── situations.md
│   └── format.md
├── override_partial/       # override parziale: solo rules.md (prova precedenza per-file)
│   └── rules.md
└── broken_set/             # set rotto (prova fail-fast della validazione)
    ├── rules.md            # manca {{channel}}
    ├── situations.md       # manca #end_conv
    └── format.md
```
