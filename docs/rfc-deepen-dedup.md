# RFC — Deepening: rimuovere i cluster di duplicazione strutturale

> Origine: audit codebase-improver (0 blocker, 7 should-fix). Questo RFC copre
> 4 deepening pass che trasformano cluster shallow/duplicati in moduli profondi
> (interfaccia piccola, implementazione nascosta). Tutte le modifiche
> preservano il comportamento e sono provate da test al boundary.

---

## ① Adapter di cattura generico (da D1, +T1, +TY1)

### Problem
`OSCaptureAdapter` e `ScreenCaptureAdapter` (`capture.py:39, 116`) sono mirror
quasi identici: stesso ciclo di vita `start/stop/events`, stessa
normalizzazione sync-or-async (`_iter_chunks`/`_iter_frames`,
`capture.py:78-87, 157-166` byte-identici). Differiscono solo per il `channel`
e il tipo di payload. Due copie che divergeranno; nessun test dedicato (T1); i
capture source tipati `object` generano un cluster di `# type: ignore` (TY1).

### Proposed Interface
Un solo `StreamCaptureAdapter(SourceAdapter)` parametrico:
```python
Captured = Iterable[Timestamped] | AsyncIterable[Timestamped]  # payload ha .ts

class StreamCaptureAdapter(SourceAdapter):
    def __init__(self, channel: str, source: Captured) -> None: ...
    def channels(self) -> set[str]: return {self._channel}
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def events(self) -> AsyncIterator[RawEvent]: ...  # usa _aiter condiviso
```
Helper unico module-level `_aiter(source)` per la normalizzazione sync/async.
Costruttori ergonomici sottili conservano i nomi di dominio:
`os_audio_capture(source)` / `os_screen_capture(source)` →
`StreamCaptureAdapter("audio"|"video", source)`. I `make_device_*` restano
stub deferiti.

### Dependency Strategy
**In-process** — merge diretto. Il payload deve esporre `.ts` (`AudioChunk` e
`VideoFrame` già lo fanno → `Timestamped` Protocol). Chiude TY1 tipando il
source come unione, eliminando i `# type: ignore`.

### Testing Strategy
- **Nuovi boundary test** (`tests/test_capture.py`, chiude T1): lifecycle
  start/stop; `events()` emette `RawEvent(channel, payload, ts)`; nessun
  evento estratto dopo `stop()` (sorgenti real-time); normalizzazione sia per
  sorgente sync sia async.
- **Vecchi test:** la copertura indiretta via perceiver resta; si aggiunge il
  boundary test mancante.

### Implementation Recommendations
- Possiede: lifecycle + iterazione + impacchettamento in `RawEvent`.
- Nasconde: la differenza sync/async della sorgente.
- Migrazione: `app.py` costruisce via i costruttori ergonomici; i due nomi
  vecchi diventano alias sottili o vengono rimossi (codebase fresca → preferire
  i costruttori, mantenere alias se semplice).

---

## ② Runner di cadenza condiviso (da D3, +N2)

### Problem
Il loop async `run(interval)/stop()` è duplicato tra `Reactor`
(`reactor.py:159-168`) e `Summarizer` (`summarizer.py:80-98`): identico
`_running=True; while _running: <step>; await sleep(interval)` + `stop()`, più
il pattern di assorbimento di `LLMError` per saltare il ciclo. L'assorbimento è
silenzioso, senza log (N2).

### Proposed Interface
Un modulo profondo che possiede la meccanica del loop:
```python
class CadenceLoop:
    def __init__(self, step: Callable[[], Awaitable[None]], interval: float, *,
                 sleep: SleepFn = asyncio.sleep,
                 swallow: tuple[type[BaseException], ...] = (),
                 on_skip: Callable[[BaseException], None] | None = None) -> None: ...
    async def run(self) -> None: ...   # while running: try step() except swallow: on_skip; sleep
    def stop(self) -> None: ...
```
`Reactor` e `Summarizer` la **compongono**: `CadenceLoop(self.run_once,
interval, swallow=(LLMError,), on_skip=...)`. Il punto unico `on_skip` è dove
N2 (log opzionale) trova casa.

### Dependency Strategy
**In-process** — utility pura sopra `asyncio`. `sleep` iniettabile (già il
pattern del repo per test deterministici).

### Testing Strategy
- **Nuovi boundary test** (`tests/test_cadence.py`): esegue N step poi `stop()`;
  `swallow` salta il ciclo e chiama `on_skip` senza rompere il loop;
  `stop()` termina; `sleep` iniettato → deterministico.
