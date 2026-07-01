## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

L'entry-point CLI `minnarone-oscapture-smoke` sopra il runner (slice 09): parsing
argomenti, validazione, codici di uscita, e registrazione dello script in
`pyproject.toml`. Modello: la CLI dello smoke Twitch (`minnarone-twitch-smoke`).
Vedi *Implementation Decisions → Smoke CLI* nel PRD.

## Step-by-step implementation plan

1. Aggiungere `main(argv)` con `argparse`: flag `--duration`, `--output`,
   `--audio`/`--video`, `--monitor`, `--audio-chunk-seconds`, `--video-fps`,
   `--vad-diagnostic` e i cap `--max-audio-samples`/`--max-video-frames`, sul
   modello di `minnarone-twitch-smoke`. *Perché ora:* dipende dal runner (09).
2. Validare gli argomenti (durata > 0, fps > 0, ecc.) restituendo exit code 2 su
   input invalido, 1 su failure di cattura, 0 su successo — stessa convenzione
   dello smoke Twitch.
3. Registrare lo script `minnarone-oscapture-smoke` in `pyproject.toml`
   (`[project.scripts]`).
4. Test: parsing/validazione argomenti e mapping degli exit code con runner/
   sorgenti fake; l'help della CLI si apre. *Verifica:* test verdi, `make quality`
   pulito.

Trappole: usare le sorgenti device reali (07/08) di default ma consentire
l'iniezione di fake nei test; non aprire hardware durante i test della CLI.

## Acceptance criteria

- [ ] `minnarone-oscapture-smoke` registrato e invocabile.
- [ ] Argomenti validati con exit code coerenti (0/1/2).
- [ ] Test coprono parsing, validazione ed exit code con fake.
- [ ] Di default usa i backend device reali; iniettabile nei test.

## Blocked by

- Blocked by [09-smoke-runner.md](./09-smoke-runner.md)

## User stories addressed

- User story 8
