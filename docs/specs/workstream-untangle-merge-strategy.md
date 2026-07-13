# Strategia di merge/split dei filoni impilati — decisione

## Type

Decision spec

## Status

Accepted — Opzione **C (ibrido)**, ordine di merge **W1 → W2 → W3 → W4** (ENV
quando comodo). Deciso dall'utente (ticket 02).

## Problem / Context

Quattro filoni sono impilati linearmente su `wip/profiles-refactor-and-tui-fixes`
sopra `main` (`f1ddf86`), nessuno mergiato: W1 os-capture, W2 twitch public-send
(pushato a `3d531b7`), W3 profiles/meeting-synth (blob unico `14e7c9b`), W4
diarizzazione, più il loader `.env`. Serve decidere **come portarli a main** in
PR pulite senza perdere lavoro. Vedi
[workstream-untangle-wayfinder.md](./workstream-untangle-wayfinder.md) per la
mappa e l'evidenza (ticket 01).

Vincoli emersi dall'analisi:
- W2 (`3d531b7`) è **già pushato** e auto-consistente su **schema vecchio**
  (`enabled/style`), ma **privo** dei fix di accettazione public-TUI.
- W3 è la **migrazione di schema** (`profiles`) ed è un **commit unico**; mescola
  in `config.py`/`app.py` i fix public-TUI, scritti sullo schema nuovo.
- W4 dipende da W3 solo in modo **stretto** (enum `SUGGESTER` + `_build_suggester`).

## Options Considered

### Opzione A — Spedire lo stack lineare così com'è
PR impilate nell'ordine dei commit esistenti: W1 → W2 → W3(snapshot) → W4 (+ENV).
- **Pro**: zero rischio di perdere lavoro; nessuna chirurgia git; già tutto verde.
- **Contro**: W3 resta un blob unico (storia illeggibile per la meeting-synth);
  i fix public-TUI restano "dentro W3" invece che con W2.

### Opzione B — Ricostruire la storia pulita di W3
Spacchettare lo snapshot nei 14 ticket meeting-synth + spostare i 2 file W2-fix
puri in W2 e i pezzi misti dove serve.
- **Pro**: storia git pulita e per-ticket.
- **Contro**: molto lavoro e rischio; i 2 file misti (`config.py`/`app.py`) non
  sono separabili in blocco (i fix sono scritti sullo schema nuovo).

### Opzione C — Ibrido (consigliata)
- W1 e `.env`: PR piccole e pulite subito (indipendenti).
- W2: mergiare il branch già pushato **così com'è** (schema vecchio, senza i
  fix public-TUI).
- W3: **una** PR "profiles refactor + public-TUI acceptance fixes" — squash
  coerente (non per-ticket), che è anche la migrazione di schema. Spostare i 2
  file W2-fix **puri** (`shadow_router.py` echo, `output_sink.py` last_decision)
  concettualmente sotto W2/W3 come preferito; i pezzi misti restano in W3.
- W4: rebase su W3 (accoppiamento stretto → facile).
- **Pro**: buon compromesso storia/tempo; niente lavoro perso; ogni PR compila.
- **Contro**: W3 non è per-ticket (ma è un unico refactor coeso, accettabile).

## Decision / Solution

**DECISO (utente): Opzione C, ordine W1 → W2 → W3 → W4** (+ENV quando comodo).
W3 va come **una PR coesa** (refactor `profiles` + fix public-TUI), non per-ticket.
I fix public-TUI puri (echo, last_decision) restano con W3 (coesi con la
migrazione di schema su cui sono scritti). L'esecuzione (creazione branch/PR) è
il ticket 03 — richiede un via libera esplicito prima di aprire PR (auto-deploy
su merge a main).

## Testing Decisions

Per ogni branch/PR ricostruito: `uv run pytest` (3 flaky noti deselezionati) +
`uv run ruff check src/minnarone/` verdi prima di aprire la PR. Nessun
auto-merge (il repo auto-deploya su merge a main).

## Open Questions

- Il verdetto "W2@3d531b7 auto-consistente" è da evidenza statica; se si sceglie
  A/C, confermare con un `git worktree` + `pytest` prima del merge.
