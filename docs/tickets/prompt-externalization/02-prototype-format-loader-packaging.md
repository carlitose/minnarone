# 02 — Prototype: formato, loader, packaging, validazione + layout prompt-set

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

prototype

## Outcome

Un contratto di **prompt-source** provato (spike reversibile) che scioglie i nodi
di design, dimostrato su 2 prompt rappresentativi: uno di prosa (persona/regole
Minnarone) e uno "a varianti chiave" o parametrizzato (le situazioni per tipo di
trigger, oppure un template con `{language}`). Al termine, decisioni registrate
(via `to-spec` o in coda qui) su: formato file, templating, packaging/override,
validazione, percorso configurabile (che abilita "gratis" un canale non italiano)
e relazione **SOUL.md ↔ `soul` di memoria**.

## Acceptance Criteria

- [ ] **Formato** scelto e motivato: markdown per la prosa + struttura (YAML/TOML)
      per le varianti chiave, oppure un unico formato. Deve gestire prosa
      multilinea, placeholder e mappe chiave→testo.
- [ ] **Templating** scelto: meccanismo di sostituzione placeholder sicuro
      (niente injection via template; gestione di `{`/`}` letterali). Placeholder
      previsti almeno: `{language}`, canale, e i punti di contenuto dinamico.
- [ ] **Packaging + override**: default impacchettati con l'app (fresh install
      funziona, es. `importlib.resources`) + override da una dir in config (come
      `soul_path`/`facts_dir`). Precedenza definita.
- [ ] **Validazione**: comportamento su file mancante/corrotto/placeholder
      mancante deciso (fail-fast con errore chiaro vs fallback), coerente col fatto
      che le regole di sicurezza restano cablate (un persona mancante non degrada a
      vuoto silenzioso).
- [ ] **Percorso configurabile**: i file di prompt si leggono da una directory
      indicata in config (stesso pattern di `soul_path`/`facts_dir`), così un
      operatore può puntare a un proprio set (anche in un'altra lingua) senza
      toccare il codice. Nessun motore i18n, nessun fallback multi-set complicato.
- [ ] **Placeholder `{language}`**: deciso se tenerlo o lasciar dettare la lingua
      direttamente al testo del file (visto che l'intero prompt sarà nella lingua
      dell'operatore).
- [ ] **Decisione SOUL.md ↔ memoria-soul** registrata: unificare persona+regole in
      SOUL.md o tenere separati memoria-soul e regole-persona.
- [ ] Spike dimostrato end-to-end sui 2 prompt scelti, con la byte-invarianza del
      prefisso stabile ancora verificabile quando i file default sono fissi.
- [ ] Decisioni ripiegate nel wayfinder; codice spike marcato come throwaway o
      promosso consapevolmente al ticket 03.

## Blocked By

- Blocked by [01-research-inventory-prompts.md](./01-research-inventory-prompts.md)

## Frontier

È l'edge di design che blocca tutte le migrazioni: fissa il contratto una volta
sola così 03-07 non vengono rifatti.

## Work Plan

1. Scegliere 2 prompt rappresentativi dall'inventario (una prosa + una a varianti).
2. Prototipare 1-2 formati candidati e un loader minimale con placeholder.
3. Provare packaging (risorsa impacchettata) + override da config (directory
   configurabile, come soul/facts).
4. Decidere SOUL.md ↔ memoria-soul e il destino di `{language}`.
5. Registrare le decisioni (to-spec o in coda) e aggiornare il wayfinder.

## Evidence to Capture

- File spike + 1 esempio di prompt-set minimo (dir configurabile).
- Nota di decisione: formato, templating, packaging, validazione, percorso
  configurabile, `{language}`, SOUL.md↔memoria.

## Out of Scope

- Migrare tutti i prompt (03-06).
- Qualsiasi motore i18n: basta il percorso configurabile + niente italiano cablato.
