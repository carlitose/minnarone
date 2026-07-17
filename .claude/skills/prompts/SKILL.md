---
name: prompts
description: Gestire i prompt esternalizzati di minnarone in sicurezza. Usare quando si chiede di cambiare/modificare i prompt, tradurre il prompt-set in un'altra lingua, validare un override o un prompts_dir, aggiungere/rinominare header di sezione, o vedere/provare l'effetto di una modifica ai prompt prima di committare. Tre modalità - validate, edit, try.
---

# Skill `prompts` — validare, modificare e provare i prompt esternalizzati

Una sola skill con tre modalità (**validate** / **edit** / **try**) perché i tre
flussi condividono la stessa mappa dei file, gli stessi vincoli e le stesse
avvertenze — e in pratica si concatenano sempre: edit → validate → try.

## Mappa del sistema (dove stanno le cose)

- **Fonte di verità dei vincoli**: `src/minnarone/prompt_source.py` — i
  `PromptSpec`/`KeySpec` (`FORMAT_SPEC`, `RULES_SPEC`, `INTRO_SPEC`,
  `SITUATIONS_SPEC`, `HEADERS_SPEC`, `OPERATOR_RULES_SPEC`,
  `MEETING_SYNTHESIZER_RULES_SPEC`, `SUGGESTER_RULES_SPEC`,
  `SUMMARIZER_SPEC`) dichiarano per ogni file placeholder ammessi/obbligatori,
  token di controllo e sezioni richieste. **In caso di dubbio o divergenza,
  leggi i spec nel codice: la tabella qui sotto è un riassunto, non la fonte.**
- **Default impacchettati**: `src/minnarone/prompts/*.md` (9 file, italiano).
- **Override**: directory indicata da `prompts_dir` nel config YAML (risolta
  relativa al file di config). Precedenza **per-file**: un file presente
  nell'override vince, gli altri cadono sul default impacchettato.
- **Cambio lingua** = riscrivere i `.md` e puntare `prompts_dir`. Esempio
  parziale commentato: `examples/prompts-en/` (leggi il suo README).

## ⚠️ Confine di sicurezza (cosa NON è nei file, di proposito)

Le regole anti-injection/anti-disclosure e il fence dei dati non fidati
(`DATI_PERCEPITI`, prefisso `| `) sono **cablati in `src/minnarone/prompt.py`**
e NON compaiono nei `.md` editabili. Un override può cambiare persona, lingua
ed etichette ma non può indebolire la protezione: il testo di sicurezza viene
sempre prepeso sotto il label `regole`, qualunque sia il label. **Non provare
a "esternalizzare" queste parti né a replicarle nei file: è una decisione di
design registrata, non una dimenticanza.**

## ⚠️ Byte-invarianza (perché NON si editano i default alla leggera)

Il prefisso stabile del prompt è in cache lato LLM: con i default impacchettati
deve restare **byte-identico** tra build. I test
(`tests/test_prompt_fresh_install.py`, `tests/test_prompt_builder.py`) pinnano
il contenuto dei default: toccare `src/minnarone/prompts/*.md` li fa fallire
finché non li si aggiorna consapevolmente. **Il percorso sicuro per
sperimentare o personalizzare è un override via `prompts_dir`**, mai l'edit
del default — modifica i default solo se il cambiamento è voluto per tutti e
aggiorni i test di conseguenza.

## Tabella file / vincoli (riassunto derivato dai PromptSpec — verifica nel codice)

| File | A chiavi? | Placeholder obbligatori | Token di controllo richiesti | Note |
|------|-----------|------------------------|------------------------------|------|
| `format.md` | no | — | `RE:`, `MSG:`, `#end_conv` | Contratto del parser dell'output |
| `rules.md` | no | `{{channel}}` | — | Persona, nel prefisso stabile |
| `intro.md` | no | `{{channel}}` | — | Banner dinamico |
| `situations.md` | sì (6 sezioni) | per-sezione, vedi sotto | `#end_conv` in `idle`, `chat-mention`, `chat-continuation`, `streamer-continuation` | Vincoli PER-SEZIONE in `SITUATIONS_SPEC.key_specs` |
| `headers.md` | sì (17 chiavi) | `{{channel}}` solo in `cosa_sai` | — | Nessun `{{header_*}}` ammesso qui (no ricorsione) |
| `operator.md` | no | `{{language}}` | — | Stile operator |
| `meeting_synthesizer.md` | no | `{{language}}` | — | Stile meeting |
| `suggester.md` | no | `{{language}}` | `#nothing` | Sentinella "niente da suggerire" |
| `summarizer.md` | sì (8 chiavi) | NESSUN placeholder ammesso | — | Set separato (`SUMMARIZER_SET`) |

