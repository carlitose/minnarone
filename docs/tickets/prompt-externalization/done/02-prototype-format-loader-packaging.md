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

---

## Risultati / Decisione (2026-07-17)

Spike **reversibile** in `spike/prompt_externalization/` (throwaway, marcato nel
README, NON cablato). Prova il contratto su 2 prompt rappresentativi:
`rules.md` (prosa, persona/regole con canale "enkk" → `{{channel}}`) e
`situations.md` (le 6 varianti `_original_chat_situation`, a chiavi). Aggiunto
`format.md` (contratto RE/MSG) per provare la validazione dei token.

**Demo verde**: `uv run --extra dev python -m pytest
spike/prompt_externalization/test_spike.py -q` → **8 passed**;
`uv run python spike/prompt_externalization/demo.py` → output atteso.

### Formato scelto — markdown-only

Un prompt-set = una **directory**. Un `.md` per prompt di prosa; i set "a
chiavi" (le 6 situazioni; per estensione le 3 etichette summarizer e i 3 template
di stile) = un **unico `.md` con sezioni `## <chiave>`** parsate in un dict
(`_split_sections`). Niente YAML/TOML: per set di *prosa multilinea con graffe e
markup* il markdown è più editabile da un non-programmatore e non introduce
escaping/quoting; le sezioni `## <chiave>` bastano per le mappe chiave→testo e
restano leggibili. YAML aggiungerebbe solo attrito (block scalars, indentazione)
senza vantaggi su questi contenuti.

### Templating — `{{nome}}` con sostituzione sicura

Delimitatore **doppia graffa** `{{nome}}` (regex `\{\{\s*(\w+)\s*\}\}`). Proprietà:

- le **graffe singole** letterali (`{`, `}`) e i contratti `<...>` **sopravvivono**
  intatti (provato: `render("codice { non toccato } e {{x}}", …)`);
- il valore iniettato è inserito **letteralmente, senza ri-scansione**: se un
  valore contenesse `{{y}}` NON verrebbe ri-espanso → **il templating non è un
  vettore di injection** (provato);
- placeholder senza valore → **`PromptError` (fail-fast)**, mai stringa vuota;
- solo i nomi in **whitelist** (`allowed_placeholders`) sono ammessi nel file: un
  `{{ignoto}}` è errore di validazione (typo / punto di sostituzione non previsto).

**Mappa di `{language}`** (decisione locked "tenere `{language}`): il file usa
`{{language}}`, il loader lo risolve dal codice-lingua di config via
`language_name()` (fonte fidata = config, MAI contenuto percepito). **Nota
importante** (vedi Open): `language_name` restituisce il *nome in italiano*
(`en`→"inglese"); nel set inglese il risultato "in inglese" è corretto solo se il
set vuole il nome-lingua in italiano. Per l'original-chat, dove l'intero file è
già nella lingua dell'operatore, `{{language}}` è **facoltativo** (l'operatore può
scrivere "in English" nel testo). Raccomandazione: mantenere `{{language}}` solo
dove serve davvero (template operator/meeting/suggester che dicono "parla in
{language}") e lasciare che l'original-chat detti la lingua dal testo.

### Packaging + override — `importlib.resources` + `prompts_dir`, precedenza per-file

Default impacchettati come **package** (`default_prompts/`, letto con
`importlib.resources.files(pkg)`); nel loader reale sarà `minnarone/prompts/`
dentro il wheel (fresh install funziona). Override da una **directory** in config.
**Precedenza per-file**: per ogni file, se esiste in `prompts_dir/<file>` vince
l'override, altrimenti il default impacchettato (provato con `override_partial/`
che sovrascrive solo `rules.md`, mentre `situations.md` cade sul default).

### Validazione — fail-fast (mai vuoto silenzioso)

`PromptError` all'avvio su: file obbligatorio mancante (in override **e**
default); contenuto vuoto/solo-spazi; placeholder ignoto (fuori whitelist);
placeholder obbligatorio mancante (es. `{{channel}}` in `rules.md`); token di
controllo mancante dove atteso (`#end_conv` in `situations.md`; `RE:`/`MSG:`/
`#end_conv` in `format.md`; `#nothing` per il suggester); sezione `## <chiave>`
mancante o vuota. Tutti provati nei test. Questa policy è **volutamente diversa**
da `FileMemory` (che degrada con grazia perché la memoria è contesto opzionale):
un prompt di prosa/regole mancante non deve degradare a vuoto — le regole di
sicurezza restano cablate, ma il resto del prompt perderebbe senso.

