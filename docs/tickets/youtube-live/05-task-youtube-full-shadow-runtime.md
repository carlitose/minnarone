---
ticket_schema: 1
ticket_id: "05"
execution_mode: AFK
blocked_by:
  - "04"
---

# Implementare YouTube full shadow tramite Chrome e OS capture

## Parent Spec

[youtube-live-wayfinder.md](../../specs/youtube-live-wayfinder.md)

## Question / Outcome

La verticale YouTube può unire la chat API del ticket 04 con audio e video
catturati localmente dal player Chrome visibile tramite `os_capture`, usando gli
stessi perceiver di Twitch e mantenendo cleanup/backpressure bounded, chat
prioritaria e output esclusivamente shadow?

Output atteso: composizione YouTube chat + OS audio/video, configurazione
validata, smoke diagnostiche limitate, full-shadow example e guida operatore
verificata.

## What to Build

Implementare la
[decisione Chrome + OS capture](../../specs/youtube-live-chrome-os-capture-decision.md).
Il target e la chat restano quelli della verticale YouTube costruita dal ticket
04; il media proviene dal player Chrome aperto manualmente dall'operatore:

- audio dall'output di sistema tramite la sorgente lazy `soundcard` esistente;
- video dal monitor configurato tramite la sorgente lazy `mss` esistente.

Riutilizzare il blocco top-level `os_capture`, `AudioChunk`, `VideoFrame`,
VAD/ASR/speaker/VLM, `MergingSourceAdapter`, la work queue bounded, statistiche
e diagnostica esistenti. Comporre chat, audio e video come reader
single-channel in un solo merger con priorità chat; non annidare
`OsCaptureAdapter`, che espone più canali.

La prima versione cattura il monitor intero. Chrome resta operator-managed: il
runtime non apre/controlla il browser e non richiede estensione, CDP o
`chrome.tabCapture`. Non aggiungere Streamlink, yt-dlp, manifest, FFmpeg o PyAV
al percorso YouTube.

Sezioni coperte: `Destination` punto 2 e `Full multimodal shadow` nella
frontiera.

## Evidence Required

- Test config per `adapter: youtube` + blocco `os_capture`, campi ignoti,
  combinazioni chat/audio/video e backend mancanti, senza regressioni Twitch.
- Test app/adapter con chat fake, `AudioChunk` e `VideoFrame` sintetici: shape,
  failure e silenzio per canale, priorità chat, drop counters, restart, cleanup
  timeout e artifact cap.
- Prova che `--check` resta lazy/offline: non apre API, `soundcard`, `mss`,
  Chrome o modelli e non legge credenziali di invio.
- Guida e smoke bounded per player Chrome visibile, monitor, Screen Recording,
  audio di sistema e BlackHole su macOS.

## Acceptance Criteria

- [ ] Audio produce PCM mono 16 kHz bounded e video produce frame campionati
  nel contratto già accettato dai perceiver, senza duplicare ASR/VLM.
- [ ] `adapter: youtube` può riusare l'unico blocco top-level `os_capture` per
  audio/video senza duplicare monitor, fps o chunk settings nel blocco YouTube;
  i config Twitch e `adapter: os_capture` restano invariati.
- [ ] Una failure media non elimina una chat sana; code sature scartano media
  prima della chat, rendono visibili i drop e isolano anche un guasto chat da
  audio/video locali produttivi.
- [ ] Start/stop e cleanup di reader/device/work queue sono idempotenti,
  restartable e bounded anche su cancellazione, device bloccato o perceiver
  lento.
- [ ] `--check` è offline/lazy e il percorso full shadow non costruisce sender,
  non legge OAuth write e non tenta di avviare o controllare Chrome.
- [ ] Le smoke separate riusano `minnarone-oscapture-smoke`, hanno durata e
  artifact limitati e non chiamano LLM né sender; l'integrazione completa è
  coperta AFK con chat/media fake.
- [ ] Full-shadow example e operator guide descrivono Chrome visibile, monitor
  dedicato, permesso Screen Recording, audio loopback/BlackHole, modelli,
  output shadow, limiti e diagnosi di silenzio/frame neri.
- [ ] Nessun percorso YouTube introduce Streamlink, yt-dlp, URL media, manifest,
  FFmpeg/PyAV playback o configurazione di comandi shell.
- [ ] Test mirati, regression suite e quality checks passano.

## Frontier

Dependency-blocked by 04. La sorgente media è decisa e non ha più un blocking
edge di policy; l'osservazione hardware reale resta HITL nel ticket 08. Il
ticket 05 può avanzare in parallelo alla safety policy 06 dopo che la chat-only
foundation è stabile.

## Step-by-Step Implementation Plan

1. Aggiungere test failing per config/wiring YouTube + `os_capture`, sorgenti
   lazy, composizione chat/audio/video e assenza di sender/browser control.
2. Rendere riusabile la costruzione dei reader OS single-channel senza
   duplicare `_lazy_device_audio_source`/`_lazy_device_video_source` e senza
   annidare due merger.
3. Estendere l'adapter YouTube del ticket 04 con reader OS iniettati e un unico
   `MergingSourceAdapter(priority_channels=("chat",))`.
4. Integrare i perceiver/config già esistenti mantenendo `--check` lazy e la
   work queue audio/video bounded.
5. Riutilizzare le smoke OS capture e aggiungere esempio/guida YouTube Chrome;
   verificare diagnostica, artifact, cleanup e regressioni.

## Testing Plan

Unit test config e lazy device factory; integration test con chat transport
fake, sorgenti OS sintetiche e perceiver fake; test merge/backpressure,
silenzio/failure per canale, restart e cleanup; test documentali/smoke; regression
Twitch e standalone OS capture; `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`.

## Out of Scope

- Invio in chat o live promotion.
- Download automatico dei modelli.
- Avvio o automazione di Chrome, estensione Chrome, CDP e `tabCapture`.
- Streamlink, yt-dlp, manifest/URL media e playback FFmpeg/PyAV per YouTube.
- Installazione/configurazione automatica di BlackHole o permessi del SO.
- Cropping/window capture: la prima versione cattura un monitor intero.
- Prova hardware reale non attended; appartiene al ticket 08 HITL.
- Ottimizzazione specifica hardware oltre i profili esistenti.
