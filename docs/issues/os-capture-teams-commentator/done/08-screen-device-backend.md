## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Implementare il backend reale di cattura **schermo** nello stub
`make_device_screen_capture_source` di `capture.py`, usando `mss` (cattura del
monitor per indice) e producendo un iterabile lazy di `VideoFrame` con i pixel in
`ndarray` RGB nel formato che il `Captioner` Qwen2-VL già consuma
(`source_label="screen"`). Aggiungere `mss` all'extra `[os-capture]`. Import
lazy. Vedi *Implementation Decisions → Backend device reali* nel PRD.

## Step-by-step implementation plan

1. Aggiungere `mss` all'extra `[os-capture]` in `pyproject.toml`. *Perché ora:* il
   backend importa `mss`.
2. Implementare `make_device_screen_capture_source(monitor, fps)` come
   **generatore lazy** che importa `mss` solo internamente e cattura il monitor
   indicato **alla prima iterazione**. Convertire il frame BGRA di `mss` in
   `ndarray` RGB e impacchettarlo in un `VideoFrame` (`source_label="screen"`,
   `ts` corrente), campionando a `fps`.
3. Gestire il caso di **monitor inesistente** e permessi negati con errori
   chiari. Nessun test automatico (richiede uno schermo): verifica manuale via
   smoke (slice 10), documentata nello slice 12.
4. Confermare `deptry`/`make quality` puliti (import lazy).

Trappole: rispettare la conversione BGRA→RGB (altrimenti caption con colori
sballati); non aprire lo schermo in fase di import/costruzione; l'indice monitor
di `mss` parte da 1 per il primo schermo reale (0 = tutti i monitor uniti) —
allineare al default `monitor: 1` della config.

## Acceptance criteria

- [ ] `make_device_screen_capture_source` produce `VideoFrame` RGB dal monitor.
- [ ] Import di `mss` lazy; schermo catturato solo alla prima iterazione.
- [ ] `mss` presente nell'extra `[os-capture]`; `make quality`/`deptry` puliti.
- [ ] Monitor inesistente/permessi negati → errore chiaro.

## Blocked by

- Blocked by [07-audio-device-backend.md](./07-audio-device-backend.md)

## User stories addressed

- User story 3
- User story 9
