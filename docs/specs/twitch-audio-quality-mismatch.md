# Audio Twitch morto: quality video passata verbatim alla CLI di streamlink

## Type

Diagnostic spec

## Status

Confirmed — triangolazione a 3 diagnosi indipendenti (repro-first, data-flow,
recent-change), 2026-07-21: convergenza 3/3 sullo stesso meccanismo, tutte con
feedback loop deterministico. Confidenza alta.

## Symptom

Con `adapter: twitch` e `audio: true`, il canale audio muore all'avvio con
l'evento `audio/unknown: audio pipeline failed: streamlink exited with status 1`
e nessun transcript viene mai prodotto. Nello stesso run video e chat
funzionano. Osservato su Windows 11 con il canale `aryssa614` e
`twitch.quality: 480p`. Variante osservata a venv non attivato:
`[WinError 2] impossibile trovare il file specificato`.

## Root Cause

`TwitchStreamAdapter._build_readers` (`src/minnarone/twitch_stream.py:169-175`)
inoltra la `twitch.quality` della config — pensata per il video — anche a
`TwitchAudioReader`, sovrascrivendone il default `audio_only`
(`twitch_audio.py:50`). La pipeline audio la passa **verbatim alla CLI** di
streamlink (`twitch_media.py:80-87`: `streamlink --stdout <url> <quality>`),
che esige il nome esatto della rendition e non fa alcun fallback. I nomi delle
rendition sono per-canale (Twitch li suffissa con gli fps): la ladder di
`aryssa614` è `audio_only, 160p30, 360p30, 480p30, 720p60, 1080p60` — non
esiste `480p` → streamlink stampa su stderr "The specified stream(s) '480p'
could not be found" ed esce con status 1. L'errore azionabile non arriva mai
all'operatore perché entrambi i sottoprocessi girano con `stderr=DEVNULL`
(`twitch_media.py:45`); resta solo lo status code nudo.

Il video sopravvive alla stessa quality sbagliata perché attraversa un
boundary diverso: l'API Python di streamlink con fallback esplicito e
silenzioso `streams.get(quality) or streams.get("best")`
(`twitch_video.py:91`) — quindi nel run incriminato il video girava in realtà
a 1080p60 senza dirlo.

**Non è una regressione**: il plumbing `quality=quality` è identico dal commit
825c148 (2026-06-25) e streamlink è 8.4.0 in entrambi i venv (installato il
2026-07-07, prima delle run riuscite). Le run del 14-17/07 funzionavano perché
usavano `quality: best` (config twitch-commentator) o canali la cui ladder
esponeva letteralmente `480p`. La variante `[WinError 2]` è la stessa
fragilità un livello sotto: il processo viene lanciato col nome nudo
`streamlink`, risolvibile solo con gli Scripts del venv nel PATH.

## Evidence

- Ladder live del canale (streamlink 8.4.0): `audio_only, 160p30, 360p30,
  480p30, 720p60, 1080p60` — niente `480p`.
- Argv esatto della pipeline riprodotto standalone: exit 1 con
  `error: The specified stream(s) '480p' could not be found.`; con `480p30`
  streamma (2 MB in 12 s); con `audio_only` streamma indefinitamente.
- Repro end-to-end con la classe reale (`TwitchAudioReader`, ProactorEventLoop
  come nell'app): `quality='480p'` → `OSError: audio pipeline failed:
  streamlink exited with status 1` (byte-identico all'evento TUI);
  `'audio_only'` e `'480p30'` → chunk PCM da 32000 byte (1.0 s × 16 kHz ×
  2 B mono) — pipeline sana. Stesso script senza Scripts nel PATH →
  `[WinError 2]` byte-identico alla prima variante.
- Delta di codice escluso: `git log -S 'quality=quality'` — invariato da
  825c148; solo commit di formattazione/localizzazione sui file media da
  giugno. Delta di versione escluso: streamlink 8.4.0 in entrambi i venv,
  uv.lock invariato per streamlink dal 2026-06-29.

## Options Considered (alternative escluse dalla triangolazione)

- Quirk subprocess di Textual/asyncio su Windows — escluso: stesso event loop
  e stesso path `create_subprocess_exec` streammano PCM corretto con quality
  valida; il fallimento riproduce anche in shell pura senza asyncio.
- ffmpeg 8.1.2 (WinGet) rotto/incompatibile — escluso: streamlink esce prima
  di scrivere un byte; ffmpeg produce PCM corretto nei run verdi.
- Sessioni streamlink concorrenti audio+video / rate limiting Twitch —
  escluso: la pipeline audio da sola fallisce con `480p` e va con `480p30`.
- Canale offline / rete / auth — escluso: video e chat vivi nello stesso run,
  audio streamma manualmente.
- Regressione di codice o dipendenze rispetto al 14-17/07 — esclusa (vedi
  Root Cause).
- Hiccup transitorio di Twitch — escluso: deterministico a ogni invocazione.

## Decision / Solution

1. **Fix semantico** (`twitch_stream.py` `_build_readers`): non inoltrare la
   quality video al reader audio — lasciare il default `audio_only` (che su
   Twitch esiste sempre quando esistono le transcodes) o introdurre un knob
   `twitch.audio_quality` separato con default `audio_only`. Scaricare un mux
   video 480p per buttare il video (`-vn`) e downmixare a 16 kHz mono è solo
   banda sprecata.
2. **Fix di diagnosticabilità** (`twitch_media.py`): non scartare lo stderr di
   streamlink — catturarne una coda limitata e includerla nell'`OSError` di
   riga ~165, così "could not be found / Available streams: ..." arriva al
   pannello EVENTS. Loggare anche il fallback silenzioso del video da quality
   configurata a `best` (`twitch_video.py:91`), che oggi maschera errori di
   config.
3. **Robustezza opzionale**: la CLI di streamlink accetta una lista di
   priorità separata da virgole (`"480p,480p30,best"`) — zero codice extra se
   si vuole onorare una quality configurata con fallback; e risolvere
   l'eseguibile via `shutil.which` per dare un errore chiaro nella variante
   WinError 2.

Workaround operatore senza codice: `quality: best` (o il nome esatto della
rendition del canale, es. `480p30` — ma è per-canale e si rompe altrove).

## Testing Decisions

Feedback loop riusabile: `scratchpad/repro_audio.py` (sessione 2026-07-21)
guida il vero `TwitchAudioReader` senza TUI/LLM/ASR contro un canale live con
una lista di quality; rosso→verde deterministico in ~30 s. Per i test di
regressione: unit test su `_build_readers` (l'audio reader non deve ricevere
la quality video) e su `AsyncioProcessRunner` (stderr incluso nell'errore).

## Follow-ups

Ticket in `docs/tickets/twitch-audio-quality-mismatch/`:

- 01 — fix quality audio + stderr in errore (+ log del fallback video).
- 02 — completare `examples/prompts-en` con `summarizer.md` e `format.md`
  (scoperto nella stessa sessione demo: `prompts_dir` è override per-file e i
  mancanti ricadono sui default italiani → run "inglesi" con riassunti e
  formato italiani).
- 03 — `--check` verifica la presenza dei binari esterni (`streamlink`,
  `ffmpeg`) quando audio/video sono attivi (avrebbe catturato la variante
  WinError 2 in dry-run).
