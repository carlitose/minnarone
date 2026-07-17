# 05 — Task: `test_vlm` skip-if-missing + comando validate-prompts

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Due igieni piccole e indipendenti fra loro, raggruppate per dimensione:

**(a) vlm**: i 5 test di `tests/test_vlm.py` si **skippano** (non falliscono)
quando l'extra `vlm`/`transformers` non è installato. Oggi non usano
`pytest.importorskip` → una fresh install fallisce la suite senza colpa.

**(b) validate-prompts**: esiste un **entry-point invocabile** per validare un
prompt-set senza avviare tutta l'app (oggi la validazione fail-fast scatta solo
costruendo i PromptSet dentro `app.py`). È il prerequisito tecnico della skill
del ticket 06.

## Acceptance Criteria

- [ ] `test_vlm.py` usa `pytest.importorskip("transformers")` (o marker
      equivalente coerente col repo): senza extra → SKIP, con extra → run.
- [ ] La suite completa gira verde su ambiente base SENZA `--ignore=tests/test_vlm.py`.
- [ ] Nuovo comando `minnarone validate-prompts [--prompts-dir DIR | --config FILE]`
      (naming coerente con la CLI esistente in `cli.py`): carica TUTTI i set
      (original-chat + summarizer) coi default impacchettati + eventuale
      override e riporta OK o gli errori `PromptError` con exit code ≠ 0.
- [ ] Output leggibile sia da umano che da agente (una riga per problema:
      file, sezione, cosa manca).
- [ ] Test del comando: set valido → 0; set rotto → exit ≠ 0 con messaggi.
- [ ] Docs: una riga in README (sezione prompt) su come validare un override.

## Blocked By

- None — può partire subito.

## Frontier

(a) toglie il rumore che ha accompagnato tutti i run finora; (b) è il mattone su
cui poggia la skill (06).

## Work Plan

1. RED (a): girare la suite base e osservare i 5 fail; aggiungere importorskip;
   verificare 5 SKIP.
2. RED (b): test del nuovo comando su set rotto (exit ≠ 0, messaggi).
3. Implementare il sottocomando in `cli.py` riusando `load_prompt_set` /
   `load_summarizer_prompt_set`.
4. Docs + suite completa (ora senza ignore).

## Evidence to Capture

- Output suite prima/dopo (fail → skip).
- Trascrizione del comando su set valido e rotto.

## Out of Scope

- La skill vera e propria (ticket 06).
- Installare l'extra vlm in dev.
