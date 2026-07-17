# Passaggio del repo a pubblico

## Type

Wayfinding spec

## Status

Active

## Destination

Il repository `minnarone` è pubblico su GitHub, con licenza chiara (MIT), nessun
segreto o contenuto sensibile nei file tracciati né nella history, README
accurato, e nessun file personale/accidentale tracciato. Un visitatore esterno
capisce cos'è il progetto, può installarlo e sa cosa può farne legalmente.

## Decisions So Far

- **Licenza MIT** — decisa dall'utente (sessione 2026-07-17). `LICENSE` creato e
  `pyproject.toml` aggiornato (`license = { text = "MIT" }`) sulla branch
  `chore/public-release-prep` (non ancora committato/mergiato).
- **Docs interni restano** — issue/ticket/prds/specs/adrs in `docs/` (96+ file)
  si pubblicano così come sono: mostrano il processo di sviluppo, nessun
  problema di sicurezza rilevato. Decisione utente.
- **Rimuovere solo la skill personale** — `.agents/skills/project-designer/SKILL.md`
  è tracciata per errore e va tolta dal repo. Decisione utente.
- **README verificato accurato** (sessione 2026-07-17): flag CLI (`--check`,
  `--tui`, `--replay`), extra pip, script console, link a docs/examples — tutto
  combacia col codice su `main` (la feature branch llamacpp è mergiata, diff
  contenuti vuoto).
- **Nessun segreto nella history**: `.env` mai committato (verificato con
  `git log --all -- .env`); grep di pattern segreti sui file tracciati trova
  solo placeholder (`oauth:dry_run`). Solo `.env.example` (template vuoto) è
  tracciato.

## Not Yet Specified

- **Screenshot in `docs/source/screenshots/`** (10 PNG, ~11 MB, tracciati):
  sono frame del video di enkk. Da chiarire: (a) contengono informazioni
  sensibili visibili (token, email, chat private)? (b) i diritti sui frame
  permettono la ripubblicazione? (c) tenerli, rimuoverli o ridurli?
- **Lingua del README/docs**: tutto in italiano. Per un repo pubblico va bene
  così o serve una versione inglese (almeno del README)? Decisione utente non
  ancora presa.
- **File untracked ambigui**: `wiki/` (clone della wiki?) e `.tokensave/` sono
  untracked ma non gitignorati — vanno aggiunti a `.gitignore` o gestiti.
- **Menzione della licenza nel README**: il README non menziona MIT; da
  aggiungere una riga/sezione.

## Out of Scope

- Traduzione completa della documentazione operativa (`docs/*.md`) in inglese.
- Pulizia o riscrittura dei docs interni (issue/ticket/prds) — restano com'è.
- Setup di CI pubblica, badge, CONTRIBUTING.md, code of conduct — nice-to-have
  post-pubblicazione, non bloccanti.
- Riscrittura della history git (i commit con email personale dell'autore sono
  accettati come normali).

## Frontier / Blocking Edges

- **Licenza non ancora su main**: LICENSE + pyproject sono su branch locale non
  committata. Blocca la pubblicazione. → ticket 01.
- **Screenshot non revisionati**: potrebbero contenere info sensibili o
  materiale di terzi; vanno guardati da un umano prima che diventino pubblici.
  → ticket 02 (grilling/human).
- **Lingua README non decisa**: se serve l'inglese, va fatto prima del flip a
  pubblico (prima impressione). → ticket 03 (grilling).
- **Pre-flight finale**: scan history con tool dedicato (es. gitleaks) e check
  file tracciati residui, come rete di sicurezza prima del flip. → ticket 04.
- **4 test rossi su main** (scoperti 2026-07-17, pre-esistenti al lavoro di
  release): chi clona il repo pubblico e lancia `pytest` vede subito 4 failure.
  Uno è un test docs stantio dal refresh README (PR #24), gli altri 3 sono da
  diagnosticare. → ticket 06.
- **Flip a pubblico**: azione GitHub irreversibile di fatto (issue/PR diventano
  pubblici). Va fatta per ultima, dopo che 01–04 e 06 sono chiusi. → ticket 05.

## Ticket Plan

- 01 — task — Finalizzare licenza MIT e pulizia file (LICENSE, pyproject,
  riga licenza nel README, rimozione `.agents/skills/`, gitignore per
  `wiki/`/`.tokensave/`) → PR su main mergiata.
- 02 — grilling — Revisione umana screenshot `docs/source/screenshots/`
  (sensibilità + diritti) → decisione registrata: tengo/rimuovo/riduco.
- 03 — grilling — Decidere lingua del README pubblico (italiano, inglese, o
  bilingue) → decisione registrata; eventuale ticket task derivato.
- 04 — task — Pre-flight di sicurezza: gitleaks (o equivalente) su tutta la
  history, verifica `git ls-files` per artifact residui → report pulito
  allegato/riassunto nella mappa.
- 05 — task — Flip visibilità GitHub a public + verifica post-flip (clone
  anonimo, link README funzionanti, pagina repo) → repo pubblico verificato.
- 06 — task — Sistemare i 4 test falliti su main (1 test docs stantio da
  PR #24 + 3 da diagnosticare) → `pytest` verde su main.

## Next Review

Dopo i ticket 01–04: rileggere questa mappa, confermare che tutte le voci in
"Not Yet Specified" sono risolte o spostate, e solo allora eseguire il ticket
05 (flip). Dopo il flip: verificare da sessione anonima che il repo sia
visibile, che i link relativi del README funzionino su GitHub e che non compaia
nulla di inatteso nelle issue/PR pubbliche.
