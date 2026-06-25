## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

Lo strato fondante su cui tutto il resto si appoggia: il **contratto dati `Perception`**, le **interfacce astratte** dei moduli che verranno implementati in più slice (`SourceAdapter`, `LLMProvider`, `OutputRouter`, hook `Memory.update`), e lo **schema del file di configurazione**. Questo slice non implementa comportamento utente: produce i *contratti* e ottiene il **sign-off umano** prima che gli altri slice (in particolare 05/06/07/08, parallelizzabili) vi si appoggino. È HITL proprio perché un errore qui è costoso da correggere a valle.

Riferimenti PRD: sezione *Implementation Decisions* (contratto `Perception`, moduli e interfacce, configurazione).

Snippet decisionale (forma canonica di una percezione — incluso perché fissa il giunto centrale del sistema):
```json
{ "ts": 1781057651.73, "source": "audio", "type": "speech", "speaker": "streamer", "text": "..." }
```
- `source ∈ {chat, audio, video, event}`; `type` dipende da `source`; `speaker` opzionale; `ts` epoch secondi (float).

## Step-by-step implementation plan

1. **Definisci il tipo `Perception`** con i campi del contratto sopra. Perché ora: è il dato che attraversa ogni layer. Verifica: serializza/deserializza una riga JSON senza perdita. Trappola: non legare il tipo a una fonte specifica (deve valere per chat/audio/video/event).
2. **Definisci l'interfaccia astratta `SourceAdapter`** (`start()` → handle stream per canale, `stop()`). Perché ora: slice 05/06 la implementeranno; deve restare neutra (nessun dettaglio Twitch/SO che trapeli). Verifica: esiste un fake adapter usabile nei test.
3. **Definisci l'interfaccia astratta `LLMProvider`** (`complete(prompt) -> message`, con segnale di errore/timeout distinto). Perché ora: slice 01 userà un fake, slice 02 l'impl. reale. Verifica: un fake ritorna un messaggio deterministico.
4. **Definisci l'interfaccia astratta `OutputRouter`** (`route(message, mode) -> channel`). Perché ora: predispone whisper/TTS v2 senza riscrivere il core. Verifica: instrada verso un canale console in modalità pubblica.
5. **Definisci l'hook `Memory.update(facts_delta)`** come no-op documentato. Perché ora: predispone l'auto-memoria v2 senza implementarla.
6. **Definisci lo schema del file di config**: `mode` (public/private), percorsi `soul`/`facts`, `adapter`, `llm_provider`+parametri, cadenze (`senser_interval≈0.5s`, `idle_interval≈150s`), `recent_chat_window≈15`, e i punti v2 inerti (`disclosure`, `retention`). Verifica: un config d'esempio valida; i punti v2 sono presenti ma non fanno nulla.
7. **Review umana (HITL):** presenta contratti e schema; ottieni approvazione prima di chiudere lo slice. Trappola: non far partire il fan-out parallelo prima del sign-off.

## Acceptance criteria

- [x] Il tipo `Perception` esiste, serializza/deserializza in JSONL senza perdita e copre i 4 `source`.
- [x] Esistono interfacce astratte per `SourceAdapter`, `LLMProvider`, `OutputRouter` con fake usabili nei test.
- [x] L'hook `Memory.update` esiste come no-op documentato.
- [x] Lo schema di config valida un esempio completo, con i punti v2 (`disclosure`, `retention`, auto-memory) presenti ma inerti.
- [x] I contratti sono stati rivisti e approvati da un umano.

## Decisioni di review (sign-off)

1. `RawEvent.payload` resta **opaco** (`object`); tipizzazione interna a ogni pipeline.
2. `SourceAdapter.events()` è **uno stream unico** di `RawEvent` etichettati per canale (ordine temporale preservato; demux a valle).
3. `VALID_TYPES`: **set minimo** per `event` (`join`/`leave`/`reaction`); vocabolario ricco aggiunto in v2 (additivo).
4. Config in **YAML** (PyYAML) — *modifica rispetto alla bozza TOML*.
5. Errori LLM via **eccezioni** (`LLMError`/`LLMTimeout`) → salto-turno nel Reactor.

## Blocked by

None - can start immediately

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 5
- User story 6
- User story 29
- User story 30
- User story 31
- User story 32
