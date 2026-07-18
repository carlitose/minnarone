# Decidere il contratto guidato per soul, facts e descrizione canale

## Parent Spec

[public-release-wayfinder.md](../../../specs/public-release-wayfinder.md)

## Type

grilling

## Outcome

Definire quali domande un umano o code agent deve porre prima di creare
`soul.md` e `facts/*.md`, quali informazioni può suggerire da metadata e quale
conferma impedisce di trasformare inferenze in identità inventata.

## Acceptance Criteria

- [x] Sono definiti campi minimi e facoltativi del soul (identità, opinioni,
      tono, limiti, lunghezza messaggi).
- [x] Sono distinti facts durevoli, contesto corrente opzionale e percezioni
      live; nessun dettaglio di sessione entra nei facts senza opt-in.
- [x] È deciso che i metadata Twitch possono precompilare solo dati
      verificabili; ogni inferenza o persistenza richiede conferma umana.
- [x] È definita la relazione con i prompt template: identity/knowledge non
      vengono confusi con regole/format/placeholder.
- [x] L'output è abbastanza preciso da alimentare il prototipo skill del ticket
      16 con due scenari di accettazione.

## Blocked By

- None.

## Frontier

Risolta: il contratto di intervista, conferma, scrittura e validazione è stato
confermato dall'utente. Nessuna modifica al runtime Minnarone è richiesta.

## Decision Contract

### Conferma e scrittura

- Non scrivere alcun file prima di una conferma esplicita.
- Mostrare il Markdown esatto di soul, facts e contesto corrente proposto,
  indicando separatamente l'origine dei dati (`utente`, `metadata`, `ipotesi`).
- Se i file esistono, proporre un diff minimo; non sovrascrivere né risolvere
  conflitti silenziosamente.
- Creare per default sotto `.local/<canale>/`; pubblicare un esempio è un'azione
  separata e deliberata.

### Soul

- Campi obbligatori: nome/nickname, ruolo nel canale, tono, 2–5 opinioni o
  tratti distintivi, limiti comportamentali e lunghezza tipica dei messaggi.
- Campi facoltativi: età, biografia, squadra, interessi e altri dettagli scelti
  dall'operatore.
- Tono, opinioni e lunghezza appartengono al soul; prompt template, formato,
  placeholder e sicurezza restano contratti condivisi.
- Se manca un campo obbligatorio, proporre un default neutro e richiederne
  l'accettazione; un campo facoltativo può essere omesso.
- Non imporre limiti di lunghezza né warning dimensionali.

### Facts e contesto canale

- Usare un file per entità: canale, streamer e altre persone rilevanti.
- Il fact del canale richiede nome, contenuto principale e rapporto della
  persona col canale. Lingua, streamer, format, community, tormentoni e
  argomenti sensibili sono facoltativi.
- I metadata Twitch possono precompilare automaticamente solo nome canale,
  categoria, titolo e stato live come dati verificabili; formato abituale,
  personalità e rapporti restano ipotesi da confermare.
- Non modificare il runtime per introdurre session context. Se l'operatore vuole
  persistere dettagli della live, chiedere opt-in e inserirli sotto
  `## Contesto corrente`, avvertendo che resteranno nelle sessioni successive.
- Alla live successiva, se `## Contesto corrente` esiste, obbligare a scegliere
  tra sostituire, rimuovere o confermare ancora valido.

### Lingua, validazione ed errori

- Usare `commentator.language` come lingua predefinita di soul/facts e chiedere
  conferma se canale e operatore usano lingue diverse.
- Dopo la scrittura, eseguire `validate-prompts` e
  `minnarone <config> --check`; mostrare l'esito e non avviare shadow/live.
- Se la validazione fallisce, mantenere il diff e proporre una correzione;
  rollback solo su richiesta esplicita.
- Non aggiungere controlli sui segreti specifici della skill: valgono i
  guardrail del code agent.

## Acceptance Scenarios

1. Nuovo canale: intervista → bozza esatta → conferma → scrittura sotto
   `.local/` → validazione, senza inventare dati né avviare il runtime.
2. Canale esistente: rilevamento di soul/facts e `Contesto corrente` → diff
   minimo → conferma → validazione, senza overwrite silenzioso.

## Work Plan

1. Intervistare l'utente sui campi utili e sul livello di dettaglio.
2. Separare identità, opinioni, fatti durevoli e contesto corrente.
3. Definire checkpoint, formato e comportamento su informazioni mancanti.
4. Concordare update, lingua, validazione ed error handling.
5. Registrare due scenari di accettazione per il prototipo del ticket 16.

## Evidence to Capture

- Risposte dell'utente nella sessione 2026-07-18.
- Contratti correnti di `FileMemory` e PromptBuilder: tutti i file di
  `facts_dir` sono memoria permanente; non esiste un session-context separato.
- Esperienza AiRwayTV: prima bozza semanticamente inventata, poi corretta dopo
  intervista e conferma.

## Out of Scope

- Modificare i prompt default.
- Modificare il runtime o aggiungere `session_context_path`.
- Implementare una UI o CLI definitiva.
- Auto-memory cross-sessione.

## Status

Done — 2026-07-18.