- **Vecchi test:** i test di loop su Reactor/Summarizer restano verdi (compongono
  il runner); alcune asserzioni di loop diventano ridondanti col boundary test.

### Implementation Recommendations
- Possiede: ciclo di vita del loop, cadenza, assorbimento errori configurabile.
- Nasconde: flag `_running`, `while`, `sleep`, `try/except`.
- Espone: `run()`/`stop()` + i parametri di costruzione.
- Migrazione: Reactor/Summarizer delegano a un `CadenceLoop` interno; le loro
  firme pubbliche `run()/stop()` restano invariate (proxy sottile).

---

## ③ Base perceiver / dispatch eventi (da D2)

### Problem
`perceive_event`/`perceive_events` sono duplicati tra `AudioPerceiver`
(`audio.py:178-200`) e `VideoPerceiver` (`video.py:188-210`): identica guardia
sul canale + `isinstance` sul payload + fold su `perceive_events`. Variano solo
canale, tipo payload e metodo delegato.

### Proposed Interface
Una base comune che possiede l'adattamento `RawEvent`→percezione:
```python
class EventPerceiver(ABC):
    channel: ClassVar[str]
    payload_type: ClassVar[type]
    def perceive_event(self, event: RawEvent) -> list[Perception]:
        if event.channel != self.channel or not isinstance(event.payload, self.payload_type):
            return []
        return self._perceive_payload(event.payload)
    def perceive_events(self, events: Iterable[RawEvent]) -> list[Perception]: ...  # fold
    @abstractmethod
    def _perceive_payload(self, payload) -> list[Perception]: ...
```
`AudioPerceiver`/`VideoPerceiver` estendono e implementano solo
`_perceive_payload` (delegando a `perceive_chunk`/`perceive_frame`, che restano
i metodi specifici già testati).

### Dependency Strategy
**In-process** — pura. Nessuna nuova dipendenza.

### Testing Strategy
- **Nuovi boundary test:** un perceiver finto minimale che estende
  `EventPerceiver` verifica routing per canale, scarto payload del tipo
  sbagliato, e fold multi-evento — una volta sola, non per ogni perceiver.
- **Vecchi test:** i test di Audio/Video perceiver restano verdi (il
  comportamento specifico è invariato).

### Implementation Recommendations
- Possiede: dispatch per canale + validazione payload + fold.
- Nasconde: la guardia ripetuta.
- Espone: `perceive_event`/`perceive_events` + l'hook `_perceive_payload`.

---

## ④ Boundary di decodifica robusto (da R1)

### Problem
`Perception.from_json` (`perception.py:88-99`) protegge solo `source`; chiavi
`ts`/`type`/`text` mancanti sollevano un `KeyError` grezzo invece del coerente
`ValueError(... in {line!r})`. `PerceptionStore._read_all`/`read_from`
(`store.py:70,100`) propagano l'eccezione → **una singola riga corrotta aborta
l'intera lettura** dello store (e quindi una reazione).

### Proposed Interface (hardening, non reshape)
- `Perception.from_json(line)` valida TUTTE le chiavi e solleva un
  `ValueError` coerente e descrittivo su qualsiasi campo mancante/malformato.
- Lo store **salta** le righe non decodificabili invece di abortire (append-only
  log: una riga corrotta non deve uccidere la percezione). Opzionale: contatore
  per osservabilità.

### Dependency Strategy
**In-process** — pura.

### Testing Strategy
- **Nuovi test:** `from_json` su riga senza `ts`/`type`/`text` → `ValueError`
  chiaro; `read_from`/`tail`/`read_since` su file con una riga corrotta in mezzo
  → ritornano le righe valide, saltando quella rotta, senza sollevare.

### Implementation Recommendations
- `from_json` è l'unico punto di decodifica: deve fallire in modo chiaro e
  uniforme.
- Lo store è resiliente alla corruzione parziale (skip-and-continue).

---

## Note trasversali opzionali (nit, abilitati da questi pass)
- N2 (log su skip `LLMError`) trova casa naturale in `CadenceLoop.on_skip`.
- TY1 chiuso da ①.
- N3 (docstring TOML→YAML), N4 (`py.typed` + reason comment) sono fix banali
  innestabili negli stessi pass.

## Ordine di implementazione suggerito
④ (robustezza, isolato) → ③ (base perceiver) → ① (capture, usa il pattern di ③) →
② (cadence, tocca Reactor/Summarizer). Ognuno è un branch/pass indipendente con
boundary test propri.
