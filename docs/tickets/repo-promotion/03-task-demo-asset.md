# 03 — Task: asset demo (GIF/clip del TUI o replay)

## Parent Spec

[repo-promotion-wayfinder.md](../../specs/repo-promotion-wayfinder.md)

## Type

task

## Outcome

Un asset visivo di ~30 secondi che mostra Minnarone in azione (percezione
multimodale → reazione), riusabile in cima al README e nei post di lancio.

## Acceptance Criteria

- [ ] Esiste un asset (GIF o mp4 breve) che mostra il loop percezione→reazione
      in modo comprensibile a chi non conosce il progetto.
- [ ] Nessun dato sensibile o volto/username di terzi non già pubblico.
- [ ] L'asset è nel repo (o linkato) e referenziato nel README.
- [ ] Pesa abbastanza poco da caricarsi su GitHub (GIF < 10 MB o mp4 esterno).

## Blocked By

- None — può partire subito. La localizzazione inglese del runtime/TUI
  ([public-release/09](../public-release/done/09-task-localize-cli-messages.md))
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

## Out of Scope

- Video YouTube lungo o contenuto editoriale (ticket 07).
- Modifiche funzionali al TUI per "farlo sembrare meglio".
