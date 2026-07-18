# 03 — Task: header esternalizzati con riferimenti via placeholder

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un prompt-set in un'altra lingua può essere **completo**: anche gli header di
sezione (`[REGOLE]`, `[FORMATO RISPOSTA]`, `[SITUAZIONE]`, `[MEMORIA] (...)`,
`[I TUOI ULTIMI MESSAGGI]`, `[CONVERSAZIONE RECENTE]`, `[CHAT/PARLATO/SCHERMO
RECENTE]`, e `## RIASSUNTO`/`## CONVERSAZIONE RECENTE`/`## SITUAZIONE` degli
altri stili) vengono dai file, SENZA che i riferimenti incrociati possano
divergere.

**Meccanismo (dalla mappa)**: gli header vivono in un file a chiavi
(`headers.md`); i corpi che citano un header (es. le situazioni che citano
`[I TUOI ULTIMI MESSAGGI]` e `[MEMORIA]`) non scrivono più il nome letterale ma
un placeholder (`{{header_self_messages}}`, `{{header_memoria}}`) risolto dal
loader dagli STESSI valori usati per rendere gli header → coerenza garantita
per costruzione.

## Acceptance Criteria

- [x] `headers.md` (a chiavi, vincoli per-sezione dal ticket 02) con tutti gli
      header tunabili; default byte-identici agli attuali.
- [x] I corpi in `situations.md` citano gli header via placeholder; il render
      con i default è byte-identico a prima.
- [x] I marcatori di SICUREZZA (fence `DATI_PERCEPITI`, `| `, `[REGOLE]`?) —
      decidere quali header sono davvero tunabili e quali restano cablati per
      sicurezza; la decisione va scritta nel ticket. Il fence resta cablato
      SEMPRE.
- [x] `examples/prompts-en/` esteso a set completo (header inclusi) come prova
      dello swap totale di lingua.
- [x] Byte-invarianza del prefisso stabile coi default preservata.
- [x] Suite verde; test: header custom → riferimenti nei corpi aggiornati da
      soli; header mancante in `headers.md` → fail-fast.

## Blocked By

- Blocked by [02-task-per-section-validation.md](./02-task-per-section-validation.md)
  (i vincoli per chiave devono coprire `headers.md`).

## Frontier

È il pezzo col rischio di design più alto del gruppo (tocca byte-invarianza,
validazione e tutti gli stili): va per ultimo dei punti-prompt, su base stabile.

## Work Plan

1. Censire ogni header e ogni riferimento incrociato (grep su `prompt.py` +
   `prompts/*.md`).
2. RED: test che con `headers.md` custom il riferimento nel corpo segua l'header.
3. Introdurre `headers.md` + placeholder nei corpi; sostituire le ancore cablate
   con lookup dal set.
4. Estendere `examples/prompts-en/`; verificare swap completo.
5. Byte-invarianza + suite.

## Evidence to Capture

- Tabella header → chiave → chi lo cita.
- Render EN completo d'esempio.

## Out of Scope

- Esternalizzare fence/regole di sicurezza.
- Tradurre altri contenuti oltre l'esempio dimostrativo.

## Risultati

Completato 2026-07-18. Suite completa: **1170 passed, 22 skipped** (baseline
1156+22, +14 test nuovi); `ruff check src tests` → 0;
`validate-prompts --prompts-dir examples/prompts-en` → ok (9 file, nota di
override parziale attesa: 4 override / 5 default).

### Decisioni di design

- **`headers.md`** (a chiavi, in `ORIGINAL_CHAT_SET` con vincoli per-sezione
  del ticket 02): tutte le chiavi hanno un `KeySpec` → implicitamente
  obbligatorie, fail-fast se un override ne perde una. `{{channel}}` è ammesso
  E obbligatorio SOLO in `cosa_sai` (stessa regola di rules/intro: il canale
  non può sparire). Nessun `{{header_*}}` è ammesso dentro `headers.md`:
  niente ricorsione header→header.
- **Riferimenti via placeholder**: i corpi di `situations.md` citano gli header
  con `{{header_memoria}}`, `{{header_tuoi_ultimi_messaggi}}`,
  `{{header_conversazione_recente}}`; il render (`_original_chat_situation` →
  `_situation_header_refs`) li risolve da `headers.md`, la STESSA fonte che
  rende gli header di sezione → coerenza per costruzione, anche in set misti
  (headers custom + situations default). I tre riferimenti sono ammessi in
  TUTTE le 6 sezioni (il render li fornisce sempre); non sono obbligatori.
