## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Integrare `OsCaptureConfig` (slice 03) dentro `Config`: nuovo campo
`os_capture: OsCaptureConfig | None`, parsing della sezione `os_capture:` in
`Config.from_dict`, e la regola di validazione che `adapter == "os_capture"`
implica la presenza della sezione (specularmente a `adapter == "twitch"`). Al
termine, `python -m minnarone <config> --check` deve validare una config
`os_capture` **senza aprire hardware** (in questo slice l'adapter non è ancora
attivo: `_configured_adapter` continua a ritornare `None` per `os_capture`, che
arriva nello slice 06). Vedi *Implementation Decisions → OsCaptureConfig* e user
story 7 nel PRD.

## Step-by-step implementation plan

1. Aggiungere il campo `os_capture` a `Config` e il suo controllo di tipo in
   `__post_init__`. *Perché ora:* dipende solo dal tipo config (03), non
   dall'hardware.
2. In `Config.from_dict`, parsare la tabella `os_capture:` (validandola come
   mappa) e costruire `OsCaptureConfig.from_dict`.
3. Aggiungere la regola: `adapter == "os_capture"` senza sezione `os_capture:` →
   `ConfigError` (come per Twitch).
4. Confermare che `_configured_adapter` gestisca `os_capture` ritornando `None`
   (nessun adapter attivo ancora), così `--check` costruisce l'agente senza
   toccare device. *Verifica:* test di `Config` (parsing, regola adapter/sezione)
   e un test che `--check` su una config `os_capture` minimale ritorna successo.

Trappole: non far crashare `build_agent`/`--check` sul ramo `os_capture` non
ancora cablato; mantenere la coerenza dei messaggi con il ramo Twitch.

## Acceptance criteria

- [ ] `Config` ha il campo `os_capture` e lo valida.
- [ ] `Config.from_dict` parsa la sezione `os_capture:`.
- [ ] `adapter: os_capture` senza sezione → `ConfigError`.
- [ ] `--check` su una config `os_capture` passa senza aprire hardware.

## Blocked by

- Blocked by [03-oscapture-config-type.md](./03-oscapture-config-type.md)

## User stories addressed

- User story 1
- User story 7
