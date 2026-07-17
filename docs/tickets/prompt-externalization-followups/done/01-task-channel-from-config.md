# 01 — Task: canale dal config (`twitch.channel` → PromptBuilder)

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Il prompt original-chat usa il canale configurato in `twitch.channel` invece del
default cablato "enkk". Bug attuale: con `channel: multiplayerit` in yaml, il
prompt continua a dire "nel canale di enkk" (`app.py:977,1016` non passa
`channel=` al `PromptBuilder`).

## Acceptance Criteria

- [ ] `app.py` passa `channel=config.twitch.channel` al `PromptBuilder` quando
      `config.twitch` è presente; default attuale (`_DEFAULT_CHANNEL`) solo se
      `twitch` è None (run non-Twitch).
- [ ] Con `channel: multiplayerit`, `rules.md`/`intro.md` rendono
      "multiplayerit" (test attraverso `PromptBuilder.build`/`stable_prefix`).
- [ ] Byte-invarianza: per una config fissa il prefisso stabile resta
      byte-identico fra i turni (il canale è dato di config, non per-turno).
- [ ] Documentazione (README sezione prompt) aggiornata: il canale viene da
      `twitch.channel`, non va editato nei file.
- [ ] Suite verde (`--ignore=tests/test_vlm.py` finché 05 non è fatto).

## Blocked By

- None — può partire subito (sul branch di PR #35 o su main post-merge).

## Frontier

È un bug visibile all'operatore (canale sbagliato nel prompt): il fix più
urgente e più piccolo del gruppo.

## Work Plan

1. RED: test che con un `TwitchConfig` fittizio con `channel="multiplayerit"` il
   prefisso stabile contenga "multiplayerit" e non "enkk".
2. GREEN: passare `channel=` nei due punti di costruzione in `app.py`.
3. Aggiornare README (nota su `twitch.channel`).

## Evidence to Capture

- Diff `app.py` + test.
- Prompt renderizzato con canale custom.

## Out of Scope

- Campo canale separato dalla sezione twitch (non serve: `twitch.channel` esiste).
- Header/lingua (ticket 03).
