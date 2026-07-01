## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Il core del runner di smoke capture-only per OS-capture (modulo
`oscapture_smoke`): costruisce gli adapter di canale abilitati e scrive gli
artifact bounded (`perceptions.jsonl` per eventuale chat, `raw/audio/*.pcm`,
`raw/video/*.jpg`, `stats.json`) **riusando il writer di artifact esistente**
(quello usato dallo smoke Twitch, che accetta già una lista di `SourceAdapter`).
Solo la funzione runner in questo slice; la CLI/entry-point è lo slice 10.
Testabile con sorgenti fake, nessun hardware. Vedi *Implementation Decisions →
Smoke CLI* e user story 8 nel PRD.

## Step-by-step implementation plan

1. Scrivere `run_oscapture_smoke(...)` che, dai flag audio/video, costruisce i
   `StreamCaptureAdapter` di canale (con sorgenti device iniettabili) e delega al
   writer di artifact esistente. *Perché ora:* dipende da `OsCaptureAdapter`/
   `StreamCaptureAdapter` (05) ma non dalla CLI né dall'hardware.
2. Se il writer di artifact ha naming Twitch-specifico nella firma pubblica,
   estrarne la parte generica riusabile; altrimenti riusarlo così com'è. *Verifica:*
   nessuna duplicazione (R0801).
3. Mantenere il runner **capture-only**: nessun ASR/VLM, salvo un'opzione VAD
   diagnostica come nello smoke Twitch.
4. Unit test con sorgenti fake: artifact scritti, conteggi eventi corretti,
   failure segnalata su zero eventi per un canale abilitato. *Verifica:* test
   verdi, `make quality` pulito.

Trappole: rispettare i cap sul numero di sample/frame salvati (bounded artifacts,
come Twitch); non richiedere `soundcard`/`mss` nei test (sorgenti iniettate).

## Acceptance criteria

- [ ] `run_oscapture_smoke` costruisce i canali abilitati e scrive artifact.
- [ ] Riusa il writer di artifact esistente (nessuna duplicazione).
- [ ] Capture-only (niente ASR/VLM, salvo VAD diagnostico opzionale).
- [ ] Unit test con sorgenti fake coprono artifact, conteggi, failure.

## Blocked by

- Blocked by [05-oscapture-adapter.md](./05-oscapture-adapter.md)

## User stories addressed

- User story 8
