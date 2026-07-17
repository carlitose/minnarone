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
- **Screenshot: si tengono tutti** (grilling 02, 2026-07-17). Revisione
  assistita dei 10 PNG: nessun segreto/credenziale visibile; contengono volti
  (enkk) e username Twitch di terzi già pubblici nel video di origine. Il
  "match binario" del grep era un falso positivo (pagina OpenRouter). Uso
  documentale con credito prominente nel README.
- **Enkk non è stato interpellato: rischio accettato** (grilling 02,
  2026-07-17). Assunzione registrata: il video di origine è pubblico, il
  credito è prominente nel README, l'idea è generalizzata in codice originale.
  Se enkk dovesse obiettare dopo il flip, si rimuove il materiale su richiesta.
- **README pubblico in inglese + README.it.md** (grilling 03, 2026-07-17):
  README principale tradotto in inglese per il pubblico globale, versione
  italiana conservata come `README.it.md` con link incrociati. → ticket 08.
- **Pre-flight sicurezza pulito** (ticket 04, 2026-07-17): gitleaks 8.30.1 su
  tutta la history (`git --log-opts=--all`) → **"no leaks found"**, 96 commit,
  3.11 MB scansionati. Review `git ls-files`: nessun `.log`/`.env`/`.key`/dump
  tracciato (solo `.env.example`). Rimosso `skills-lock.json` (artefatto orfano
  di Claude Code che puntava alla skill `project-designer` già rimossa nel
  ticket 01) e aggiunto a `.gitignore`.
- **Extra utente (2026-07-17)**: hero image dalla copertina del video di enkk
  (`docs/source/minnarone-cover.jpg`) in cima ai due README; sezione "offrimi
  un caffè" con link PayPal (`https://paypal.me/CarloSergi`). Entrambi committati
  sulla branch/PR del ticket 08.

## Not Yet Specified

- (vuoto — le voci precedenti sono risolte: screenshot → si tengono, lingua
  README → inglese + README.it.md (ticket 08), gitignore e riga licenza →
  fatti nel ticket 01 / PR #26.)

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
- ~~Screenshot non revisionati~~: risolto (grilling 02 chiuso: si tengono).
- ~~Lingua README non decisa~~: risolto (grilling 03 chiuso: inglese +
  README.it.md). La traduzione è ora il ticket 08 e va fatta prima del flip
  (prima impressione).
- **Pre-flight finale**: scan history con tool dedicato (es. gitleaks) e check
  file tracciati residui, come rete di sicurezza prima del flip. → ticket 04.
- **4 test rossi su main** (scoperti 2026-07-17, pre-esistenti al lavoro di
  release): chi clona il repo pubblico e lancia `pytest` vede subito 4 failure.
  Uno è un test docs stantio dal refresh README (PR #24), gli altri 3 sono da
  diagnosticare. → ticket 06.
- **Nessuna verifica da installazione pulita**: il README è verificato "sulla
  carta" ma nessuno ha rifatto di recente il percorso utente-nuovo (clone →
  venv pulito → install → avvio modalità) seguendo SOLO il README. → ticket 07.
- **Flip a pubblico**: azione GitHub irreversibile di fatto (issue/PR diventano
  pubblici). Va fatta per ultima, dopo che 01–04, 06 e 07 sono chiusi. → ticket 05.

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
- 07 — task — Verifica da installazione pulita seguendo SOLO il README (clone
  fresco, venv nuovo, extra, `--check` su tutti gli examples, avvio modalità
  fattibili, smoke CLI, replay) → gap README↔realtà registrati e risolti.
- 08 — task — Tradurre il README in inglese (README.md) conservando l'italiano
  come README.it.md con link incrociati → README pubblico in inglese.

## Next Review

Dopo i ticket 01–04: rileggere questa mappa, confermare che tutte le voci in
"Not Yet Specified" sono risolte o spostate, e solo allora eseguire il ticket
05 (flip). Dopo il flip: verificare da sessione anonima che il repo sia
visibile, che i link relativi del README funzionino su GitHub e che non compaia
nulla di inatteso nelle issue/PR pubbliche.
