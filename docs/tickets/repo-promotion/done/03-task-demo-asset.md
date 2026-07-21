# 03 — Task: asset demo (GIF/clip del TUI o replay)

## Parent Spec

[repo-promotion-wayfinder.md](../../../specs/repo-promotion-wayfinder.md)

## Type

task

## Outcome

Un asset visivo di ~30 secondi che mostra Minnarone in azione (percezione
multimodale → reazione), riusabile in cima al README e nei post di lancio.

## Acceptance Criteria

- [x] Esiste un asset (GIF o mp4 breve) che mostra il loop percezione→reazione
      in modo comprensibile a chi non conosce il progetto.
- [x] Nessun dato sensibile o volto/username di terzi non già pubblico.
- [x] L'asset è nel repo (o linkato) e referenziato nel README.
- [x] Pesa abbastanza poco da caricarsi su GitHub (GIF < 10 MB o mp4 esterno).

## Blocked By

- None — può partire subito. La localizzazione inglese del runtime/TUI
  ([public-release/09](../../public-release/done/09-task-localize-cli-messages.md))
  è già mergiata su main (PR #43, 2026-07-19).
- Vincolo (non blocco): il run usato per la demo deve percepire contenuto in
  inglese (canale Twitch EN o meeting EN) e produrre reazioni in inglese
  (`commentator.language`, decisione autore 2026-07-21).

## Frontier

Su HN/Reddit la demo decide l'esito del post molto più del testo: senza asset
il lancio (06) parte zoppo.

## Work Plan

1. Scegliere lo scenario più mostrabile SENZA live reale: candidato forte è la
   **replay dashboard** (`python -m minnarone --replay <run_dir>`) su un run
   registrato, oppure il TUI live su una demo os_capture locale.
2. Registrare lo schermo del terminale (es. `asciinema` + `agg` per GIF, o OBS
   per mp4) su un run con eventi interessanti (chat + audio + reazione).
3. Ritagliare a ~30s, annotare se serve (frecce/didascalie minime).
4. Inserire nel README sotto la hero image; salvare il sorgente del run usato.

## Evidence to Capture

- L'asset stesso + il comando/run usato per produrlo (riproducibilità).

## Execution Record (2026-07-21)

- Asset: [`docs/assets/minnarone-tui-demo.gif`](../../../assets/minnarone-tui-demo.gif),
  referenziato sotto la hero di `README.md`.
- Sorgente locale: `Windows PowerShell 2026-07-21 20-04-44.mp4`, SHA-256
  `08fb57e70dce00f01fbe49a7703d6edbbf9c71022f78d89f5382ed368c36d537`.
- Taglio scelto: `00:01:16`–`00:01:46`. Il contesto inglese si aggiorna nei
  pannelli chat, trascrizione, video e memoria; circa 17 secondi dopo l'inizio
  del taglio compare una nuova reazione `[SHADOW]` nel pannello `MINNARONE`.
- Il bordo ciano evidenzia quel pannello per quattro secondi senza alterare il
  contenuto del TUI. La barra superiore del terminale è esclusa dal crop.
- Decisione autore: gli handle e i messaggi mostrati provengono dalla chat
  pubblica del canale Twitch registrato e sono accettati in questo asset; non
  sono presenti token, percorsi personali o dati non pubblici. Questa decisione
  deroga per il solo asset al divieto generale sui captured chat artifacts in
  `CONTRIBUTING.md`.

Comando riproducibile (FFmpeg):

```bash
SOURCE_VIDEO="/path/to/Windows PowerShell 2026-07-21 20-04-44.mp4"
ffmpeg -hide_banner -loglevel error -ss 76 -t 30 -i "$SOURCE_VIDEO" \
  -filter_complex "[0:v]crop=iw:ih-40:0:40,fps=3,scale=1440:-1:flags=lanczos,drawbox=x=952:y=281:w=468:h=232:color=cyan@0.95:t=4:enable='between(t,16,20)',split[s0][s1];[s0]palettegen=max_colors=96:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  -loop 0 docs/assets/minnarone-tui-demo.gif
```

Verifica: 30,000 s, 1440×761, 90 frame, 984.568 byte (0,98 MB), SHA-256
`e4d75d0b4a527afb2f6deb5d6cd5059f8fbf3baec11f7c918e52088fe077a945`.

## Out of Scope

- Video YouTube lungo o contenuto editoriale (ticket 07).
- Modifiche funzionali al TUI per "farlo sembrare meglio".
