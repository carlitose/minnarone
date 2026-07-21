# 03 — `--check` verifica i binari esterni (streamlink, ffmpeg)

## Parent Spec

[twitch-audio-quality-mismatch.md](../../specs/twitch-audio-quality-mismatch.md)

## Type

task

## Outcome

`python -m minnarone <config> --check` fallisce con un errore azionabile se i
binari esterni richiesti dai canali attivi (`streamlink`, `ffmpeg` per
audio/video Twitch) non sono risolvibili nel PATH — restando dry-run e senza
rete. Avrebbe catturato la variante `[WinError 2]` della sessione demo
(venv non attivato → `streamlink` introvabile solo a runtime).

## Acceptance Criteria

- [ ] Con `twitch.audio: true` o `twitch.video: true` (pipeline subprocess),
      `--check` verifica `shutil.which("streamlink")` e
      `shutil.which("ffmpeg")` e in caso di assenza fallisce con messaggio
      che nomina il binario mancante e suggerisce venv/PATH.
- [ ] Nessuna verifica di rete aggiunta: `--check` resta offline.
- [ ] Canali che non usano subprocess non scatenano la verifica.
- [ ] Unit test per presenza/assenza binario (monkeypatch di `shutil.which`).
- [ ] `pytest` verde; README aggiornato se documenta cosa copre `--check`.

## Blocked By

- None — indipendente (componibile col ticket 01 nello stesso PR se comodo).

## Frontier

Chiude il gap "il check non se ne accorge" emerso in sessione: oggi il
dry-run valida config/modelli/prompt ma non l'esistenza dei processi esterni
che il loop live lancerà.

## Work Plan

1. Individuare il punto del build/`--check` dove i reader dichiarano le
   dipendenze da binari (o aggiungere una hook di preflight per adapter).
2. Implementare la verifica con `shutil.which` + messaggio azionabile.
3. Test unitari; prova manuale con venv non attivato.

## Evidence to Capture

- Output di `--check` con e senza binari nel PATH.

## Out of Scope

- Health-check di rete (llama-server, Twitch) in `--check`; retry runtime.
