# PRD — Commentatore locale su meeting Teams via OS-capture

> **Slug:** `os-capture-teams-commentator`
> **Data:** 2026-07-01
> **Riferimenti:** [SPECIFICATION.md](../SPECIFICATION.md) (FR06/FR07, US02, U03, roadmap v2) ·
> [ADR Live Media Backpressure Boundary](../adrs/2026-06-29-live-media-backpressure-boundary.md)

## Problem Statement

Oggi Minnarone percepisce solo sorgenti Twitch (chat via IRC, audio/video via
Streamlink) più un percorso di cattura del sistema operativo (`os_capture`) che
è **documentato ma non cablato**: gli stub `make_device_capture_source` /
`make_device_screen_capture_source` sollevano `NotImplementedError`, e
`app.py::_configured_adapter` costruisce un adapter solo per `adapter == "twitch"`.

L'operatore vuole usare Minnarone durante un **meeting Microsoft Teams**: entrare
lui stesso nella call col client Teams e avere un **commentatore locale** che
osserva ciò che accade (voci degli altri partecipanti + schermo condiviso) e
stampa commenti riservati in console, senza inviare nulla nel meeting.

Teams non espone un modo semplice per leggere audio/video/chat di una call senza
la complessità di Microsoft Graph (app registration, consenso admin del tenant,
media application-hosted). L'operatore ha scelto esplicitamente di **evitare
Graph** e di catturare il meeting a livello di sistema operativo.

## Solution

Cablare finalmente il percorso **OS-capture** come `SourceAdapter` di prima
classe, agnostico alla piattaforma. L'operatore:

1. entra nel meeting col client Teams (audio del meeting sull'uscita audio di
   default, eventuale schermo condiviso visibile a video);
2. avvia Minnarone con una config `adapter: os_capture`, `mode: private`,
   `commentator.enabled: true`;
3. Minnarone cattura **l'audio di sistema** (loopback: le voci degli altri
   partecipanti) e lo **schermo** (contenuto condiviso), li fa passare per le
   pipeline già esistenti VAD→ASR→speaker e sampling→VLM, e il commentatore
   stampa i suoi interventi in console come `[PRIVATE]`.

Poiché il percorso è identico per Zoom/Meet/Teams, la feature è generica
(`os_capture`) e "Teams" è solo un **preset di configurazione** di esempio.

**Decisione di scope chiave:** la **chat scritta** di Teams è **fuori scope**
(non ottenibile via OS-capture senza Graph/OCR). Il parlato del meeting è
comunque coperto dal canale audio→ASR. Vedi *Out of Scope*.

## User Stories

1. Come operatore in un meeting Teams, voglio avviare Minnarone da un file di
   configurazione con `adapter: os_capture`, così che possa osservare la call
   senza scrivere codice.
2. Come operatore, voglio che Minnarone catturi **l'audio di sistema** (le voci
   degli altri partecipanti), così che il commentatore capisca cosa viene detto.
3. Come operatore, voglio che Minnarone catturi **lo schermo** (contenuto
   condiviso), così che il commentatore possa riferirsi a ciò che è mostrato.
4. Come operatore, voglio ricevere i commenti **solo in console locale**
   (`[PRIVATE]`), così che nulla venga inviato dentro il meeting.
5. Come operatore, voglio poter **abilitare/disabilitare audio e video**
   indipendentemente dalla config, così da poter partire con solo audio se il
   VLM è troppo lento sulla mia macchina.
6. Come operatore, voglio poter **scegliere quale schermo** catturare (indice
   monitor), così da catturare il monitor giusto in un setup multi-monitor.
7. Come operatore, voglio che `python -m minnarone config.yaml --check` **validi
   la configurazione senza aprire mic/schermo**, così da verificare il setup
   senza attivare la cattura hardware.
8. Come operatore, voglio uno strumento di **smoke capture-only**
   (`minnarone-oscapture-smoke`), così da diagnosticare "il device cattura?"
   separatamente da "l'ASR/VLM funziona?".
9. Come operatore su **Windows**, voglio che il loopback dell'audio di sistema
   funzioni nativamente (WASAPI), senza installare device virtuali.
10. Come operatore, voglio una **guida** che spieghi come impostare l'uscita
    audio di default e i permessi di cattura schermo, così da evitare frame neri
    o audio muto.
11. Come sviluppatore del framework, voglio che il **motore di merge** dei
    canali sia condiviso fra Twitch e OS-capture, così da non duplicare ~250
    righe (che il gate pylint `duplicate-code` boccerebbe) e da mantenere il core
    neutro rispetto alla piattaforma.
12. Come sviluppatore, voglio che la cattura hardware sia **iniettabile**, così
    che i test girino offline senza device.
