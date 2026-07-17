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

---

## Esito (2026-07-17) — CHIUSO

Suite completa verde: **1093 passed, 0 failed** (era 4 failed). Diagnosi e fix
per test:

1. `test_readme_private_commentator_wording_is_not_contradictory` — **test
   stantio**. Il refresh README (PR #24) ha rimosso il percorso "whisper v2";
   oggi `private` = solo console locale, nessun PRIVMSG. Test aggiornato ad
   ancore minime sul wording attuale (`sola **console locale**`, `messaggio
   pubblico viene mai inviato`) + guardia che il wording contraddittorio
   storico (`whisper v2`) non riappaia. Invariante preservata senza vincolare
   la prosa (utile per la traduzione EN del ticket 08).
2. `test_twitch_audio_runtime_writes_clustered_speaker_speech_perception` —
   **fix codice** in `asr.py`: `_faster_whisper_progress_disabled` ora usa
   `sys.modules.get("faster_whisper.transcribe")` invece di forzare un import
   pesante dentro il worker; se il modulo non è caricato (modello fake nei
   test) fa yield senza toccare tqdm. Comportamento reale invariato.
3. `test_cli_check_fails_for_live_send_without_write_token` (+ test live
   gemello) — **test non isolato**: la CLI ricarica `.env` dalla cwd, quindi un
   `.env` locale dell'operatore con `TWITCH_SEND_OAUTH_TOKEN` vanificava il
   `delenv`. Aggiunto `monkeypatch.chdir(tmp_path)`.
4. `test_audio_reader_stop_kills_process_that_ignores_terminate` —
   **test fragile su Windows**: `process_stop_timeout=0.01` sotto la risoluzione
   del timer (~15ms) faceva scadere l'attesa del pump cancellato prima che il
   pump venisse schedulato. Alzato a `0.1` solo in questo test (verifica il
   kill del processo, non la race sul pump — quella la copre il test sullo
   stdin close che si impianta, lasciato a 0.01). Codice `twitch_media.py`
   invariato.

ruff pulito sui file toccati. La modifica iniziale del subagent a
`twitch_media.py` (heuristica `if not pump.cancelled()`) è stata scartata:
rompeva il test gemello sullo stdin-close-hang perché non distingueva la race
benigna dal hang genuino.
