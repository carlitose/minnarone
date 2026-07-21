# 05 — Task: launch kit (testi per ogni canale)

## Parent Spec

[repo-promotion-wayfinder.md](../../../specs/repo-promotion-wayfinder.md)

## Type

task

## Outcome

Testi pronti e approvati dall'autore per ciascun canale scelto nel grilling 01,
conformi alle regole mappate nel research 04, con l'asset demo del ticket 03
integrato.

## Acceptance Criteria

- [x] Un testo per canale (titolo + corpo), nella lingua giusta per il canale.
- [x] Ogni testo rispetta il vincolo di non-affiliazione: l'ispirazione a Enkk
      è citata come fatto, mai come endorsement; nessun invito a contattarlo.
- [x] Titolo Show HN conforme alle guideline (niente clickbait, formato
      "Show HN: ...").
- [x] Calendario di pubblicazione concordato (canale → giorno/ora).
- [x] L'autore ha approvato esplicitamente ogni testo prima del lancio.

## Blocked By

- 01 (pubblico/canali/tono), 03 (asset demo), 04 (regole canali).

## Frontier

È il punto in cui le decisioni diventano materiale eseguibile; dopo questo il
lancio è solo esecuzione.

## Work Plan

1. Per ogni canale scelto: bozza di titolo e corpo nel formato raccomandato
   dal research 04, col tono deciso nel grilling 01.
2. Revisione incrociata contro il vincolo non-affiliazione.
3. Giro di approvazione con l'autore; iterare finché approvato.
4. Fissare il calendario e salvarlo nella mappa.

## Evidence to Capture

- Testi finali approvati + calendario, salvati accanto a questo ticket.

## Progress (2026-07-21)

- Kit approvato: [repo-promotion-launch-kit.md](../../../specs/repo-promotion-launch-kit.md).
- Preparati titolo/commento Show HN, thread X, post LinkedIn, post
  r/SideProject, risposte FAQ e calendario esatto 25–28 luglio 2026.
- Per r/LocalLLaMA è stata preparata una scheda fattuale, non testo
  pubblicabile: le regole vietano post principalmente generati da LLM e
  richiedono quindi una bozza scritta dall'autore con voce propria.
- Review completata sui due assi: le affermazioni tecniche, i link, i formati e
  il calendario sono stati verificati; la formulazione sull'autoria distingue
  esplicitamente questo framework dal bot originale di Enkk. Verifica locale:
  `git diff --check`, limiti X/LinkedIn e 51 test documentali passati.
- Approvazione autore ricevuta in chat il 2026-07-21: “Approvo tutto”. Il set
  pubblicabile approvato comprende Show HN, X, LinkedIn e r/SideProject; il
  calendario è approvato. r/LocalLLaMA resta opzionale e richiede ancora testo
  scritto personalmente dall'autore per rispettarne le regole.

## Out of Scope

- La pubblicazione stessa (ticket 06).
