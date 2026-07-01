## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Implementare il backend reale di cattura **audio di sistema (loopback)** nello
stub `make_device_capture_source` di `capture.py`, usando `soundcard`
(`get_microphone(..., include_loopback=True)`) e producendo un iterabile lazy di
`AudioChunk` (PCM mono 16 kHz signed 16-bit LE, `source_label="system"`).
Aggiungere il nuovo extra `[os-capture]` in `pyproject.toml` con `soundcard`
(più `numpy` se serve). Import lazy della dipendenza. Vedi *Implementation
Decisions → Backend device reali* e *Step-by-Step → step 5* nel PRD.

## Step-by-step implementation plan

1. Aggiungere l'extra `os-capture` in `pyproject.toml` con `soundcard` (e
   `numpy>=1.26` se necessario alla conversione dei campioni). *Perché ora:* il
   backend importa `soundcard`, quindi l'extra deve esistere.
2. Implementare `make_device_capture_source` come **generatore lazy** che importa
   `soundcard` solo internamente e apre il device di loopback dell'uscita di
   default **alla prima iterazione**, non alla costruzione. Ogni chunk diventa un
   `AudioChunk` con `sample_rate=16000`, `source_label="system"`, `ts` corrente.
3. Convertire i campioni nel formato PCM atteso dalla pipeline VAD/ASR (mono
   16 kHz s16le). *Perché:* VAD/ASR assumono quel formato.
4. Gestire errori operatore (nessun device di loopback / permessi) con messaggi
   chiari. Nessun test automatico (richiede hardware): la verifica è manuale via
   smoke (slice 10) — documentata nello slice 12.
5. Confermare che `deptry`/`make quality` non segnali la nuova dipendenza come
   inutilizzata o mancante (import lazy dentro la funzione).

Trappole: non aprire il device in fase di import/costruzione (romperebbe
`--check` e i test); non fissare un sample rate diverso da 16 kHz; su macOS il
loopback richiede un device esterno (limite noto, gestito come errore chiaro).

## Acceptance criteria

- [ ] `make_device_capture_source` produce `AudioChunk` PCM 16 kHz da loopback.
- [ ] Import di `soundcard` lazy; device aperto solo alla prima iterazione.
- [ ] Extra `[os-capture]` presente; `make quality`/`deptry` puliti.
- [ ] Errori di device/permessi riportati con messaggi chiari.

## Blocked by

None - can start immediately

## User stories addressed

- User story 2
- User story 9
- User story 14