### Proposta config `prompts_dir`

Nuova chiave stringa opzionale in `Config`, gemella di `soul_path`/`facts_dir`:

- opzionale: se assente → si usano SOLO i default impacchettati;
- se relativa, risolta **relativa alla dir del file di config** (stesso
  trattamento di `soul_path`/`facts_dir` in `_with_config_relative_memory_paths`);
- punta a una directory che contiene i `.md` del set (anche parziale). Un
  operatore che vuole un canale non-italiano ci mette il proprio set tradotto.

### Swap lingua — PROVATO "gratis"

`override_en/` è un set inglese completo. Puntando `prompts_dir` lì, **lo stesso
codice** serve i prompt in inglese (test `test_language_swap_serves_english_set`):
persona in inglese, 6 trigger presenti, `#end_conv` preservato. Nessun motore
i18n, nessuna traduzione fornita dal progetto.

### SOUL.md ↔ memoria-soul (decisione)

Confermato l'assetto locked: **separati ma co-locati**. `soul.md` resta l'IDENTITÀ
caricata da `FileMemory` (degrado con grazia, → `[MEMORIA PERMANENTE]`); le
**regole** di comportamento (`_ORIGINAL_CHAT_RULES`) diventano `rules.md`
caricato da `PromptSet` (**fail-fast**, → `[REGOLE]`). Due path di caricamento con
due policy di errore diverse, di proposito: non si unifica persona+regole in un
unico SOUL.md. Il PromptBuilder continuerà a comporre `soul` (da memoria) e
`rules`/`situations`/`format` (da PromptSet) come oggi.

### Open — da confermare al Next Review (umano)

1. **`{{language}}`**: tenerlo solo nei template operator/meeting/suggester e
   lasciare l'original-chat dettare la lingua dal testo? E `language_name`
   (nomi in italiano) resta in codice o sparisce con la mappa? (Vedi sopra.)
2. **Ancore di sezione cablate**: `situations.md` cita `[CONVERSAZIONE RECENTE]`,
   `[I TUOI ULTIMI MESSAGGI]`, `[MEMORIA]`. Nel set inglese sono rimaste **in
   italiano** perché sono ancore agli header cablati in `prompt.py`. Decisione
   ereditata dal ticket 01: o gli header si esternalizzano **insieme** al testo
   che li cita (coerenza garantita), o restano ancore cablate e il set operatore
   deve citarle uguali. Da chiudere nel 03/04.
3. **Precedenza per-file vs set completo**: comoda (override di un solo file), ma
   per uno swap-lingua un file dimenticato ricade **silenziosamente** sul default
   italiano (mescolando le lingue). La validazione garantisce la *presenza* (dal
   default) ma non la *coerenza linguistica*. Valutare una modalità "set stretto"
   (nessun fallback quando `prompts_dir` è impostato) nel ticket 03.
4. **Byte-invarianza del prefisso stabile**: con set default fissi il prefisso
   resta byte-identico (i `.md` sono costanti; la sostituzione di `{{channel}}`/
   `{{language}}` dipende solo da config, non da dati per-turno). Il ticket 07 deve
   comunque aggiungere il test di byte-invarianza sul loader reale.

### Raccomandazione — PROMOVIBILE al ticket 03

Sì. Il design (markdown-only + `{{...}}` sicuro + `importlib.resources` +
`prompts_dir` per-file + validazione fail-fast) è minimale, provato end-to-end e
copre tutte le voci "a varianti chiave" del ticket 01. Il ticket 03 può portare
`spike/prompt_externalization/loader.py` in `minnarone/prompts.py` (o
`prompt_source.py`) quasi as-is, spostare i `.md` in `minnarone/prompts/`,
aggiungere la chiave `prompts_dir` a `Config` e migrare il primo prompt come
tracer. Codice spike **conservato** in `spike/` (referenziato dal 03), NON
cablato. Ticket 02 **non** spostato in `done/`: attende conferma umana del design
al Next Review.
