# Correggere drift e attriti scoperti nella prova operatore

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

Runtime, example e guide concordano sul percorso Twitch corrente; gli smoke
sono utilizzabili con `.env` e distinguono un canale quieto da un guasto media.

## Acceptance Criteria

- [ ] Gli smoke Twitch adottano una strategia `.env` coerente con la CLI o la
      differenza è esplicita e testata.
- [ ] Zero eventi chat in una finestra breve non invalida automaticamente audio
      e video riusciti senza una modalità strict esplicita.
- [ ] `docs/twitch-operator.md` non usa più `commentator.enabled` e descrive
      correttamente il token write: richiesto per `live`, non per `shadow`.
- [ ] Examples e README concordano sulla stessa semantica shadow/live e sui
      tasti TUI.
- [ ] Default/override Grok e parametri (`thinking`/`reasoning_effort`) hanno una
      policy corrente, documentata e coperta da test.
- [ ] Test mirati, quality e smoke offline passano.

## Blocked By

- [12-research-first-operator-journey.md](done/12-research-first-operator-journey.md) — done
- [14-research-public-twitch-safety.md](14-research-public-twitch-safety.md)
- [15-research-runtime-model-profiles.md](15-research-runtime-model-profiles.md)

## Frontier

Questi problemi rendono un tutorial accurato oggi ma falso domani. Correggerli
prima del ticket README evita di documentare workaround (`source .env`) o
contratti già smentiti dal codice.

## Work Plan

1. Convertire la matrice del ticket 12 in casi di test riproducibili.
2. Allineare dotenv e semantica di successo degli smoke.
3. Aggiornare schema/commentator e shadow/live in guide/examples.
4. Decidere e applicare model slug/parameter handling coerente.
5. Eseguire test, quality e smoke bounded.

## Evidence to Capture

- Test rossi/verdi per ogni drift.
- Diff codice/docs/examples.
- Output smoke con chat quieta e media riusciti.

## Out of Scope

- Download automatico modelli (ticket 15/16).
- Catalogo skill e riscrittura README (ticket 17).
- Promozione live durante i test automatici.