- **Suffisso spezzato**: `memoria` = `[MEMORIA]` (l'ancora citata dai corpi),
  `memoria_suffix` = `(com'e' andata la live e le conversazioni recenti)`;
  l'header di sezione compone `"{memoria} {memoria_suffix}"` — byte-identico
  al vecchio literal. Idem `[MEMORIA PERMANENTE]`: header (`memoria_permanente`)
  e riga di framing (`memoria_permanente_uso`) sono chiavi separate.
- **`ORIGINAL_CHAT_CONTEXT_SPECS`**: la costante module-level ora porta la
  CHIAVE (`chat_recente`, ...) non il testo; `_recent_context_block` è diventato
  metodo d'istanza e risolve il testo dal `PromptSet` del builder → gli header
  per-fonte si risolvono per-istanza, mai a import-time. Il Reactor usa solo
  `source`/`type`: invariato.
- **Stili non-original-chat**: `riassunto_std`/`conversazione_recente_std`/
  `situazione_std` sono le ETICHETTE; il prefisso markdown `## ` resta
  strutturale e composto in codice (`_std_header`) — un corpo che iniziasse con
  `## ` verrebbe comunque parsato come nuova sezione del file a chiavi. Gli
  header del prefisso stabile non-original-chat (`## REGOLE`, `## IDENTITÀ`,
  `## FATTI`) restano cablati (fuori dall'elenco del ticket).
- **Cosa resta cablato (sicurezza)**: il fence (`DATI_PERCEPITI`,
  `>>> FINE_DATI_PERCEPITI`, prefisso di riga `| `) SEMPRE; il testo delle
  regole anti-injection/disclosure SEMPRE — viene prepeso subito sotto il label
  `regole` qualunque sia il label. Solo il LABEL `[REGOLE]` è tunabile
  (test: `test_custom_headers_change_stable_prefix_sections` verifica l'ordine
  label → regole cablate).
- **Byte-invarianza**: con i default il render è byte-identico a prima (test
  esistenti su prefisso stabile e confini + nuovi
  `test_original_chat_headers_default_render_byte_identical` /
  `test_default_body_references_match_section_headers_byte_identical`).

### Tabella header → chiave → chi lo cita

| Header default | Chiave | Reso da | Citato da |
|---|---|---|---|
| `[REGOLE]` | `regole` | prefisso stabile original-chat | — |
| `[MEMORIA PERMANENTE] (informazioni...)` | `memoria_permanente` | prefisso stabile | — |
| `Usale SOLO se sensate...` | `memoria_permanente_uso` | prefisso stabile | — |
| `CHI SEI:` | `chi_sei` | prefisso stabile | — |
| `COSA SAI SU @{{channel}} (lo streamer):` | `cosa_sai` | prefisso stabile | — |
| `[FORMATO RISPOSTA]` | `formato_risposta` | prefisso stabile | — |
| `[MEMORIA]` (+ suffix) | `memoria` + `memoria_suffix` | summary header | `situations.md: streamer-mention` |
| `[I TUOI ULTIMI MESSAGGI]` | `tuoi_ultimi_messaggi` | self-messages header | `situations.md: streamer-mention, streamer-continuation` |
| `[CONVERSAZIONE RECENTE]` | `conversazione_recente` | recent header | `situations.md: chat-continuation` |
| `[SITUAZIONE]` | `situazione` | situation header | — |
| `[CHAT/PARLATO/SCHERMO RECENTE]` | `chat_recente`/`parlato_recente`/`schermo_recente` | recent per-fonte (`ORIGINAL_CHAT_CONTEXT_SPECS`) | — |
| `## RIASSUNTO` / `## CONVERSAZIONE RECENTE` / `## SITUAZIONE` | `riassunto_std`/`conversazione_recente_std`/`situazione_std` | stili default/operator/meeting/suggester (`## ` composto) | — |

### Render EN d'esempio (set `examples/prompts-en`, ora completo di header)

Estratto (streamer-mention, summary+self-messages, canale `pepper`):

```
[RULES]
...regole di sicurezza cablate + rules.md EN...
[PERMANENT MEMORY] (background context about you and the streamer)
...
[MEMORY] (how the stream and recent conversations have been going)
[YOUR LAST MESSAGES]
[RECENT CONVERSATION]
[RECENT CHAT] / [RECENT SPEECH] / [RECENT SCREEN]
[SITUATION]
The streamer addressed YOU (...). Reply naturally, keeping the thread of what
you said to each other ([YOUR LAST MESSAGES] and [MEMORY]).
```

Il riferimento nel corpo segue l'header per costruzione: nessun residuo
italiano negli header/riferimenti (restano in italiano solo i file NON
sovrascritti dall'esempio: format.md e i per-stile, segnalati dalla nota di
override parziale).
