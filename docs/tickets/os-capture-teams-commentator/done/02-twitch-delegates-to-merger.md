## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Rifattorizzare `TwitchStreamAdapter` in un **thin wrapper** che delega tutto il
merge/backpressure al `MergingSourceAdapter` (slice 01), conservando solo la
parte Twitch-specifica (`_build_readers` e i default: chat/audio/video Twitch).
Nessun cambiamento di comportamento osservabile. Vedi *Implementation Decisions →
MergingSourceAdapter* e *Step-by-Step Implementation Plan → step 1* nel PRD.

## Step-by-step implementation plan

1. Sostituire il corpo di merge di `TwitchStreamAdapter` con una delega a
   `MergingSourceAdapter`, passandogli la mappa di reader costruita da
   `_build_readers`. Mantenere `channels()`/`start()`/`stop()`/`events()`/`stats()`
   con la stessa firma pubblica. *Perché ora:* dopo che il motore condiviso è
   testato in isolamento (01), lo swap di Twitch è a rischio contenuto.
2. Preservare la validazione dei canali dei reader e i costruttori
   ergonomici/entry-point esistenti che usano `TwitchStreamAdapter`.
3. *Verifica:* l'intera suite di test Twitch esistente (adapter, stream, smoke)
   resta **verde senza modifiche ai test**. Se un test cambia, il refactor ha
   alterato il comportamento — indagare invece di adeguare il test.
4. Eseguire `make quality` e confermare che **non** compaia alcun report
   `duplicate-code` (R0801) fra `TwitchStreamAdapter` e `MergingSourceAdapter`.

Trappole: non cambiare l'ordine dei canali né la policy di drop; il tipo di
`stats()` restituito deve restare compatibile con ciò che la TUI/osservabilità
già legge.

## Acceptance criteria

- [ ] `TwitchStreamAdapter` delega il merge a `MergingSourceAdapter`.
- [ ] Tutti i test Twitch preesistenti passano senza essere modificati.
- [ ] Nessun `duplicate-code`/R0801 fra i due moduli.
- [ ] La superficie pubblica di `TwitchStreamAdapter` è invariata.

## Blocked by

- Blocked by [01-merging-source-adapter.md](./01-merging-source-adapter.md)

## User stories addressed

- User story 11
