# Districare i filoni impilati verso main — Wayfinder

## Type

Wayfinding spec

## Status

Active

## Destination

Tutto il lavoro in volo arriva su `main` tramite PR **pulite, revisionabili e
nell'ordine giusto**, senza perdere né la feature meeting-synth/suggester, né i
fix di diarizzazione e public-send, e con lo schema config (`profiles`)
unificato. Nessuna esecuzione del merge finale finché la strategia non è decisa
(gate umano).

## Decisions So Far

Ricostruzione della storia (branch `wip/profiles-refactor-and-tui-fixes`, base
`main` = `f1ddf86`). Quattro filoni **impilati linearmente**, nessuno su main:

- **W1 — OS-capture / Teams commentator**: commit puliti per-issue
  `5a3cf80 → 6d8dbdb` (+ VLM/preset `9ff16ed..73a30c0`). Cattura Teams via
  screen/audio OS. È la base su cui poggia W3.
- **W2 — Twitch public-send** (PRD public chat output): commit puliti per-issue
  `08c5af9 → 3d531b7`, **impilati sopra W1**. Branch `autopilot/twitch-public-chat-output`
  è **pushato** e fermo a `3d531b7` (schema vecchio `enabled/style`,
  auto-consistente). Issue 01–09 done; 10–11 HITL.
- **W3 — meeting-synth + suggester** (refactor `profiles`): **un unico commit
  snapshot** `14e7c9b`. Contiene il refactor `commentator.enabled/style →
  profiles` con stili `MEETING_SYNTHESIZER`/`SUGGESTER`, prompt per-profilo,
  trigger-mode del senser, sentinel `#nothing`, multi-reactor, pannelli TUI
  per-profilo. **14/15 ticket in `done/`**; manca il 15 (HITL live acceptance).
  ⚠️ Lo snapshot **mescola** anche i fix di accettazione public-TUI (validazione
  persona `original_chat`, routing pannello public+TUI, flag `echo`) negli stessi
  file (`config.py`, `app.py`, `shadow_router.py`, `output_sink.py`, `dashboard*`).
- **W4 — diarizzazione** (spec + ticket): commit puliti per-ticket
  `12af75c → 0d8a19b`. **Dipende dallo schema `profiles` di W3** (usa
  `active_styles()`/profiles). Ticket 01–04 done; 05 HITL.
- **`.env` loader** `3988989`: piccolo, quasi indipendente.

Fatto chiave: **W3 è la chiave di volta dello schema**. W4 e i fix public-TUI
non compilano senza `profiles`. Il branch W2 pushato è invece su schema vecchio e
**gli mancano i fix di accettazione public-TUI** (intrappolati nel blob W3).

## Evidence (ticket 01 — attribuzione, read-only)

Storia **lineare**, padre di `14e7c9b` = `3d531b7`. Classificazione confermata:
W1 `5a3cf80→6d8dbdb` (+VLM `9ff16ed..73a30c0`), W2 `08c5af9→3d531b7`, W3 = **solo**
`14e7c9b`, W4 `12af75c→0d8a19b`, ENV `3988989`. (I due commit-cerniera
`92d0637`/`443e1cf` sono solo-docs; `92d0637` è il kickoff PRD di W2.)

**Attribuzione dello snapshot `14e7c9b` (12 file src):**
- **8 file W3 puri**: `__init__.py`, `output.py` (enum MEETING_SYNTHESIZER/SUGGESTER),
  `prompt.py` (+142: template synth/suggester, sentinel `#nothing`), `senser.py`
  (+66: trigger_mode periodic/on_perception), `reactor.py` (+11: `#nothing`),
  `dashboard.py`/`dashboard_tui.py`/`dashboard_health.py` (pannelli per-profilo).
- **2 file W2-fix puri**: `shadow_router.py` (flag `echo`+`_display`),
  `output_sink.py` (property `last_decision` delegante sul wrapper TUI).
