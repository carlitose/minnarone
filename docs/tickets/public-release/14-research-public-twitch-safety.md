# Verificare policy e guardrail per un bot Twitch pubblico

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

research

## Outcome

Produrre una decisione evidence-backed su autorizzazione del canale, disclosure
AI, credenziali separate, retention e comportamento attended-only da rendere
parte del golden path pubblico.

## Acceptance Criteria

- [ ] Fonti primarie Twitch correnti coprono bot/chat, token/scope, rate limit e
      regole applicabili al caso d'uso.
- [ ] È esplicito cosa è requisito tecnico, policy di piattaforma o scelta etica
      del progetto.
- [ ] La posizione corrente `announce_ai`/non-disclosure è confrontata con le
      fonti e con il rischio di un repo pubblico.
- [ ] Sono definiti guardrail minimi per shadow/live, autorizzazione streamer,
      account bot dedicato, retention e kill-switch.
- [ ] Le decisioni confluiscono in una decision spec o nel parent spec e
      sbloccano i ticket 16–18.

## Blocked By

- None - può iniziare immediatamente.

## Frontier

Il runtime è tecnicamente capace di apparire umano e inviare messaggi reali.
Prima di trasformare questa capacità in un tutorial pubblico serve una posizione
verificata e non implicita.

## Work Plan

1. Consultare documentazione Twitch corrente e altri owner primari rilevanti.
2. Mappare policy esterne sui gate già presenti nel codice.
3. Evidenziare gap tra policy, README, `.env.example`, prompt e runtime.
4. Proporre decisioni minime e farle confermare all'utente quando normative o
   di prodotto.
5. Aggiornare mappa e acceptance criteria dei ticket dipendenti.

## Evidence to Capture

- URL e data delle fonti primarie.
- Gate correnti in config/app/public_send/live_tui.
- Decisioni dell'utente su disclosure e autorizzazione.

## Out of Scope

- Consulenza legale.
- Modifica immediata del runtime.
- Promozione live durante la ricerca.