13. Come sviluppatore, voglio che l'adapter OS-capture rispetti la stessa
    **policy di backpressure** già decisa nell'ADR (audio/video sono stream
    lossy real-time), così che una macchina lenta degradi con drop osservabili
    invece di accumulare backlog stale.
14. Come operatore multi-platform, voglio che lo stesso adapter funzioni su
    **Linux** (monitor PulseAudio), accettando che **macOS** richieda un device
    di loopback esterno (limite documentato).

## Implementation Decisions

### Architettura e moduli

- **`MergingSourceAdapter` (NUOVO, modulo profondo).** Si estrae dal
  `TwitchStreamAdapter` il motore che compone più `SourceAdapter` per-canale in
  un unico stream `RawEvent` bounded, con la policy di backpressure esistente
  (coda limitata; sotto pressione droppa preferendo mantenere la chat; conteggi
  `produced`/`dropped`/`failures`; isolamento per-canale; arresto pulito). La
  sua interfaccia pubblica resta quella di un `SourceAdapter`
  (`channels()`/`start()`/`stop()`/`events()`) più uno `stats()` diagnostico.
  `TwitchStreamAdapter` viene rifattorizzato a **thin wrapper**: conserva
  `_build_readers` (costruzione dei reader Twitch) e delega tutto il resto al
  `MergingSourceAdapter`. **Vincolo:** i test Twitch esistenti devono restare
  verdi (nessun cambio di comportamento osservabile).

- **`OsCaptureAdapter` (NUOVO, modulo profondo).** Data una `OsCaptureConfig` e
  le sorgenti device (audio/video), costruisce i `StreamCaptureAdapter` di canale
  (via `os_audio_capture` / `os_screen_capture` già esistenti) e li compone con
  un `MergingSourceAdapter`. Espone `channels()` = sottoinsieme di
  `{"audio","video"}` secondo i flag. Le **sorgenti device sono iniettabili**:
  nei test si passano iterabili in-memory di `AudioChunk`/`VideoFrame`; live, di
  default usa i backend reali.

- **Backend device reali (in `capture.py`, moduli shallow).** Si implementano
  gli stub oggi `NotImplementedError`:
  - audio system-loopback via **`soundcard`** (`get_microphone(..., include_loopback=True)`)
    → generatore di `AudioChunk` (PCM mono 16 kHz, `source_label="system"`);
  - schermo via **`mss`** (monitor per indice) → generatore di `VideoFrame`
    (`source_label="screen"`), con i pixel convertiti in `ndarray` RGB nel
    formato che il `Captioner` Qwen2-VL già consuma.
  L'import della dipendenza pesante avviene **solo dentro la factory** (import
  lazy), e la factory ritorna un **generatore lazy** che apre il device solo alla
  prima iterazione. Così il caricamento del modulo, `--check` e i test non
  toccano mai hardware.

- **`OsCaptureConfig` (MODIFY `config.py`, modulo profondo).** Nuova dataclass
  frozen sul modello di `TwitchConfig`, con `from_dict` e validazione a mano
  (`ConfigError` puntuali). Campi:
  - `audio: bool = True`
  - `video: bool = True`
  - `audio_chunk_seconds: float = 1.0`
  - `video_fps: float = 1.0`
  - `monitor: int = 1` (indice schermo per `mss`; 1 = primario)
  Regola: almeno uno fra `audio`/`video` deve essere abilitato. `Config`
  acquisisce un campo `os_capture: OsCaptureConfig | None`, e la validazione
  richiede che `adapter == "os_capture"` implichi la sezione `os_capture:`
  (specularmente a Twitch).

- **Wiring (MODIFY `app.py::_configured_adapter`).** Aggiungere il ramo
  `adapter == "os_capture"`: riusare `_build_default_audio_perceiver` /
  `_build_default_video_perceiver` (identici a Twitch) per i canali abilitati, e
  costruire un `OsCaptureAdapter` con le sorgenti device reali (lazy). Il resto
  del cablaggio (`BoundedLocalPerceptionQueue`, dispatcher per-canale, reactor,
  summarizer, output) resta invariato: audio/video passano già dalla queue
  bounded, quindi la policy dell'ADR si applica automaticamente.

- **Output.** Nessun modulo nuovo: si riusa il percorso commentatore locale già
  esistente (`mode: private` + `commentator.enabled: true` →
  `TuiPrivateOutputRouter` / console `[PRIVATE]`).

- **Smoke CLI (NUOVO `oscapture_smoke.py` + entry-point).** `minnarone-oscapture-smoke`
  con flag `--duration`, `--output`, `--audio`/`--video`, `--monitor`,
  `--audio-chunk-seconds`, `--video-fps`, `--vad-diagnostic`, ecc. Riusa il
  writer di artifact esistente (che accetta già una lista di `SourceAdapter` e
  scrive `perceptions.jsonl`, `raw/audio/*.pcm`, `raw/video/*.jpg`, `stats.json`).
  Se il writer contiene naming Twitch-specifico nella firma pubblica, estrarne la
  parte generica; altrimenti riusarlo così com'è.