- **2 file MISTI (non separabili in blocco)**: `config.py` (refactor `profiles`
  **+** `_validate_public_twitch_persona`) e `app.py` (multi-reactor **+** gate
  routing `styles_to_build` e param `echo`). I pezzi W2-fix qui sono **scritti
  contro lo schema `profiles`** (chiamano `active_styles()`), quindi non
  cherry-pickabili sullo schema vecchio senza riscrittura.

**Dipendenza W4→W3 = NARROW (correzione allo spec):** i file core di
diarizzazione (`speaker.py`, `audio.py`, `speaker_commands.py`, `live_tui.py`,
`run_events.py`) **non** referenziano `profiles`/`active_styles` (0 hit da
`git grep`). L'unico accoppiamento passa per l'enum `CommentatorStyle.SUGGESTER`
+ il metodo `_build_suggester` toccati dal commit `6e28fa3` e dal suo test
`test_prompt_builder.py`. Gran parte di W4 sarebbe rebasabile su schema vecchio
con una piccola modifica al solo tocco suggester.

**W2 a `3d531b7` auto-consistente senza lo snapshot = SÌ** (evidenza statica:
schema vecchio `enabled/style`, nessun `profiles`/`active_styles`/`echo`, enum
senza MEETING/SUGGESTER; tutti i simboli referenziati esistono nel suo albero).
Cautela: test non eseguiti (task read-only, nessun checkout). I fix di
accettazione public-TUI **non ci sono** a `3d531b7` — sono nel blob `14e7c9b`.

## Not Yet Specified

- **Ordine di merge / strategia PR**: W3-come-fondazione-prima (poi W2 rifatto su
  `profiles`, poi W4) vs W2-prima-poi-migrazione-a-`profiles` in W3. Trade-off
  reali (W2 è già pushato su schema vecchio).
- **Come dare a W3 una storia pulita**: ora è un blob unico; accettabile come
  singolo commit "profiles refactor" oppure spacchettato per-ticket?
- **Dove vanno i fix di accettazione public-TUI**: concettualmente sono W2, ma
  scritti sullo schema `profiles` di W3.
- **W1+W2 restano impilati** in una PR unica o si separano?
- **`.env` loader**: PR a sé o dentro una delle altre?

## Out of Scope

- Rifare il lavoro di feature; nuove feature.
- Eseguire le run di accettazione HITL (W2 issue 10–11, W3 ticket 15, W4 ticket
  05): tracciate, non eseguite qui.
- Il merge effettivo su main (gate umano, dopo la decisione di strategia).

## Frontier / Blocking Edges

- **E1 — Attribuzione dello snapshot `14e7c9b`** (research): separare a livello
  file/hunk "refactor `profiles` (W3)" da "fix accettazione public-TUI (W2)".
  Gran parte già emersa in conversazione; va finalizzata e scritta. → ticket 01.
- **E2 — Decisione ordine di merge + strategia PR** (grilling, gate umano):
  scegliere tra W3-fondazione vs W2-prima, e come gestire il branch W2 già
  pushato. Da registrare come decision spec. → ticket 02. Blocca E3.
- **E3 — Ricostruzione storia pulita / creazione branch-PR** (task): eseguire lo
  split secondo la decisione. Bloccato da E1 + E2. → ticket 03 (solo su richiesta
  esplicita di esecuzione).
- **E4 — Accettazione live meeting-synth** (HITL): già tracciata in
  `docs/issues/meeting-synthesizer-and-suggester/15-hitl-live-meeting-acceptance.md`.
  Non duplicare.

## Ticket Plan

- **01 research** — Mappa dipendenze definitiva + attribuzione snapshot `14e7c9b`.
  Output: tabella file→filone e conferma della catena di dipendenze.
- **02 grilling** — Decidere ordine di merge e strategia PR; registrare decision
  spec. Gate umano.
- **03 task** — Eseguire lo split in branch/PR secondo la decisione (bloccato da
  01+02; NON eseguire senza ok esplicito).

## Next Review

Dopo 01+02: rileggere la decision spec di strategia, verificare che l'ordine di
merge non generi conflitti irrisolvibili su `config.py`/`app.py`, e solo allora
autorizzare 03.
