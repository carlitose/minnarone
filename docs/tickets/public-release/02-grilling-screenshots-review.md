# Revisione umana degli screenshot in docs/source/screenshots/

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

grilling

## Outcome

Decisione registrata su cosa fare dei 10 PNG (~11 MB) tracciati in
`docs/source/screenshots/`: tenerli, rimuoverli, o sostituirli/ridurli.
Copre due domande: contenuti sensibili visibili e diritti sui frame (sono
catture del video di enkk).

## Acceptance Criteria

- [ ] Ogni screenshot è stato guardato da un umano (o da revisione assistita)
      per token/credenziali/chat private/email visibili.
- [ ] Decisione presa sui diritti: la ripubblicazione dei frame del video di
      enkk è accettabile (credito già presente nel README) oppure no.
- [ ] Decisione registrata nella mappa (`Decisions So Far`) ed eventuale
      ticket task derivato per la rimozione.

## Blocked By

- None - can start immediately.

## Frontier

Gli screenshot diventano pubblici col flip: è l'unico contenuto tracciato non
ancora ispezionato da un umano. Un grep binario su un PNG ha dato un match di
pattern (quasi certamente falso positivo, ma va confermato a vista).

## Work Plan

1. Aprire i 10 PNG in `docs/source/screenshots/` uno per uno.
2. Verificare assenza di token, credenziali, messaggi privati, dati personali
   di terzi visibili a schermo.
3. Decidere sulla questione diritti (frame di video altrui, uso documentale
   con credito).
4. Registrare la decisione nella mappa; se si rimuovono, creare ticket task.

## Evidence to Capture

- Elenco dei file revisionati con esito per ciascuno.
- Risposta dell'utente sulla questione diritti.

## Out of Scope

- Riscrittura della history per file già pubblicati altrove.
- Ottimizzazione peso immagini (solo se decisa qui come follow-up).
