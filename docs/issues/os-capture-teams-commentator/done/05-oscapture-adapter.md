## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Il modulo profondo `OsCaptureAdapter`: data una `OsCaptureConfig` e le sorgenti
device (audio/video), costruisce i `StreamCaptureAdapter` di canale (via i
costruttori esistenti `os_audio_capture` / `os_screen_capture`) e li compone con
un `MergingSourceAdapter` (slice 01). Le sorgenti device sono **iniettabili**: in
questo slice si testa con iterabili in-memory di `AudioChunk`/`VideoFrame`,
nessun hardware. Vedi *Implementation Decisions → OsCaptureAdapter* nel PRD.

## Step-by-step implementation plan

1. Definire `OsCaptureAdapter` che, dai flag `audio`/`video` della config,
   seleziona i canali attivi e costruisce un `StreamCaptureAdapter` per canale a
   partire dalla sorgente iniettata corrispondente. *Perché ora:* dipende dal
   merge (01) e dal tipo config (03), ma non dall'hardware.
2. Comporre i reader di canale con `MergingSourceAdapter`; esporre
   `channels()` = sottoinsieme di `{"audio","video"}` e delegare
   `start()/stop()/events()/stats()`.
3. Rispettare il **contratto lazy**: le sorgenti non devono essere iterate prima
   di `start()`.
4. Unit test con sorgenti fake in-memory: emette `RawEvent` sui canali attesi con
   il payload corretto (`AudioChunk`/`VideoFrame`); rispetta il ciclo di vita; si
   ferma quando le sorgenti si esauriscono; `stats()` coerente; se nessun canale
   è attivo, errore chiaro. *Verifica:* test verdi, `make quality` pulito.

Trappole: `AudioChunk.source_label` deve restare `"system"` e
`VideoFrame.source_label` `"screen"` (contratti del PRD); non importare qui alcun
backend hardware (`soundcard`/`mss`), che arriva negli slice 07/08.

## Acceptance criteria

- [ ] `OsCaptureAdapter` compone audio/video via `MergingSourceAdapter`.
- [ ] Sorgenti device iniettabili; nessun import di backend hardware nel modulo.
- [ ] Unit test con sorgenti fake coprono canali, payload, lifecycle, stats.
- [ ] Contratto lazy rispettato (nessuna iterazione prima di `start()`).

## Blocked by

- Blocked by [01-merging-source-adapter.md](./01-merging-source-adapter.md)
- Blocked by [03-oscapture-config-type.md](./03-oscapture-config-type.md)

## User stories addressed

- User story 12
- User story 13
