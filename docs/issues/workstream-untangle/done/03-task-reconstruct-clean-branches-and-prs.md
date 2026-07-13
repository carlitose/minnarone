## Parent Spec

[workstream-untangle-wayfinder.md](../../specs/workstream-untangle-wayfinder.md)

## Type

task

## Outcome

Eseguire lo split concreto in branch/PR puliti secondo la decisione del ticket
02, così che ogni filone (W1, W2, W3, W4, `.env`) arrivi a `main` in modo
revisionabile e nell'ordine giusto, senza perdere lavoro.

## Acceptance Criteria

- [ ] I branch/PR creati riflettono la strategia decisa nel ticket 02.
- [ ] W3 (meeting-synth/`profiles`) ha una storia coerente (singolo commit o
      per-ticket, come deciso) e non trascina dentro fix estranei.
- [ ] I fix di accettazione public-TUI risultano nel filone deciso (W2 o W3).
- [ ] Ogni branch compila e passa la suite (con i 3 flaky noti deselezionati).
- [ ] Nessun lavoro perso: W1–W4 + `.env` + i ticket meeting-synth/diarizzazione
      restano rappresentati.
- [ ] Le PR NON vengono auto-mergiate (il repo auto-deploya su merge a main).

## Blocked By

- [01-research-dependency-map-and-snapshot-attribution.md](./01-research-dependency-map-and-snapshot-attribution.md)
- [02-grilling-merge-order-and-pr-strategy.md](./02-grilling-merge-order-and-pr-strategy.md)

## Frontier

Ultimo edge esecutivo. Non iniziare finché 01 (mappa) e 02 (decisione) non sono
chiusi, e solo su richiesta esplicita dell'utente di ESEGUIRE (wayfinder si
ferma al piano per default).

## Work Plan

Dipende dalla decisione del ticket 02. In generale:
1. Partire dalla base `main` (`f1ddf86`) e ricostruire i branch nell'ordine
   deciso (cherry-pick / rebase / commit ricomposti dallo snapshot secondo la
   mappa del ticket 01).
2. Per lo snapshot `14e7c9b`: separarne i contenuti nei filoni giusti usando la
   mappa file/hunk del ticket 01 (probabile `git checkout -p` / patch mirati).
3. Dopo ogni branch: compilare, `uv run pytest` (3 flaky deselezionati),
   `uv run ruff check`.
4. Creare le PR (senza auto-merge) nell'ordine deciso.

## Evidence to Capture

- I branch/PR creati e il loro contenuto.
- Esiti test/lint per branch.
- Eventuali conflitti risolti e come.

## Out of Scope

- Le run di accettazione HITL (W2 10–11, W3 15, W4 05).
- Il merge finale su main (gate umano separato).
