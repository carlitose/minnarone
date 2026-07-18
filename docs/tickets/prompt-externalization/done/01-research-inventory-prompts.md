# 01 — Research: inventario dei prompt hard-coded

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

research

## Outcome

Una tabella esaustiva di OGNI stringa di prompt hard-coded in `prompt.py` e
`summarizer.py` (e altrove se emerge), con: posizione `file:line`, a quale
sezione/stile appartiene, classificazione **ESTERNO** (tunabile) vs **CABLATO**
(sicurezza/struttura), i placeholder che ciascuna richiede (`{language}`, canale,
punti di iniezione del contenuto dinamico), e se contiene caratteri problematici
per il templating (`{`/`}`). È la base fattuale per il prototype (02) e le
migrazioni (04-06).

## Acceptance Criteria

- [ ] Tabella completa di tutte le costanti/f-string di prompt: `_ROBUSTNESS_RULES`,
      `_DISCLOSURE_*`, `_ORIGINAL_CHAT_RULES`, `_ORIGINAL_CHAT_INTRO`,
      `_COMMENTATOR_/_MEETING_/_SUGGESTER_RULES_TEMPLATE`, `[FORMATO RISPOSTA]`,
      i testi di `_original_chat_situation` (tutte le varianti), gli header di
      sezione, e in `summarizer.py` `_PROMPT_INSTRUCTION`,
      `_EMPTY_SUMMARY_PLACEHOLDER`, `_SOURCE_GROUPS`.
- [ ] Ogni voce classificata ESTERNO/CABLATO secondo il confine deciso
      (sicurezza = anti-injection + disclosure + fence restano CABLATE).
- [ ] Placeholder e parti dinamiche annotate per ciascuna voce.
- [ ] Voci "a varianti chiave" identificate (situazioni per tipo trigger, etichette
      gruppi summarizer) perché guideranno la scelta del formato.
- [ ] Verificato se ci sono prompt hard-coded in altri moduli oltre ai due noti.
- [ ] Risultati salvati in coda a questo ticket e ripiegati nel wayfinder.

## Blocked By

- None — può partire subito.

## Frontier

Nessuna migrazione è sicura senza la lista completa: è l'edge dell'inventario.

## Work Plan

1. Estrarre tutte le costanti e f-string di prompt dai due moduli (grep + lettura).
2. Classificare e annotare placeholder/parti dinamiche.
3. Cercare prompt hard-coded in altri file (es. `original_chat_output.py`, cli/app).
4. Compilare la tabella; aggiornare il wayfinder.

## Evidence to Capture

- Tabella `file:line | sezione/stile | ESTERNO/CABLATO | placeholder | note`.
- Elenco delle voci "a varianti chiave".

## Out of Scope

- Spostare codice o creare file di prompt (tocca a 03-06).
- Decidere il formato (tocca a 02).

---

## Risultati (2026-07-17)

### Base di riferimento

