## Parent Spec

[workstream-untangle-wayfinder.md](../../specs/workstream-untangle-wayfinder.md)

## Type

research

## Outcome

Una mappa definitiva, con evidenza, di: (a) quali commit appartengono a quale
filone (W1 os-capture, W2 twitch public-send, W3 profiles/meeting-synth, W4
diarizzazione, `.env`), e (b) l'attribuzione a livello file/hunk del commit
snapshot `14e7c9b` tra "refactor `profiles` (W3)" e "fix accettazione public-TUI
(W2)". Serve a rendere decidibile la strategia di split (ticket 02).

## Acceptance Criteria

- [ ] Tabella commit→filone per tutti i commit `main..wip` (già in parte nello
      spec; confermare e correggere).
- [ ] Per lo snapshot `14e7c9b`, per ogni file `src/` toccato: quali hunk sono
      profiles-refactor (W3) e quali sono fix public-TUI (W2), con evidenza
      (nomi di simboli/funzioni, non solo il file).
- [ ] Conferma della catena di dipendenze: cosa esattamente in W4 e nei fix
      public-TUI richiede lo schema `profiles` (citare simboli, es.
      `active_styles()`, `profiles`).
- [ ] Verifica se il branch pushato `autopilot/twitch-public-chat-output`
      (`3d531b7`, schema vecchio) compila/passa i test **senza** lo snapshot —
      cioè se W2 è davvero indipendente da W3 a `3d531b7`.
- [ ] Risultati salvati nella sezione Evidence dello spec wayfinder.

## Blocked By

- None - can start immediately.

## Frontier

È il primo edge: senza attribuzione fine dello snapshot, la decisione di
strategia (ticket 02) sarebbe alla cieca.

## Work Plan

1. `git log --oneline main..wip/profiles-refactor-and-tui-fixes` → confermare la
   classificazione per-filone nello spec.
2. Per lo snapshot: `git show 14e7c9b -- src/minnarone/config.py` (e app.py,
   shadow_router.py, output_sink.py, dashboard*.py) → per ogni hunk decidere
   W3-refactor vs W2-fix guardando i simboli toccati (es. `profiles`,
   `active_styles`, `MEETING_SYNTHESIZER` = W3; `_validate_public_twitch_persona`,
   il gate router `styles_to_build`, `echo` = W2-fix).
3. `git grep` di `active_styles`/`profiles` nei file di W4 e nei fix public-TUI
   per provare la dipendenza dallo schema.
4. Provare a costruire mentalmente/di fatto se `3d531b7` sta in piedi da solo
   (è già pushato; i suoi test passavano su schema vecchio — confermare).

## Evidence to Capture

- Tabella commit→filone.
- Mappa file/hunk→(W3|W2) dello snapshot.
- Elenco simboli di W4/fix che dipendono da `profiles`.
- Esito compile/test di `3d531b7` senza snapshot.

## Out of Scope

- Eseguire lo split (ticket 03).
- Decidere l'ordine di merge (ticket 02).
