# Original-chat prompt fidelity — riproduzione IDENTICA del Minnarone originale

## Type

Wayfinding spec

## Status

Active

## Destination

Rendere il prompt **original-chat** (`PromptBuilder`) e il **Summarizer**
**identici** al Minnarone originale di enkk come documentato negli screenshot
della sua doc Notion — stessa struttura, stessi header, stesso testo delle regole
e degli spazi dinamici, stesso formato riga.

**Unica differenza accettata:** il **fence anti-injection** (`DATI_PERCEPITI`)
resta (decisione operatore 2026-07-17). Il prompt sarà quindi identico
all'originale a meno di quella "recinzione" di sicurezza attorno al testo
percepito.

> Nota di scope: questa destinazione **sovrascrive** le decisioni del PRD
> [original-minnarone-chat-dry-run](../prds/original-minnarone-chat-dry-run.md)
> che avevano dichiarato la fedeltà pixel-perfect *Out of Scope* e alcune
> divergenze come intenzionali. Considerate frutto della fase autopilot e
> superate.

## Divergenze da chiudere (per l'identità)

- **A — Summarizer rolling + `[MEMORIA]` strutturata**: l'originale mantiene un
  riassunto *incrementale* (reinietta "Riassunto attuale: …", integra "Eventi
  recenti" raggruppati in **STREAMER / SCHERMO / CHAT**, chiude con "Aggiorna il
  riassunto") e lo rende nel prompt come `[MEMORIA]` con sotto-sezioni **STREAM /
  CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN CHAT**. Il codice fa un
  riassunto *from-scratch* piatto (`## EVENTI`).
- **B — Formato riga percezione**: originale `-23s <leo95nf>: KEKW` (timestamp
  relativo + `< >`); codice `leo95nf: KEKW`.
- **C — Formato messaggi propri**: originale `-277s tu: "..." (rispondevi a: ...)`
  sotto `[I TUOI ULTIMI MESSAGGI]`; codice `minnarone: <msg>` sotto
  `[TUOI MESSAGGI RECENTI]`.
- **D — Riferimenti di sezione**: il testo SITUAZIONE del codice cita
  `[CONVERSAZIONE RECENTE]`; l'originale cita `[I TUOI ULTIMI MESSAGGI]` e
  `[MEMORIA]`.
- **F — Header e layout**: l'originale apre con `====== SITUAZIONE ATTUALE ======`
  e `Ti trovi nel canale di enkk`, assenti nel codice; ordine/etichette delle
  sezioni da riconciliare al layout originale.

## Decisions So Far

- **Destinazione = identico all'originale** — operatore, 2026-07-17. Le decisioni
  contrarie del PRD padre (pixel-perfect OOS, divergenze intenzionali) sono
  superate.
- **Fence `DATI_PERCEPITI` = TENUTO** — operatore, 2026-07-17. Trade-off
  identità vs sicurezza risolto a favore della sicurezza: la recinzione anti
  prompt-injection resta l'unica differenza deliberata dall'originale. Il fence
  NON è più una divergenza da chiudere.
- **Blocchi già coincidenti** (verificati byte-identici): `[FORMATO RISPOSTA]`,
  `[SITUAZIONE]` idle, frase-core `[SITUAZIONE]` chat. Non reintrodurre delta lì.
- **Trascrizione fatta (ticket 01, 2026-07-17)**: testo di riferimento in
  [original-chat-prompt-reference.md](./original-chat-prompt-reference.md).
- **Nodo timestamp = RISOLTO**: `Perception.ts` esiste; passare
  `now = self._senser.now()` da `Reactor.run_once` a `build(..., now=now)`;
  relativo `-{int(now - p.ts)}s`. Timestamp solo in sezione dinamica → prefisso
  stabile invariante.
- **Nodo `format_perception_line` = RISOLTO: separare i renderer**. Recent-context
  prende `(perception, now)` → `-<N>s <user>: testo`; il Summarizer ha il proprio
  raggruppamento per fonte.

## Not Yet Specified

- **Incognite residue di trascrizione** (screenshot parziali) — elencate in
  [original-chat-prompt-reference.md](./original-chat-prompt-reference.md):
  posizione del prefisso stabile, wording esatto del sintetizzatore, etichette
  parentetiche delle sezioni, chiusura esatta di "streamer→TE", esistenza di
  `[PARLATO/SCHERMO RECENTE]`, formato riga chat nell'input del summarizer.
  Chiudibili con screenshot a piena risoluzione o conferma operatore.
- **Provenienza del "(rispondevi a: …)"** (C): il Reactor passa i messaggi propri
  come `Sequence[str]` nudi; serve arricchirli con reason/target (ticket 04).
- **A come mini-PRD**: la memoria rolling strutturata è quasi una feature a sé —
  se A merita un `to-spec`/PRD dedicato o sta in un ticket task (decisione al
  Next Review).

## Out of Scope

- **Rimuovere il fence** — deciso di tenerlo (vedi Decisions So Far).
- Ciò che era già Out of Scope nel PRD padre e resta fuori: invio pubblico Twitch,
  auto-memoria/auto-facts, modifiche ad ASR/VLM/diarization/perception queue.
- Toccare i blocchi già coincidenti (`[FORMATO RISPOSTA]`, `[SITUAZIONE]` idle).

## Frontier / Blocking Edges

- ✅ **Edge #1 — trascrizione**: CHIUSO dal ticket 01 (riferimento salvato).
  Restano incognite di dettaglio non bloccanti (vedi Not Yet Specified).
- ✅ **Edge #2 — nodi architetturali**: CHIUSI dal ticket 01 (timestamp via
  `senser.now()`; renderer separati). Da applicare in 03.
- **Edge #3 (nuovo frontier): implementazione.** I ticket 02-06 sono sbloccati.
  Ordine consigliato: 02 (D, basso rischio) → 03 (B, meccanismo timestamp) →
  04 (C) → 05 (F) → 06 (A). Attenzione a coordinare 02/05 sui nomi-sezione e
  05/06 sulla collocazione di `[MEMORIA]`.

## Ticket Plan

| # | Tipo | Titolo | Output atteso |
|---|------|--------|---------------|
| 01 | research | Trascrizione fedele di TUTTI gli screenshot + nodi architetturali | Testo esatto per ogni sezione + verdetto shared-formatter/timestamp |
| 02 | task | D — Allineare i riferimenti di sezione in SITUAZIONE | Testo SITUAZIONE con i nomi-sezione dell'originale |
| 03 | task | B — Formato riga percezione (`-23s <user>:`) | Renderer con timestamp+brackets + test |
| 04 | task | C — Formato messaggi propri + header | `[I TUOI ULTIMI MESSAGGI]` con `-Ns tu: "..." (rispondevi a: ...)` |
| 05 | task | F — Header `SITUAZIONE ATTUALE` + layout sezioni | Apertura e ordine sezioni identici all'originale |
| 06 | task | A — Summarizer rolling + `[MEMORIA]` strutturata | Riassunto incrementale STREAM/CONVERSAZIONI |

Dipendenze: 01 blocca 02-06. 04 (C) dipende da 03 (B). 06 (A) consuma da 03 (B)
la resa delle righe evento.

## Next Review

Dopo 01: (1) ricalibrare i task col testo esatto trascritto; (2) confermare il
verdetto su `format_perception_line` (condivisa vs separata) prima di aprire 03;
(3) decidere se A resta task o diventa spec dedicato.