- **Packaging (MODIFY `pyproject.toml`).** Nuovo extra
  `os-capture = ["soundcard>=0.4", "mss>=9", "numpy>=1.26"]` e nuovo script
  `minnarone-oscapture-smoke = "minnarone.oscapture_smoke:main"`. Mappare i
  moduli per deptry se necessario.

### Contratti dati (invarianti, non modificati)

- Il canale `audio` produce `RawEvent(channel="audio", payload=AudioChunk)`; il
  canale `video` produce `RawEvent(channel="video", payload=VideoFrame)`. Sono i
  contratti già consumati da `AudioPerceiver` / `VideoPerceiver`.
- `AudioChunk.source_label = "system"` per tutto l'audio catturato (nessun
  operatore locale nell'MVP): lo speaker-tagger tratta i cluster come non-operatore.
- `VideoFrame.source_label = "screen"`.

## Step-by-Step Implementation Plan

L'ordine minimizza il rischio: prima il refactor (dietro test verdi), poi la
config, poi i pezzi che dipendono da entrambi, infine hardware e docs.

1. **Estrarre `MergingSourceAdapter`.** Creare il nuovo modulo con il motore di
   merge/backpressure preso da `TwitchStreamAdapter`, e rifattorizzare
   `TwitchStreamAdapter` a wrapper che delega (mantiene solo `_build_readers` e
   i default Twitch). *Perché prima:* è l'unico passo che tocca codice esistente;
   isolandolo si verifica subito la non-regressione. *Verifica:* l'intera suite
   di test Twitch (adapter, stream, smoke) resta verde senza modifiche ai test;
   `make quality` pulito, in particolare **nessun** report `duplicate-code`.
   *Trappola:* non cambiare l'ordine dei canali né la semantica di drop; sono
   osservati dai test e dalla TUI.

2. **Aggiungere `OsCaptureConfig` e cablarla in `Config`.** Nuova dataclass +
   `from_dict` + campo `os_capture` in `Config` + validazione
   `adapter == "os_capture"` ⇒ sezione presente. *Perché ora:* è indipendente
   dall'hardware e sblocca `--check`. *Verifica:* test di config (campi default,
   campi sconosciuti rifiutati, `adapter os_capture` senza sezione → `ConfigError`,
   né audio né video → `ConfigError`); `python -m minnarone <preset> --check`
   passa. *Trappola:* rifiutare i campi sconosciuti (come fa `TwitchConfig`), non
   ignorarli.

3. **Implementare `OsCaptureAdapter` con sorgenti iniettate.** Compone i
   `StreamCaptureAdapter` audio/video via `MergingSourceAdapter`; **nessun**
   backend reale ancora — solo l'iniezione. *Perché ora:* dipende da (1) e (2)
   ma non dall'hardware, quindi è testabile offline. *Verifica:* test con
   sorgenti fake in-memory: emette `RawEvent` sui canali giusti, rispetta
   `start()/stop()`, si ferma quando le sorgenti si esauriscono, espone `stats()`.
   *Trappola:* rispettare il contratto lazy — non iterare le sorgenti prima di
   `start()`.

4. **Cablare il ramo `os_capture` in `app.py`.** In `_configured_adapter`
   gestire `adapter == "os_capture"`: costruire i perceiver audio/video riusando
   gli helper esistenti e istanziare `OsCaptureAdapter` con sorgenti device
   **lazy**. *Perché ora:* collega config + adapter al runtime; ancora testabile
   iniettando `adapter=` o sorgenti fake in `build_agent`. *Verifica:* test di
   wiring che `build_agent` con una `os_capture` config e sorgenti fake produce
   un `Agent` che, in `run()`, popola lo store da audio+video; `--check` non apre
   device. *Trappola:* replicare la coerenza di Twitch (se un canale è abilitato
   ma manca il perceiver/backend, errore chiaro).

5. **Implementare i backend device reali** (`soundcard` loopback + `mss`) negli
   stub di `capture.py`, con import lazy e generatore lazy. *Perché ora:* è la
   parte non-testabile automaticamente; arriva dopo che tutto il resto è verde.
   *Verifica:* **manuale** — vedi passo 7 (smoke). Nessun test automatico.
   *Trappola:* PCM mono 16 kHz signed 16-bit LE per l'audio (formato atteso da
   VAD/ASR); conversione `mss` BGRA→RGB `ndarray` per il video; gestire il caso
   monitor inesistente con errore chiaro.

