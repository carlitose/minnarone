# 02 — Task: vetrina GitHub (description, topics, About, release)

## Parent Spec

[repo-promotion-wayfinder.md](../../specs/repo-promotion-wayfinder.md)

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
- [ ] Social preview image caricata (Settings → Social preview) — può essere
      la cover già nel repo (`docs/source/minnarone-cover.jpg`) o un asset del
      ticket 03; verificare i diritti d'uso della cover fuori dal contesto
      "credito nel README" prima di riusarla come preview.
- [ ] Valutata (e decisa) una release taggata v0.x con release notes brevi,
      così il repo non appare "senza versioni".
- [ ] Verifica da sessione anonima: la card del repo (link condiviso su
      X/Slack) mostra titolo, description e preview corretti.

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

## Out of Scope

- Modifiche al contenuto del README (già verificato accurato).
- Asset demo animato (ticket 03).
