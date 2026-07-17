# Sistemare i 4 test falliti su main

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

La suite test è verde su `main` (`pytest`: 0 failed). I 4 fallimenti
pre-esistenti — verificati il 2026-07-17 su main pulito, non causati dal lavoro
di release — sono diagnosticati e risolti, decidendo caso per caso se
aggiornare il test o il codice/docs.

Fallimenti noti:

1. `tests/test_twitch_operator_docs.py::test_readme_private_commentator_wording_is_not_contradictory`
   — cerca la stringa `private+commentator = console locale` nel README, che il
   refresh del README (PR #24) ha rimosso. Probabile fix: aggiornare il test al
   wording attuale (o reintrodurre il wording se il vincolo è ancora voluto).
2. `tests/test_app.py::test_twitch_audio_runtime_writes_clustered_speaker_speech_perception`
3. `tests/test_cli.py::test_cli_check_fails_for_live_send_without_write_token`
4. `tests/test_twitch_audio.py::test_audio_reader_stop_kills_process_that_ignores_terminate`
   — cause non ancora diagnosticate (2–4); possibile drift da merge recenti o
   dipendenza dall'ambiente Windows.

## Acceptance Criteria

- [ ] Ogni fallimento ha una diagnosi: regressione reale, test stantio, o
      dipendenza d'ambiente.
- [ ] Fix applicati con la scelta giusta per ciascuno (test vs codice/docs),
      senza indebolire i vincoli che i test proteggono.
- [ ] `pytest` completo verde in locale.
- [ ] PR mergiata su main.

## Blocked By

- None - can start immediately (indipendente dal ticket 01).

## Frontier

Test rossi su main sono un pessimo biglietto da visita per un repo pubblico:
chi clona e lancia `pytest` vede subito 4 failure. Gate di qualità prima del
flip (il ticket 05 ora dipende anche da questo).

## Work Plan

1. Riprodurre i 4 fallimenti su main pulito (`pytest <i 4 test>`).
2. Diagnosticare uno per uno (leggere test + codice + storia recente dei merge:
   PR #21 diarizzazione, #24 README, #25 llamacpp sono i sospetti).
3. Applicare i fix; rilanciare la suite completa.
4. PR su main, merge.

## Evidence to Capture

- Diagnosi per ciascun test (test stantio vs regressione).
- Output pytest verde finale.

## Out of Scope

- Aggiungere CI (nice-to-have post-pubblicazione).
- Refactor dei test non coinvolti.
