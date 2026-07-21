# 02 — Task: vetrina GitHub (description, topics, About, release)

## Parent Spec

[repo-promotion-wayfinder.md](../../../specs/repo-promotion-wayfinder.md)

## Type

task

## Outcome

Chi arriva al repo da un link nudo capisce in 5 secondi cos'è: description e
topics compilati, social preview impostata, eventuale release v0.x taggata.

## Acceptance Criteria

- [x] Description GitHub compilata (fatto 2026-07-21: "Framework for AI
      agents that perceive live multimodal context (audio, video, chat) and
      react in real time - fully local").
- [x] Topics impostati (fatto 2026-07-21: `ai-agents`, `multimodal`,
      `twitch`, `llm`, `llamacpp`, `speech-recognition`,
      `speaker-diarization`, `python`).
- [x] Social preview image caricata (Settings → Social preview) — può essere
      la cover già nel repo (`docs/source/minnarone-cover.jpg`) o un asset del
      ticket 03; verificare i diritti d'uso della cover fuori dal contesto
      "credito nel README" prima di riusarla come preview.
- [x] Valutata (e decisa) una release taggata v0.x con release notes brevi,
      così il repo non appare "senza versioni".
- [x] Verifica da sessione anonima: i metadata usati dalle card X/Slack
      espongono titolo, description e preview corretti.

## Blocked By

- None — può partire subito (description e topics via
  `gh repo edit carlitose/minnarone --description ... --add-topic ...`).

## Frontier

Qualunque lancio spreca traffico finché la vetrina è vuota: è il quick win a
costo minimo con dipendenze zero.

## Work Plan

1. Scrivere 2-3 proposte di description e farle scegliere all'autore.
2. `gh repo edit` per description + topics; homepage → per ora il repo stesso
   o nessuna.
3. Social preview: scelta immagine (vedi criterio diritti) e upload manuale
   (non c'è API: Settings → General → Social preview).
4. Se deciso: `git tag v0.x` su release branch/main + `gh release create` con
   note sintetiche.
5. Verifica anonima della card e della pagina repo.

## Evidence to Capture

- Description e topics finali, screenshot della card di anteprima.

## Progress (2026-07-21)

- Release verificata: [`v0.1.0 — first public release`](https://github.com/carlitose/minnarone/releases/tag/v0.1.0),
  pubblicata il 2026-07-21 con release notes.
- Social preview pronta in
  [`docs/assets/minnarone-social-preview.jpg`](../../../assets/minnarone-social-preview.jpg):
  1280×640, 180.620 byte, SHA-256
  `478417b58b5c41c0fed472e072f7d38a582b8807283a5da6e66a7f5228c3aa1f`.
  È derivata dal demo asset del progetto invece che dalla cover di Enkk, così
  non introduce dubbi sui diritti di riuso della cover come card esterna.
- La preview rispetta la raccomandazione GitHub di 1280×640 ed è molto sotto il
  limite di 1 MB. Upload manuale completato dall'autore il 2026-07-21.
- Verifica anonima completata il 2026-07-21 sulla pagina pubblica del repo: il
  set Open Graph per Slack (`og:title`, `og:description`, `og:image`) e il set
  X (`twitter:card=summary_large_image`, `twitter:title`,
  `twitter:description`, `twitter:image`) espongono i dati corretti e la stessa
  immagine su `repository-images.githubusercontent.com`. Il file servito è un
  JPEG 1280×640 e il suo SHA-256 coincide con l'asset locale
  (`478417b58b5c41c0fed472e072f7d38a582b8807283a5da6e66a7f5228c3aa1f`).
- La preview è un derivato statico della GIF approvata nel ticket 03 e mostra
  lo stesso segmento di chat Twitch pubblica. L'upload manuale effettuato
  dall'autore conferma l'estensione a questa preview della deroga già registrata
  per l'asset demo rispetto al divieto generale di captured chat artifacts.

## Out of Scope

- Modifiche al contenuto del README (già verificato accurato).
- Asset demo animato (ticket 03).
