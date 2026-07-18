# 02 — Task: validazione per-sezione / strict-set mode

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un override malformato fallisce **all'avvio** con un messaggio chiaro, non a
runtime al primo trigger sfortunato. Oggi `required_tokens`/placeholder di un
file a chiavi (es. `situations.md`) sono validati sull'INTERO file: se un
override toglie `#end_conv` solo dalla sezione `streamer-mention`, l'avvio passa
e l'errore esplode live.

## Acceptance Criteria

- [x] `PromptSpec` (o estensione) permette vincoli **per chiave**: token di
      controllo richiesti e placeholder ammessi/richiesti per singola sezione
      (es. `#end_conv` richiesto in OGNI variante situazione che lo usa;
      `{{user}}`/`{{mention}}` ammessi solo nelle sezioni chat).
- [x] `situations.md` (e `summarizer.md` dove sensato) migrati ai vincoli
      per-sezione; i default passano invariati.
- [x] Un override con una sezione rotta (token mancante / placeholder estraneo)
      fallisce al load con `PromptError` che indica FILE e SEZIONE.
- [x] Messaggio d'errore utilizzabile da un agente/operatore (file, chiave,
      cosa manca).
- [x] Valutato (e deciso nel ticket) lo "strict-set mode": nessun fallback
      per-file quando `prompts_dir` è impostato, per evitare mix silenzioso di
      lingue con override parziali. Se adottato: opt-in documentato; se
      scartato: motivazione scritta. → **Scartato**, vedi Risultati.
- [x] Suite verde; test nuovi per ogni modo di rottura.

## Blocked By

- None — può partire subito.

## Frontier

Chiude la maglia larga della rete di sicurezza del loader; prerequisito logico
del ticket 03 (headers.md avrà anch'esso vincoli per chiave).

## Work Plan

1. RED: test che un `situations.md` senza `#end_conv` in UNA sezione fallisca al
   load nominando file+sezione.
2. Estendere la validazione in `prompt_source.py` (vincoli per chiave).
3. Migrare le spec esistenti; decidere e (eventualmente) implementare
   strict-set.
4. Aggiornare docs (README sezione override).

## Evidence to Capture

- Diff `prompt_source.py` + spec; messaggi d'errore d'esempio.
- Decisione strict-set registrata.

## Out of Scope

- Header (ticket 03) — ma il meccanismo qui costruito deve poterli coprire.

## Risultati

Fatto 2026-07-17, TDD (RED per ogni modo di rottura → GREEN). Suite completa:
**1156 passed, 22 skipped**; `ruff check src tests` pulito.

### Meccanismo (`prompt_source.py`)

- Nuovo dataclass frozen `KeySpec` (`allowed_placeholders`,
  `required_placeholders`, `required_tokens`) — i vincoli di UNA sezione
  `## <chiave>`.
- `PromptSpec.key_specs: Mapping[str, KeySpec]` — vincoli per-sezione dei file
  a-chiavi. Una chiave con `KeySpec` è **implicitamente obbligatoria**. I file
  a-chiavi si validano PRIMA per-sezione (`_validate_key_specs`, iterazione
  ordinata → errori deterministici), poi coi vincoli file-wide, che restano per
  i file di prosa (`format.md` invariato) e per il testo fuori sezione; il
  check file-wide dei placeholder ammette l'unione dei `key_specs` (whitelist
  per-sezione = unica fonte di verità, niente doppia dichiarazione).
- Messaggi con FILE e SEZIONE, es.:
  `token di controllo mancante in 'situations.md' sezione 'chat-mention':
  '#end_conv' (il parser dell'output ne dipende)`.

### Migrazione dei contratti reali (ground truth dai render path)

- `SITUATIONS_SPEC` (da `prompt._original_chat_situation` + default):
  `idle` → nessun placeholder, richiede `#end_conv`; `chat-mention` /
  `chat-continuation` → ammessi `{{user}}`/`{{mention}}`, richiedono
  `#end_conv`; `streamer-continuation` → nessun placeholder, richiede
  `#end_conv`; `streamer-mention` e `generic` → **NON** richiedono `#end_conv`
  (il default impacchettato non lo contiene in quelle sezioni: lì la risposta è
  sempre attesa); `generic` ammette solo `{{reason}}`. Il `required_tokens`
  file-wide di `#end_conv` è stato rimosso: subsunto dai vincoli per-sezione.
- `SUMMARIZER_SPEC`: `KeySpec()` vuoto per tutte le 8 chiavi — il summarizer
  non fornisce mai valori di render e non ha token di parser: nessun
  placeholder ammesso in nessuna sezione, con errore che nomina la sezione.
- `minnarone validate-prompts` (FU-05) funziona invariato e riporta ora gli
  errori per-sezione (stesso `_validate` via PromptSet mono-file).

### Decisione strict-set mode: **SCARTATO** (niente modalità bloccante)

Motivazione:

1. Il fallback per-file è una feature documentata e voluta ("override just one
   file"): il caso d'uso principe è ritoccare `situations.md` lasciando il
   resto ai default. Un blocco (anche opt-in) punirebbe il caso comune per
   proteggere quello raro.
2. Il rischio reale (set inglese "a metà": corpi override + resto default
   italiano) è un problema di **visibilità**, non di correttezza: nessun
   crash, nessuna violazione di contratto. La risposta proporzionata è rendere
   il mix visibile, non vietarlo.
3. Copertura adottata: `validate-prompts` elenca già l'origine per file
   (`override`/`default`); aggiunta una riga esplicita quando l'override è
   parziale — `nota: override parziale — N file da override, M dal default
   impacchettato (possibile mix di lingue: verifica che sia voluto)` — assente
   quando l'override è completo o assente. Un flag bloccante resta possibile
   in futuro come opt-in della CLI, se l'esperienza lo richiedesse.

### Demo (transcript)

`situations.md` di override con `#end_conv` mancante SOLO in `chat-mention`:

```
$ minnarone validate-prompts --prompts-dir <dir>
errore prompt [original-chat]: token di controllo mancante in 'situations.md' sezione 'chat-mention': '#end_conv' (il parser dell'output ne dipende)
validazione fallita: 1 problema.
(exit 1)
```

Override parziale valido (solo `situations.md`):

```
ok: 8 file di prompt validati (override: <dir>)
  [original-chat] situations.md: override
  ... (gli altri 7: default)
nota: override parziale — 1 file da override, 7 dal default impacchettato (possibile mix di lingue: verifica che sia voluto)
(exit 0)
```

### File toccati

- `src/minnarone/prompt_source.py` — `KeySpec`, `PromptSpec.key_specs`,
  `_validate_key_specs`, migrazione `SITUATIONS_SPEC`/`SUMMARIZER_SPEC`.
- `src/minnarone/cli.py` — nota "override parziale" nel riepilogo OK.
- `tests/test_prompt_source.py` — 11 test nuovi (meccanismo + contratti reali).
- `tests/test_cli.py` — 3 test nuovi (nota parziale, no-nota su set completo,
  errore CLI con file+sezione).
- `README.md` — vincoli per-sezione di `situations.md`, fail-fast per sezione,
  nota override parziale.

### Nota per il ticket 03

Il meccanismo copre `headers.md` senza modifiche: basta dichiarare
`key_specs={chiave: KeySpec(...)}` nel suo `PromptSpec`.