Inventario fatto contro lo stato **post-fidelity** (branch
`autopilot/original-chat-prompt-fidelity`, PR #32), che è la base su cui poggia
questo lavoro — include costanti non presenti su `main`/altri branch
(`_ORIGINAL_CHAT_INTRO`, summarizer rolling, ecc.). **Dipendenza**: l'esternalizzazione
va basata/rebasata su quel branch (o su `main` dopo il merge di #32).

I prompt sono confinati in `prompt.py` e `summarizer.py`. Verificato: il
`RE:/MSG:` in `original_chat_output.py:53` è formattazione dell'**output** (display),
NON un prompt → fuori inventario. Nessun altro modulo contiene prompt.

### CABLATO — resta nel codice (sicurezza/struttura)

| Simbolo | prompt.py | Motivo |
|---|---|---|
| `_ROBUSTNESS_RULES` | ~86 | Anti-injection |
| `_DISCLOSURE_HIDE` / `_DISCLOSURE_ANNOUNCE` | ~101 / ~105 | Disclosure |
| `_UNTRUSTED_OPEN` / `_UNTRUSTED_CLOSE` / `_DATA_LINE_PREFIX` | 44 / 45 / 52 | Meccanica fence |
| `_SAFE_DISPLAY_TOKEN_RE` | 53 | Sanitizzazione (non è testo di prompt) |

### ESTERNO — da spostare in file (tunabile)

**prompt.py:**
| Simbolo / testo | Riga | Placeholder / note |
|---|---|---|
| `_ORIGINAL_CHAT_RULES` (persona, stile, emote) | 143 | ⚠️ canale "enkk" **incorporato nel testo** (riga ~124) |
| `_ORIGINAL_CHAT_INTRO` (banner + riga canale) | 170 | ⚠️ canale "enkk" (2ª occorrenza) |
| `_COMMENTATOR_RULES_TEMPLATE` | 110 | `{language}` |
| `_MEETING_SYNTHESIZER_RULES_TEMPLATE` | 119 | `{language}` |
| `_SUGGESTER_RULES_TEMPLATE` | 131 | `{language}`; token di controllo `#nothing` |
| Testo `[FORMATO RISPOSTA]` (contratto RE/MSG) | ~254 | ⚠️ contiene `RE:`/`MSG:`/`#end_conv`: il parser dell'output ne dipende |
| `_original_chat_situation` — 6 varianti | 466–517 | **"a varianti chiave"** (source × kind): idle, chat-mention, chat-continuation, streamer-mention, streamer-continuation, fallback. Placeholder `{user}`/`{mention}`; token `#end_conv`; riferimenti `[CONVERSAZIONE RECENTE]`/`[I TUOI ULTIMI MESSAGGI]`/`[MEMORIA]` |
| `_language_name` (mappa code→nome) | ~718 | Supporta `{language}`; sparisce se si abbandona il placeholder |

**summarizer.py:**
| Simbolo / testo | Riga | Note |
|---|---|---|
| `_PROMPT_INSTRUCTION` | 44 | Include la riga sotto-sezioni (ricostruzione) |
| `_EMPTY_SUMMARY_PLACEHOLDER` | 60 | |
| `_SOURCE_GROUPS` etichette ("STREAMER ha detto:", "SCHERMO:", "CHAT:") | 64–67 | La **mappa** Source→etichetta resta codice; solo le etichette vanno in file |
| Scaffolding in `_build_prompt`: "Riassunto attuale:", "Eventi recenti:", "Aggiorna il riassunto." | ~108–111 | Literal f-string, non costanti nominate |

### ESTERNO — DA DECIDERE (header/etichette di sezione)

Le etichette di sezione sono tunabili ma **referenziate in modo incrociato** (il
testo delle situazioni cita `[I TUOI ULTIMI MESSAGGI]`/`[MEMORIA]`): se
esternalizzate devono restare coerenti. Sono: `[REGOLE]` (238),
`[MEMORIA PERMANENTE]` (243), `[FORMATO RISPOSTA]` (254), `[MEMORIA] (...)` (457),
`[I TUOI ULTIMI MESSAGGI]` (458), `[CONVERSAZIONE RECENTE]` (459), `[SITUAZIONE]`
(461), `ORIGINAL_CHAT_CONTEXT_SPECS` → `[CHAT RECENTE]`/`[PARLATO RECENTE]`/
`[SCHERMO RECENTE]` (80–82), e per gli altri stili `## RIASSUNTO`/`## CONVERSAZIONE
RECENTE`/`## SITUAZIONE`. **Raccomandazione per il 02**: o si esternalizzano
INSIEME al testo che le referenzia (coerenza garantita), o restano ancore
strutturali cablate. Decidere nel prototype.

### Voci "a varianti chiave" (guidano la scelta del formato — input per 02)

1. Le 6 varianti di `_original_chat_situation` (source × kind).
2. Le 3 etichette `_SOURCE_GROUPS` del summarizer.
3. I 3 template di stile con `{language}`.

### Token di controllo che DEVONO sopravvivere all'esternalizzazione

`#end_conv`, `#nothing`, `RE:`, `MSG:` — il parser dell'output e la logica di
chiusura conversazione ne dipendono. La validazione (02) dovrebbe verificarne la
presenza dove attesi.

### Caratteri problematici per il templating

Il testo usa `{language}` come placeholder intenzionale; i contratti usano `<...>`
(non graffe). Nessuna graffa letterale spuria trovata → `str.format` fattibile, ma
il 02 deve comunque gestire graffe letterali in modo sicuro.

### Note ripiegate nel wayfinder

- Canale "enkk" appare in **2 punti** (`_ORIGINAL_CHAT_RULES` + `_ORIGINAL_CHAT_INTRO`):
  unificarlo in un unico placeholder/valore.
- Il contratto `[FORMATO RISPOSTA]` è ESTERNO ma **accoppiato al parser**: candidato
  a validazione forte.
- Header di sezione: decisione esplicita rimandata al 02.
