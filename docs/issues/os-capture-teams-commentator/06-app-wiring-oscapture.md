## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Cablare il ramo `adapter == "os_capture"` in `app.py::_configured_adapter` /
`build_agent`, così che il percorso sia **completo end-to-end**: da una config
`os_capture` (audio+video) l'agente costruisce i perceiver audio/video (riusando
gli helper esistenti) e un `OsCaptureAdapter` (slice 05) con sorgenti device
lazy. Verificabile senza hardware iniettando sorgenti fake in `build_agent`.
Questo è il tracer bullet: config → adapter → pump → store → (commentatore).
Vedi *Implementation Decisions → Wiring* e *Step-by-Step → step 4* nel PRD.

## Step-by-step implementation plan

1. In `_configured_adapter`, aggiungere il ramo `os_capture`: per i canali
   abilitati dalla config, riusare `_build_default_audio_perceiver` /
   `_build_default_video_perceiver` (identici al path Twitch) e istanziare
   `OsCaptureAdapter` con le sorgenti device **lazy**. *Perché ora:* dipende da
   config integrata (04) e dall'adapter (05).
2. Consentire l'iniezione delle sorgenti device / dell'`adapter` in `build_agent`
   per i test (nessun device reale nei test), sullo stesso modello dei parametri
   iniettabili già presenti per Twitch.
3. Assicurare che audio/video passino, come per Twitch, dalla
   `BoundedLocalPerceptionQueue`, così la policy di backpressure dell'ADR si
   applica senza codice nuovo.
4. Replicare la coerenza di Twitch: se un canale è abilitato ma manca il
   perceiver/backend richiesto, sollevare un `ConfigError` chiaro.
5. Test di wiring: `build_agent` con config `os_capture` e sorgenti fake produce
   un `Agent` che in `run()` popola lo store da audio+video; `--check` resta
   pulito senza aprire device. *Verifica:* test verdi, `make quality` pulito.

Trappole: non aprire hardware in `build_agent`/`--check` (le sorgenti restano
lazy); mantenere l'output sul percorso commentatore locale esistente (nessun
nuovo router).

## Acceptance criteria

- [ ] `adapter: os_capture` costruisce un agente completo con `OsCaptureAdapter`.
- [ ] Sorgenti device iniettabili in `build_agent`; `--check` non apre hardware.
- [ ] Con sorgenti fake, `run()` scrive percezioni audio+video nello store.
- [ ] Canale abilitato senza backend → `ConfigError` chiaro.

## Blocked by

- Blocked by [04-config-integration-and-check.md](./04-config-integration-and-check.md)
- Blocked by [05-oscapture-adapter.md](./05-oscapture-adapter.md)

## User stories addressed

- User story 1
- User story 4
- User story 5
- User story 7
