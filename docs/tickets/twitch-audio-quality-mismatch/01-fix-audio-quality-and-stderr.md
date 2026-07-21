# 01 — Fix: audio reader non deve ereditare la quality video; stderr di streamlink nell'errore

## Parent Spec

[twitch-audio-quality-mismatch.md](../../specs/twitch-audio-quality-mismatch.md)

## Type

task

## Outcome

Il canale audio Twitch non muore più quando `twitch.quality` non combacia con
i nomi delle rendition del canale, e quando una pipeline media fallisce
l'operatore vede l'errore reale di streamlink nel pannello EVENTS, non uno
status code nudo.

## Acceptance Criteria

- [ ] `TwitchStreamAdapter._build_readers` non inoltra più la quality video a
      `TwitchAudioReader`: l'audio usa `audio_only` (default del reader) o un
      nuovo knob `twitch.audio_quality` con default `audio_only`.
- [ ] Lo stderr di streamlink non è più `DEVNULL`: una coda limitata (es.
      ultime 1-3 righe) è inclusa nel messaggio dell'`OSError` sollevata in
      `twitch_media.py` (~riga 165).
- [ ] Il fallback silenzioso del video (`streams.get(quality) or
      streams.get("best")`, `twitch_video.py:91`) emette un log/evento quando
      scatta, indicando quality richiesta e quality effettiva.
- [ ] Unit test: `_build_readers` con `quality: 480p` costruisce l'audio
      reader con `audio_only`; il fallimento pipeline include lo stderr.
- [ ] `pytest` verde; nessuna modifica al comportamento del canale video a
      quality valida.

## Blocked By

- None — la diagnosi è confermata (spec Confirmed, triangolazione 3/3).

## Frontier

È il fix vero del bug che ha bloccato la demo del piano promozione; senza,
ogni utente pubblico con `quality` esplicita su un canale con ladder
fps-suffissata (la maggioranza) perde l'audio con un errore opaco.

## Work Plan

1. Modificare `_build_readers` (audio → `audio_only` / knob dedicato).
2. `AsyncioProcessRunner`: stderr a PIPE con lettura bounded; arricchire
   l'`OSError`.
3. Log del fallback in `twitch_video.py`.
4. Test unitari nuovi + aggiornare eventuali test esistenti sul wiring.
5. Verifica manuale col feedback loop `repro_audio.py` (canale live, quality
   inesistente → errore chiaro; default → PCM).

## Evidence to Capture

- Output del repro prima/dopo; testo dell'errore arricchito.

## Out of Scope

- Retry/backoff automatico della pipeline; risoluzione binari (ticket 03).