6. **Aggiungere lo smoke CLI** `minnarone-oscapture-smoke` + entry-point in
   `pyproject.toml` + extra `[os-capture]`. Riusa il writer di artifact.
   *Verifica:* test del runner con sorgenti fake (scrive artifact, conta eventi,
   segnala "nessun evento" come failure); l'help della CLI si apre. *Trappola:*
   il runner deve rimanere capture-only (niente ASR/VLM se non `--vad-diagnostic`).

7. **Preset + docs operatore.** `examples/teams-commentator.yaml`
   (`adapter: os_capture`, `mode: private`, `commentator.enabled: true`, audio+video
   on) e sezione README: impostare l'uscita audio di default sul dispositivo su
   cui gira Teams, permessi di cattura schermo, comando smoke, limiti macOS.
   *Verifica:* `--check` sul preset passa; walkthrough manuale dello smoke su una
   call Teams reale cattura audio+video (acceptance manuale, come per Twitch).

8. **Acceptance manuale live** (HITL, non automatizzata): eseguire il
   commentatore su un meeting Teams reale e registrare l'esito, sullo stesso
   modello delle issue di acceptance Twitch/TUI esistenti.

## Testing Decisions

Un buon test qui verifica **comportamento esterno**, non dettagli interni: che
canali emette un adapter, quali `RawEvent` produce da sorgenti note, come si
comporta sotto pressione (drop osservabili), quali `ConfigError` solleva una
config malformata. I test **non** devono toccare device, rete, modelli ML, né
richiedere `soundcard`/`mss`/FFmpeg installati.

Moduli coperti da unit test:

- **`MergingSourceAdapter`** — merge di più reader fake, ordine/isolamento
  canali, policy di backpressure e conteggi, arresto pulito. Prior art:
  i test esistenti di `TwitchStreamAdapter` (stessa superficie).
- **`OsCaptureAdapter`** — composizione e ciclo di vita con sorgenti
  `AudioChunk`/`VideoFrame` fake in-memory. Prior art: i test dei perceiver che
  usano `os_audio_capture`/`os_screen_capture` con sorgenti finte, e i fake in
  `fakes.py`.
- **`OsCaptureConfig`** (+ integrazione in `Config`) — default, rifiuto campi
  sconosciuti, regole di validazione. Prior art: i test di `TwitchConfig`/`Config`.
- **Runner dello smoke** — con sorgenti fake: artifact scritti, conteggi,
  failure su zero eventi. Prior art: i test di `run_twitch_smoke` /
  `capture_twitch_smoke`.
- **Wiring `build_agent`** per `adapter: os_capture` con sorgenti fake. Prior
  art: i test di wiring Twitch chat-only.

**Non** coperti da test automatici: i backend device reali (`soundcard`/`mss`) e
l'acceptance live — restano manuali (coerente con l'ADR: acceptance
Twitch/Qwen/Whisper è manuale perché dipende da hardware/stream).

## Out of Scope

- **Chat scritta di Teams.** Non ottenibile via OS-capture senza Microsoft Graph
  o OCR. Il parlato è coperto da audio→ASR. Se servirà, sarà uno slice separato
  (connettore Graph) dietro l'astrazione `SourceAdapter`, senza toccare il resto.
- **Cattura del microfono dell'operatore.** MVP cattura solo system audio; il mic
  come seconda sotto-sorgente audio è un'evoluzione futura.
- **Qualsiasi output *dentro* Teams** (scrivere in chat, parlare via TTS,
  partecipare). L'agente è un osservatore locale; modalità pubblica su Teams è
  fuori scope.
- **Integrazione API Microsoft Graph / Bot Framework / media application-hosted.**
- **Cattura di una specifica finestra** (solo monitor interi via `mss`).
- **Diarizzazione con nomi reali dei partecipanti Teams** (lo speaker-tagger
  produce cluster anonimi).

## Further Notes

- Il percorso è **agnostico alla piattaforma**: la stessa feature abilita Zoom e
  Meet. "Teams" è solo un preset; la sezione config si chiama `os_capture:`
  proprio per non implicare un'integrazione Teams-specifica inesistente.
- **Multi-platform:** loopback audio nativo su Windows (WASAPI) e Linux (monitor
  PulseAudio) via `soundcard`; su **macOS** serve un device di loopback esterno
  (es. BlackHole) — limite noto da documentare, nessun impatto per l'operatore
  attuale (Windows).
- La policy di backpressure dell'ADR si applica **gratis**: audio/video passano
  già dal `BoundedLocalPerceptionQueue`, quindi una macchina lenta degrada con
  drop osservabili invece di accumulare backlog.
- Prossimo passo suggerito: spacchettare questo PRD in issue con la skill
  `prd-to-issues` (slice verticali tracciabili nell'ordine del piano sopra).