Dettagli per-sezione di `situations.md` (da `SITUATIONS_SPEC.key_specs`):
`{{user}}`/`{{mention}}` sono ammessi SOLO in `chat-mention` e
`chat-continuation`; `{{reason}}` SOLO in `generic`; i riferimenti incrociati
`{{header_memoria}}`, `{{header_tuoi_ultimi_messaggi}}`,
`{{header_conversazione_recente}}` sono ammessi in OGNI sezione (risolti da
`headers.md`, così un rename dell'header propaga da solo). Un placeholder in
una sezione il cui render non lo fornisce fallisce all'avvio.

Regole trasversali:

- I placeholder sono ESATTAMENTE `{{nome}}`; graffe singole e `<...>` restano
  letterali. Un `{{x}}` fuori whitelist = errore al load.
- Le **chiavi** delle sezioni (`## idle`, `## regole`, ...) sono il contratto:
  si traducono i CORPI, mai le chiavi.
- Mai lasciare un file o una sezione vuoti: il loader è fail-fast, non degrada.

---

## Modalità VALIDATE

Valida entrambi i set (original-chat + summarizer) con l'entry-point reale:

```bash
# solo default impacchettati
uv run python -m minnarone validate-prompts

# con una directory di override
uv run python -m minnarone validate-prompts --prompts-dir PATH/ALLA/DIR

# leggendo prompts_dir da un config YAML (stessa risoluzione relativa dell'app)
uv run python -m minnarone validate-prompts --config PATH/AL/CONFIG.yaml
```

Exit code: `0` = tutto valido; `1` = errori di prompt (una riga per problema su
stderr, con file e — per i file a chiavi — la SEZIONE incriminata); `2` =
errore di config. Con exit 0 stampa l'origine di ogni file
(`default`/`override`) e una **nota di override parziale** se solo alcuni file
vengono dall'override (possibile mix di lingue: chiedi conferma che sia voluto).

Riporta gli errori così come sono: sono già azionabili (es.
`token di controllo mancante in 'situations.md' sezione 'chat-mention': '#end_conv'`).

## Modalità EDIT

Flusso guidato per modificare o tradurre i prompt:

1. **Decidi il bersaglio**: override via `prompts_dir` (caso normale: prova,
   personalizzazione, traduzione) oppure default impacchettati (solo se il
   cambiamento è per tutti — vedi byte-invarianza sopra). Per un override
   parti copiando il file default da `src/minnarone/prompts/`.
2. **Consulta i vincoli** del file che tocchi: tabella sopra + il relativo
   `PromptSpec` in `src/minnarone/prompt_source.py`. Non rimuovere MAI
   placeholder obbligatori (`{{channel}}`, `{{language}}`), token di controllo
   (`#end_conv`, `#nothing`, `RE:`, `MSG:`), sezioni richieste o chiavi.
3. **Modifica** i `.md`.
4. **Valida**: `uv run python -m minnarone validate-prompts --prompts-dir DIR`
   (o senza flag se hai toccato i default). Deve uscire 0.
5. **Test mirati** (obbligatori se hai toccato i default, consigliati sempre):

   ```bash
   uv run --extra dev python -m pytest -q tests/test_prompt_source.py tests/test_prompt_builder.py tests/test_prompt_fresh_install.py tests/test_cli.py
   ```

6. **Diff review**: `git diff` — controlla di non aver toccato chiavi di
   sezione, placeholder o token per sbaglio; se hai modificato i default,
   verifica che ogni cambiamento del prefisso stabile sia voluto.
7. (Opzionale ma consigliato) **Prova l'effetto** con la modalità TRY.

## Modalità TRY

Due livelli, dal più leggero al più completo:

1. **Render del prompt** con percezioni fake — mostra il prompt COMPLETO che
   l'LLM riceverebbe, usando lo script incluso nella skill:

   ```bash
   # default impacchettati
   uv run python .claude/skills/prompts/preview_prompt.py

   # con override
   uv run python .claude/skills/prompts/preview_prompt.py PATH/ALLA/DIR
   ```

   Fail-fast: se il set è rotto lo script muore con `PromptError` prima di
   renderizzare (stesso comportamento dell'avvio dell'app). Utile per un diff
   prima/dopo: salva l'output di default e override e confrontali.

2. **Smoke dell'app senza rete** — costruisce l'agente completo (validazione
   prompt inclusa) e esce:

   ```bash
   # baseline che passa senza setup extra
   uv run python -m minnarone examples/llamacpp-local.example.yaml --check

   # con il TUO config che punta a prompts_dir
   uv run python -m minnarone PATH/AL/CONFIG.yaml --check
   ```

   Exit 0 e `ok: agente '...' costruito (...)` = i prompt (e il resto del
   config) reggono l'avvio reale.
