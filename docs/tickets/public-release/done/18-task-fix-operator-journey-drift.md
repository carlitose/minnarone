# Correggere drift e attriti scoperti nella prova operatore

## Parent Spec

[public-release-wayfinder.md](../../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

Runtime, example e guide concordano sul percorso Twitch corrente; gli smoke
sono utilizzabili con `.env` e distinguono un canale quieto da un guasto media.

## Acceptance Criteria

- [x] Gli smoke Twitch adottano una strategia `.env` coerente con la CLI o la
      differenza è esplicita e testata.
- [x] Zero eventi chat in una finestra breve non invalida automaticamente audio
      e video riusciti senza una modalità strict esplicita.
- [x] `docs/twitch-operator.md` non usa più `commentator.enabled` e descrive
      correttamente il token write: richiesto per `live`, non per `shadow`.
- [x] Examples e README concordano sulla stessa semantica shadow/live e sui
      tasti TUI.
- [x] Default/override Grok e parametri (`thinking`/`reasoning_effort`) hanno una
      policy corrente, documentata e coperta da test.
- [x] Il percorso live valida account, scope e scadenza dei token all'avvio e
      ogni ora, fallendo verso shadow/stop su revoca, `401` o mismatch.
- [x] `announce_ai` governa davvero `ORIGINAL_CHAT`, oppure il flag è
      documentato come non supportato senza imporre una falsa negazione.
- [x] L'inerzia di `retention.perceptions_days` è visibile e il percorso
      documenta artifact, cancellazione manuale e opt-out finché manca enforcement.
- [x] Guida ed examples migrano la raccomandazione speaker italiana da CAM++
      zh-cn 192-dim a English VoxCeleb 512-dim con soglia iniziale 0.5.
- [x] Test mirati, quality e smoke offline passano.

## Blocked By

- [12-research-first-operator-journey.md](12-research-first-operator-journey.md) — done
- [14-research-public-twitch-safety.md](14-research-public-twitch-safety.md) — done
- [15-research-runtime-model-profiles.md](15-research-runtime-model-profiles.md) — done

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

## Progress

- 2026-07-19 — completato l'allineamento end-to-end: dotenv condiviso, smoke
  quiet/strict, schema e guide correnti, Grok 4.5/permaslug e reasoning policy,
  disclosure veritiera, retention esplicita, speaker VoxCeleb 512-dim e
  validazione OAuth startup/deadline con fallback read-stop/send-shadow.
- Verifica finale: **1261 test full-suite passati**, `make quality` verde, due
  review complete con relativi fix loop e simulazione QA offline finale verde;
  nessuna chiamata Twitch live, credenziale reale o download modello.
- Note non bloccanti emerse dalla review finale: dopo una sospensione multi-ora
  lo scheduler recupera immediatamente le deadline perse ma non le coalesca
  ancora in un singolo controllo; inoltre il disarmo auth usa oggi il motivo
  osservabile `kill_switch` e lo snapshot non espone un campo/reason dedicato
  `auth_disabled`. Entrambi sono miglioramenti futuri, non gap di sicurezza o
  blocker per la chiusura.
