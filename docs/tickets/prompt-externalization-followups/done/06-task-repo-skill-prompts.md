# 06 — Task: skill di repo `prompts` per il code agent

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un code agent (Claude Code) che lavora su questo repo può gestire i prompt in
autonomia e in sicurezza tramite skill locali in `.claude/skills/`, senza dover
riscoprire ogni volta loader, vincoli e comandi. Copertura minima (assunzione
dalla mappa, da confermare in apertura ticket):

- **validate**: valida un set/override col comando del ticket 05 e riporta gli
  errori in forma azionabile.
- **edit**: flusso guidato di modifica — quali file esistono, quali placeholder
  e token NON vanno rimossi, modifica → `validate-prompts` → test mirati
  (`test_prompt_source.py`, `test_prompt_builder.py`, fresh-install) → diff.
- **try**: rende il prompt con un set (default o override) e lo mostra
  (es. via `PromptBuilder.build` con percezioni fake o lo smoke esistente),
  così l'agente vede l'effetto della modifica prima di committare.

## Acceptance Criteria

- [x] Skill(s) in `.claude/skills/` (una `prompts` con sottocomandi o 2-3
      separate — scelta motivata nel ticket) con frontmatter e descrizioni che
      le fanno scattare sulle richieste giuste ("cambia i prompt", "traduci il
      set", "valida il mio override", ...).
- [x] La skill di edit incorpora i vincoli non ovvi: token di controllo
      (`#end_conv`, `#nothing`, `RE:`, `MSG:`), placeholder richiesti
      (`{{channel}}`, `{{language}}`), sezioni richieste, confine di sicurezza
      (cosa NON è nei file e perché), byte-invarianza per i default.
- [x] Ogni skill usa comandi reali e verificati (validate-prompts del 05, pytest
      mirati, eventuale smoke `/run`), non pseudo-procedure.
- [x] Prova end-to-end documentata: un agente segue la skill per creare un
      override rotto → la skill lo porta a scoprire l'errore all'avvio e a
      correggerlo.
- [x] README (sezione contributor/agent) menziona le skill.

## Blocked By

- Blocked by [05-task-vlm-skip-and-validate-cli.md](./05-task-vlm-skip-and-validate-cli.md)
  (serve il comando di validazione).

## Frontier

Trasforma l'infrastruttura dei prompt in un flusso operabile da agenti: è il
"manuale eseguibile" che evita regressioni da editing manuale.

## Work Plan

1. Decidere la granularità (1 skill con modalità vs 2-3 skill) e scriverle.
2. Includere la mappa dei file/vincoli (generata dai `PromptSpec`, non duplicata
   a mano dove possibile).
3. Prova end-to-end con override rotto e correzione guidata.
4. README + eventuale nota in CLAUDE.md del repo.

## Evidence to Capture

- Trascrizione della prova end-to-end.
- Le skill stesse.

## Out of Scope

- Skill per aspetti non-prompt (build, deploy, ecc.).
- Automazioni via hook (solo skill invocabili).

## Risultati (2026-07-18)

### Cosa è stato consegnato

- `.claude/skills/prompts/SKILL.md` — UNA skill con tre modalità
  (validate / edit / try).
- `.claude/skills/prompts/preview_prompt.py` — script di supporto della
  modalità try (render del prompt completo con percezioni fake, default o
  override; fail-fast su set rotto).
- README.md + README.it.md: paragrafo contributor/agent nella sezione
  "Quality checks" che rimanda alla skill.

### Scelta di granularità: 1 skill con modalità, non 2-3 skill

Motivazione: i tre flussi condividono l'80% del contesto necessario (mappa dei
file, tabella dei vincoli, confine di sicurezza, byte-invarianza) — tre skill
separate lo avrebbero triplicato o costretto a rimandi incrociati fragili.
Inoltre i flussi si concatenano sempre nello stesso ordine (edit → validate →
try): una richiesta "cambia i prompt" ha comunque bisogno di tutte e tre le
modalità. Il frontmatter `description` porta tutte le frasi-trigger
("cambiare/modificare i prompt", "tradurre il set", "validare un override",
"vedere l'effetto di una modifica").

La tabella file/vincoli nella skill è un riassunto DERIVATO dai
`PromptSpec`/`KeySpec` di `src/minnarone/prompt_source.py`, con l'istruzione
esplicita che in caso di dubbio la fonte di verità è il codice (non si duplica
ogni dettaglio a mano).

### Comandi reali verificati (tutti eseguiti prima di scriverli nella skill)

- `uv run python -m minnarone validate-prompts` → exit 0,
  "ok: 9 file di prompt validati (solo default impacchettati)".
- `uv run python -m minnarone validate-prompts --prompts-dir examples/prompts-en`
  → exit 0 + nota di override parziale (4 override, 5 default).
- `uv run python .claude/skills/prompts/preview_prompt.py` (e con
  `examples/prompts-en`) → exit 0, stampa il prompt completo.
- `uv run python -m minnarone examples/llamacpp-local.example.yaml --check`
  → exit 0, "ok: agente 'minnarone' costruito (mode=public, provider=llamacpp)".
- pytest mirati (`test_prompt_source.py`, `test_prompt_builder.py`,
  `test_prompt_fresh_install.py`, `test_cli.py`) → 182 passed.

### Prova end-to-end (override rotto → scoperta all'avvio → fix)

Simulato il flusso prescritto dalla skill:

1. Creato un override in una dir temporanea copiando `situations.md` dal
   default e rimuovendo `#end_conv` dalla sola sezione `chat-mention`.
2. Step validate della skill:

   ```text
   $ uv run python -m minnarone validate-prompts --prompts-dir <tmp>/broken-override
   errore prompt [original-chat]: token di controllo mancante in 'situations.md' sezione 'chat-mention': '#end_conv' (il parser dell'output ne dipende)
   validazione fallita: 1 problema.
   (exit 1)
   ```

   Fallisce al load nominando FILE e SEZIONE, come richiesto dalla review
   della mappa ("deve fallire all'avvio con messaggio chiaro").
3. Fix guidato: ripristinato `#end_conv` nella sezione; ri-validato:

   ```text
   $ uv run python -m minnarone validate-prompts --prompts-dir <tmp>/broken-override
   ok: 9 file di prompt validati (override: <tmp>/broken-override)
     [original-chat] situations.md: override
     ... (gli altri 8: default)
   nota: override parziale — 1 file da override, 8 dal default impacchettato (possibile mix di lingue: verifica che sia voluto)
   (exit 0)
   ```

### Regressione

- `uv run --extra dev python -m pytest -q` → 1170 passed (baseline invariata).
- `uv run ruff check src tests` → pulito (nessun file src/ toccato).

### Note

- Nessuna nota aggiunta a un CLAUDE.md di repo: non esiste un CLAUDE.md di
  progetto in questo worktree e la skill è già auto-scoperta da Claude Code;
  il rimando per gli umani sta nei due README ("eventuale" nel work plan).
