## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

La **percezione audio** end-to-end: l'`OSCaptureAdapter` (parte audio: mic + audio di sistema) alimenta l'`AudioPerceiver` che esegue la pipeline VAD → ASR → speaker tagging e scrive `Perception(source=audio)` nello store, con `speaker` valorizzato (in particolare distinguendo l'operatore/"streamer" dall'audio di un video riprodotto). Da qui il parlato può informare e innescare reazioni.

Demo: parlo → la mia frase appare nello store trascritta e taggata `streamer`; l'audio di un video riprodotto NON viene taggato come streamer.

Riferimenti PRD: *Step-by-Step* 3 (parte audio), 5; *Implementation Decisions* (OSCaptureAdapter, AudioPerceiver); FR01, EC01, EC02.

## Step-by-step implementation plan

1. **Implementa la parte audio di `OSCaptureAdapter`** (cattura mic + audio di sistema), dietro l'interfaccia `SourceAdapter` dello slice 00. Perché ora: l'`AudioPerceiver` ha bisogno di uno stream. Trappola: permessi macOS per l'audio di sistema — documentarli.
2. **Implementa l'`AudioPerceiver`**: VAD (salta il silenzio) → ASR → speaker tagging → `Perception`. Perché ora: è la fonte a più alto valore. Verifica su clip nota: trascrizione plausibile, `speaker` valorizzato, silenzio non trascritto.
3. **Distingui la fonte "operatore" dal resto** (EC02): la frase detta dall'operatore va taggata `streamer`; l'audio di un video no. Verifica con un caso misto. Trappola: tollerare trascrizioni rumorose (EC01) — basta "il senso", non rompere.
4. **Verifica end-to-end:** le percezioni audio finiscono nello store e possono alimentare Senser/PromptBuilder come gli altri canali.

## Acceptance criteria

- [ ] Il parlato dell'operatore viene trascritto e scritto nello store come `Perception(source=audio)` con `speaker` valorizzato.
- [ ] Il VAD evita di trascrivere il silenzio.
- [ ] L'audio di un video riprodotto non viene taggato come `streamer`.
- [ ] Trascrizioni rumorose degradano con grazia, senza crash.
- [ ] Test di contratto su `AudioPerceiver` (fake VAD/ASR) e su `OSCaptureAdapter` (fake device).

## Blocked by

- Blocked by [00-foundational-contracts.md](./00-foundational-contracts.md)

## User stories addressed

- User story 7
- User story 8
- User story 12
