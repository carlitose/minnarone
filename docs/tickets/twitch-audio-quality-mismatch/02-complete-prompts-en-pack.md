# 02 — Completare examples/prompts-en (summarizer.md + format.md)

## Parent Spec

[twitch-audio-quality-mismatch.md](../../specs/twitch-audio-quality-mismatch.md)
(scoperto nella stessa sessione demo 2026-07-21 — vedi Follow-ups)

## Type

task

## Outcome

Chi punta `prompts_dir` a `examples/prompts-en` ottiene un run interamente in
inglese. Oggi il pack copre solo intro/rules/situations/headers: `prompts_dir`
è un override per-file e i file mancanti ricadono sui default impacchettati in
italiano — quindi `summarizer.md` (che dice letteralmente "riassunto breve in
italiano") produce MEMORY in italiano e `format.md` dà le istruzioni di
formato in italiano, trascinando anche le risposte del reactor.

## Acceptance Criteria

- [ ] `examples/prompts-en/summarizer.md` e `examples/prompts-en/format.md`
      esistono, in inglese, con chiavi di sezione e token di controllo
      (`RE:`, `MSG:`, `#end_conv`, nomi `## label_*`) IDENTICI ai default
      impacchettati (traduzione già collaudata nella sessione demo:
      `.local/demo-en/prompts/` sulla macchina dell'autore).
- [ ] `minnarone validate-prompts --prompts-dir examples/prompts-en` passa e
      non segnala più file original-chat/summarizer mancanti dal pack.
- [ ] `examples/prompts-en/README.md` aggiornato (elenco file coperti e nota
      sul comportamento per-file dell'override).
- [ ] Test/`pytest` verdi (incluso l'eventuale contratto docs).

## Blocked By

- None — indipendente.

## Frontier

Prerequisito di qualità per il lancio pubblico: i primi utenti da HN/Reddit
seguiranno il README verso prompts-en e oggi otterrebbero output misto
italiano/inglese.

## Work Plan

1. Portare i due file già tradotti e collaudati nella demo dentro
   `examples/prompts-en/`.
2. `validate-prompts` + run breve di verifica.
3. Aggiornare il README del pack.

## Evidence to Capture

- Output di `validate-prompts` (override completo, nessun default IT residuo
  per i set original-chat e summarizer).

## Out of Scope

- Tradurre i prompt dei profili Teams (`operator`, `meeting_synthesizer`,
  `suggester`) — altro pack, altra utenza.
