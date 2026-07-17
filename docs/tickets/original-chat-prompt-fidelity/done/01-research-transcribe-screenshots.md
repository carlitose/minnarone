# 01 — Research: trascrizione fedele degli screenshot + nodi architetturali

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

research

## Outcome

Il **testo esatto e integrale** di ogni sezione del prompt originale di enkk (dai
4 screenshot della doc Notion + eventuali frame aggiuntivi del video), trascritto
alla lettera, così che i ticket 02-06 abbiano un target verificato invece di
stringhe inventate. In più, la risoluzione dei due nodi architetturali che
bloccano l'implementazione: (1) da dove arriva il riferimento temporale per i
timestamp relativi `-Ns`; (2) se `format_perception_line` resta condivisa fra
`PromptBuilder` e `Summarizer` o si separano i renderer.

## Acceptance Criteria

- [ ] Trascrizione fedele, sezione per sezione, di: `====== SITUAZIONE ATTUALE ======`,
      `[MEMORIA]` (con STREAM / CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN
      CHAT), `[CHAT RECENTE]`, `[I TUOI ULTIMI MESSAGGI]`, `[FORMATO RISPOSTA]`,
      `[SITUAZIONE]` (tutte le varianti trigger), e il prompt del sintetizzatore.
- [ ] Formato riga percezione documentato esattamente: prefisso `-Ns`, uso di
      `< >`, ordine dei campi (es. `-23s <leo95nf>: KEKW`).
- [ ] Formato messaggi propri documentato: `-Ns tu: "..." (rispondevi a: ...)`.
- [ ] Verificato se l'originale ha una qualunque forma di protezione anti-injection
      (probabile: no) — annotato per confermare che il fence è un'aggiunta del repo.
- [ ] Nodo timestamp risolto: dove/come iniettare un "now" nel renderer senza
      intaccare la byte-invarianza del prefisso stabile.
- [ ] Nodo `format_perception_line` risolto: condivisa vs renderer separati, con
      motivazione.
- [ ] Parti illeggibili/mancanti degli screenshot elencate esplicitamente (cosa
      NON sappiamo), invece di riempirle a indovinare.
- [ ] Conclusioni ripiegate nel wayfinder (`Decisions So Far` / `Not Yet Specified`).

## Blocked By

- None — può partire subito.

## Frontier

È il bordo che blocca tutto: senza il testo esatto dell'originale, ogni task a
valle rischia di introdurre stringhe inventate, che è l'opposto dell'obiettivo
"identico".

## Work Plan

1. Rileggere i 4 screenshot forniti e trascrivere alla lettera ogni sezione
   visibile, marcando i punti tagliati/illeggibili.
2. Confrontare con lo stato attuale del codice (`prompt.py`, `summarizer.py`,
   `perception.py`) per isolare esattamente le differenze testuali.
3. Decidere il meccanismo del "now": candidato = parametro opzionale passato a
   `build()`/al formatter, usato solo nella sezione dinamica.
4. Decidere il destino di `format_perception_line`: se il summarizer vuole un
   formato diverso dalla recent-context, proporre due renderer distinti con una
   base comune.
5. Aggiornare il wayfinder con testo di riferimento e verdetti.

## Evidence to Capture

- Blocco di testo trascritto per ogni sezione (in un file di appoggio o in coda a
  questo ticket).
- Righe `prompt.py`/`summarizer.py`/`perception.py` che cambieranno, con numero.
- Elenco esplicito delle incognite residue (parti non leggibili).

## Out of Scope

- Implementare qualsiasi modifica al codice (è dei ticket 02-06).
- Rimuovere il fence (deciso: si tiene).

---

## Risultati (2026-07-17)

### Trascrizione

Trascrizione fedele (per sezione, con marcatura confidenza e struttura-vs-esempio)
salvata in
[original-chat-prompt-reference.md](../../specs/original-chat-prompt-reference.md).

Sintesi divergenze confermate dal confronto con il codice:

- **A** — Summarizer: originale rolling con `Riassunto attuale:` + `Eventi
  recenti:` raggruppati STREAMER/SCHERMO/CHAT + `Aggiorna il riassunto`; reso sotto
  `[MEMORIA]` (STREAM / CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN CHAT). Il
  codice fa from-scratch piatto (`summarizer.py:34-69`).
- **B** — riga percezione `-<N>s <user>: testo`; codice `user: testo`
  (`perception.py:127`).
- **C** — messaggi propri `-<N>s tu: "..." (rispondevi a: ...)` sotto `[I TUOI
  ULTIMI MESSAGGI]`; codice `minnarone: <msg>` sotto `[TUOI MESSAGGI RECENTI]`
  (`prompt.py:546-558`).
- **D** — riferimenti di sezione: continuation streamer cita `[I TUOI ULTIMI
  MESSAGGI]` (codice: `[CONVERSAZIONE RECENTE]`, `prompt.py:459-461`); streamer→TE
  cita `([ULTIMI MESSAGGI] e [MEMORIA])` (codice: nessun riferimento,
  `prompt.py:466-471`).
- **F** — apertura `====== SITUAZIONE ATTUALE ======` + `Ti trovi nel canale di
  enkk` assente nel codice.
- Fence: **non presente nell'originale** → conferma che è aggiunta del repo; tenuto.

Già coincidenti (non toccare): `[FORMATO RISPOSTA]`, `[SITUAZIONE]` idle,
frase-core `[SITUAZIONE]` chat.

### Nodo architetturale 1 — riferimento temporale ("now") ✅ RISOLTO

- `Perception` ha già `ts: float` (epoch secondi) — il dato temporale esiste
  (`perception.py:49`).
- Il Senser espone `now()` con clock iniettabile (default `time.time`)
  (`senser.py:116,156`); il Reactor lo usa già per `note_agent_message`
  (`reactor.py:215-220`).
- **Verdetto**: in `Reactor.run_once` catturare `now = self._senser.now()` una
  volta per tick (accanto a `recent`/`summary`, `reactor.py:122-132`) e passarlo a
  `build(..., now=now)`. Relativo = `int(round(now - p.ts))` → `-{n}s`. Determinismo
  garantito (clock iniettato nei test); i timestamp vivono SOLO nella sezione
  dinamica → il prefisso stabile resta byte-invariante.

### Nodo architetturale 2 — destino di `format_perception_line` ✅ RISOLTO

- Oggi è la fonte unica condivisa da PromptBuilder e Summarizer
  (`perception.py:118-127`).
- L'originale richiede rese DIVERSE: recent-context `-<N>s <user>: testo`
  (con timestamp e `< >`) vs input Summarizer a bullet raggruppati per fonte
  (`STREAMER:`/`SCHERMO:`/`CHAT:`).
- **Verdetto**: **separare i renderer**. Introdurre un renderer per la
  recent-context che prende `(perception, now)` e produce `-<N>s <user>: testo`;
  il Summarizer ottiene il proprio raggruppamento per fonte (ticket 06).
  `format_perception_line` può restare come helper di base per il testo nudo
  `who: text` o essere ritirata dove non più usata. Da applicare nel ticket 03.

### Incognite residue

Elencate in fondo a `original-chat-prompt-reference.md` (posizione prefisso
stabile, wording esatto del sintetizzatore, etichette parentetiche, chiusura
"streamer→TE", esistenza `[PARLATO/SCHERMO RECENTE]`, formato riga chat nel
summarizer). Richiedono screenshot a piena risoluzione o conferma dell'operatore
prima/durante i ticket relativi.
