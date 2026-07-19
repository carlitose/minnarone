> 🇬🇧 [English version](README.md)

# Minnarone Framework

<p align="center">
  <a href="https://www.youtube.com/watch?v=EkunaRO0uKg">
    <img src="docs/source/minnarone-cover.jpg" alt="Minnarone — vedo e sento tutto" width="640">
  </a>
</p>
<p align="center"><em>Copertina del <a href="https://www.youtube.com/watch?v=EkunaRO0uKg">video di origine di enkk</a>.</em></p>

Framework riusabile per costruire agenti AI che **percepiscono un contesto live multimodale** (audio, video/schermo, chat, eventi di piattaforma) e **reagiscono proattivamente** — sia come partecipante pubblico (co-host streamer, commentatore di gruppo) sia come assistente privato (suggerimenti per venditori, presentatori, partecipanti a riunioni).

Nasce dalla generalizzazione di **Minnarone**, un bot che osservava live stream Twitch e interagiva in chat in modo indistinguibile da un umano.

## Avvio rapido: shadow solo chat

Il primo task supportato è una prova **shadow solo chat**: Minnarone legge il
canale, prepara risposte candidate, registra evidenze locali e non invia alcun
messaggio Twitch. Da un clone pulito:

```bash
git clone https://github.com/carlitose/minnarone.git
cd minnarone
uv sync --extra tui
cp .env.example .env
mkdir -p .local/minnarone/onboarding/examplechannel
cp -R examples/onboarding/. .local/minnarone/onboarding/examplechannel/
```

Nella copia locale cambia `examplechannel`, `soul.md` e `facts/channel.md`. In
`.env` inserisci le credenziali di lettura dell'account bot dedicato e la chiave
LLM; mai inserire token nello YAML. Poi valida e avvia:

```bash
uv run python -m minnarone .local/minnarone/onboarding/examplechannel/twitch-chat-shadow.it.yaml --check
uv run python -m minnarone .local/minnarone/onboarding/examplechannel/twitch-chat-shadow.it.yaml --tui
```

`--check` è locale e lazy: valida la costruzione, ma non dimostra connessione a
Twitch, capacità hardware o prima inferenza del modello. La run parte in shadow
e va fermata in modo presidiato con `Ctrl-C`.

### Cosa stai modificando

Questi input hanno responsabilità deliberatamente distinte:

| Input | Responsabilità | Non deve fare |
| --- | --- | --- |
| **Configurazione** YAML | Seleziona adapter, modalità, modelli, provider, budget di sicurezza e cadenze. | Contenere prosa della persona o conoscenza stabile del canale. |
| `soul.md` | Definisce identità, voce, valori e confini comportamentali. | Collegare il runtime o dichiarare fatti sul canale. |
| `facts/` | Contiene facts stabili, curati manualmente e con fonte, su canali o interlocutori. | Essere memoria appresa, segreti o istruzioni di prompt. |
| **Prompt template** built-in / `prompts_dir` | Modella le istruzioni runtime; un `prompts_dir` esplicito sovrascrive i template inclusi. | Essere configurazione generale, soul o facts. |

Minnarone non apprende automaticamente facts persistenti. Revisiona ogni
modifica. Per gli override dei template usa la skill prompt indicata sotto:
l'onboarding non deve confondere questo confine di sicurezza.

### Golden path Twitch progressivi

1. **Shadow solo chat (P0).** Parti da
   [`twitch-chat-shadow.it.yaml`](examples/onboarding/twitch-chat-shadow.it.yaml),
   esegui `--check`, quindi osserva gli invii candidati nella TUI. Il token di
   scrittura non serve e non viene letto.
2. **Smoke media (P1/P2).** Prova i componenti di cattura separatamente prima
   di aggiungerli all'agente. Segui i comandi bounded per chat,
   `--no-chat --audio`, VAD e `--no-chat --video` nella
   [guida operatore Twitch](docs/twitch-operator.md#smoke-commands).
   Controlla `.smoke/*/stats.json`: uno smoke dimostra solo quel componente.
3. **Multimodale completo in shadow (P3-P5).** Scegli un profilo hardware nella
   [ricerca sui modelli runtime](docs/research/runtime-model-profiles.md),
   acquisisci esplicitamente gli artifact alle revisioni del
   [manifest](docs/runtime-model-manifest.json) e verifica il bundle completo:
   file richiesti, digest SHA-256 pubblicati e smoke locale del loader. Il
   digest del solo peso primario non dimostra la readiness. La config italiana
   [`twitch-full-shadow.it.yaml`](examples/onboarding/twitch-full-shadow.it.yaml)
   è un **esempio MPS solo P3**. Usa English VoxCeleb CAM++
   `3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx`, dimensione `512` e
   soglia `0.5`; il vecchio artifact Mandarin a 192 dimensioni non è il default
   pubblico. **P4 CUDA e P5 llama.cpp** richiedono backend, device, modelli e
   runtime specifici del profilo: non usarlo senza modifiche. Esegui ogni smoke
   isolato, poi `--check`, quindi una run shadow bounded in TUI osservando
   memoria, code e latenza.
4. **Live presidiato.** Usa una config locale separata solo dopo aver superato
   tutti i gate sotto. Una nuova sessione configurata `live` parte comunque in
   shadow. Ispeziona l'output candidato, poi premi `p` due volte entro tre
   secondi per promuovere. Premi `k` per il kill-switch immediato; per tornare
   live occorre sempre premere di nuovo `p` due volte. Non lasciare mai una
   sessione live senza presidio.

### Gate di sicurezza per l'invio pubblico

Il live non è l'avvio rapido. Richiede **consenso del broadcaster** registrato
per il canale target, un **account bot dedicato**, una allow-list e token di
lettura/scrittura appartenenti a quell'account. La allow-list è una difesa
tecnica, non prova del consenso. Completa la **validazione dei token** per
account, scope richiesti, scadenza e revoca all'avvio e almeno ogni ora. Un
mismatch, `401`, revoca, scope mancante, block, ban o richiesta di stop impone
fallback a shadow o stop, mai un invio best effort.

Scegli una **disclosure** onesta e adatta al canale: profilo del bot,
descrizione del canale, risposta chiara o annuncio. Non ordinare al sistema di
negare la realtà. Minnarone oggi invia via IRC: non promettere il **Chat Bot
Badge** Twitch, che richiede il percorso supportato Send Chat Message API/App
token e non è fornito da IRC.

I default `max_per_minute: 1` e `max_per_hour: 20` sono **budget Minnarone**
conservativi. Non sono i **limiti Twitch** ufficiali e non autorizzano a
riempire il bucket Twitch. Mantieni entrambi i livelli di vincoli.

Anche shadow legge e conserva dati. Una run può contenere
`perceptions.jsonl`, `debug/prompts/`, `debug/events.jsonl`, riassunti e copie
derivate della chat. `retention.perceptions_days` è riservato e inerte: non
cancella i dati. Scegli una durata legata allo scopo, documenta un contatto di
**opt-out**, ferma la run ed esegui la **cancellazione manuale** dell'intera
directory di run e delle copie derivate quando viene richiesto, il consenso è
revocato o i dati non servono più.

### Catalogo delle skill pubbliche

Le skill canoniche e portabili sono sotto `.agents/skills/` in ogni checkout.
Gli alias symlink relativi in `.claude/skills/` sono optional e servono solo
sui checkout che supportano i symlink. Con `core.symlinks=false`, Git può
materializzare un alias come plain file contenente soltanto il target: quel file
non è una skill valida. I code agent devono caricare il relativo `SKILL.md`
canonico da `.agents` prima di agire.

| Skill | Trigger | Azioni | Confine |
| --- | --- | --- | --- |
| [`minnarone-prompts`](.agents/skills/minnarone-prompts/SKILL.md) | Modificare, tradurre, validare o provare override dei prompt. | Valida/modifica/prova un prompt set esplicito. | Non crea config generica, soul, facts o stato live Twitch. |
| [`minnarone-twitch-onboarding`](.agents/skills/minnarone-twitch-onboarding/SKILL.md) | Preparare il workspace di un canale o intervistare per config/persona/facts. | Mostra i file esatti, richiede conferma, scrive input locali sanitizzati, valida e si ferma in shadow. | Non modifica prompt template, scarica modelli o abilita live. |
| [`minnarone-runtime-doctor`](.agents/skills/minnarone-runtime-doctor/SKILL.md) | Controllare se un runtime/profilo P0-P5 è pronto. | Esegue check read-only di tool, config, artifact, digest, capacità e sicurezza con evidenza PASS/FAIL/SKIP. | Non installa, scarica, modifica, avvia catture lunghe o invia. |

Gli umani possono seguire direttamente i percorsi sopra. I code agent devono
partire da [`AGENTS.md`](AGENTS.md), i contributor da
[`CONTRIBUTING.md`](CONTRIBUTING.md): entrambi instradano architettura, qualità,
prompt safety, dirty worktree e skill routing.

## Origine e crediti

Minnarone è stato ideato e costruito da **enkk**, che ne è l'autore e designer originale: un bot capace di ascoltare e vedere una live stream Twitch e di interagire in chat con gli altri utenti e con lo streamer senza che nessuno si accorgesse di parlare con un'intelligenza artificiale (una specie di test di Turing applicato alla chat).

- **Video di origine**: <https://www.youtube.com/watch?v=EkunaRO0uKg>
- **Transcript**: [`docs/source/transcript.md`](docs/source/transcript.md) — la trascrizione del video di enkk da cui è stata derivata la specifica di questo framework.

Questo repository generalizza quell'idea in un framework riusabile: lo stesso motore di percezione + reazione serve casi d'uso diversi (Twitch, riunioni Teams) cambiando solo la configurazione.

## Documentazione

- **[Specifica di progetto](docs/SPECIFICATION.md)** — requisiti, user stories, use case, edge case, system design e roadmap.
- **[Guida operatore Twitch](docs/twitch-operator.md)** — smoke di cattura, diagnostica VAD, runtime `adapter: twitch` e abilitazione dell'invio pubblico (shadow/live).
- **[Guida assistente meeting](docs/meeting-assistant-operator.md)** — profili sintetizzatore e suggeritore su Teams via `adapter: os_capture`.
- **[Materiale sorgente](docs/source/)** — transcript e screenshot da cui è stata derivata la specifica.

## Avvio dell'app di riferimento

L'app "Minnarone" si avvia da un **file di configurazione** YAML (soul, facts,
adapter, provider, cadenze, modalità) — senza scrivere codice.

**Prerequisiti**: Python 3.11+ (3.12 consigliato — vedi `.python-version`).

Crea e attiva prima un ambiente virtuale. Con
[uv](https://docs.astral.sh/uv/) (consigliato):

```bash
uv venv                             # crea .venv
# attivala (scegli la tua shell):
source .venv/bin/activate           # macOS / Linux
source .venv/Scripts/activate       # Windows — Git Bash
# .venv\Scripts\Activate.ps1        # Windows — PowerShell
# .venv\Scripts\activate.bat        # Windows — cmd

uv pip install -e .                 # core
uv pip install -e '.[tui]'          # + dashboard di osservabilità (textual)
uv pip install -e '.[audio]'        # + runtime audio: faster-whisper + sherpa-onnx (ASR + speaker)
uv pip install -e '.[video]'        # + runtime video Twitch: Streamlink Python + PyAV
uv pip install -e '.[vlm]'          # + captioning `vlm.backend: qwen`: transformers + torch/torchvision + Pillow
uv pip install -e '.[vlm-llamacpp]' # + captioning `vlm.backend: llamacpp`: solo Pillow (via llama-server multimodale, niente torch)
uv pip install -e '.[os-capture]'   # + cattura audio di sistema (soundcard) e schermo (mss)

# Valida la config e costruisci l'agente (dry-run, niente loop né rete):
python -m minnarone path/al/config.yaml --check

# Avvia il loop di reazione live:
python -m minnarone path/al/config.yaml

# Avvia con la dashboard TUI di osservabilità (richiede l'extra `tui`):
python -m minnarone path/al/config.yaml --tui

# Rivedi offline una run passata o un perceptions.jsonl (dashboard replay):
python -m minnarone --replay <run_dir_o_perceptions.jsonl>
```

Preferisci `pip`? Crea la venv con la stdlib (`python -m venv .venv`), attivala
e togli il prefisso `uv` (`pip install -e '.[tui]'`). Nota: una `uv venv` **non**
include `pip`, quindi con essa usa `uv pip`. I comandi di avvio qui sopra
assumono la venv attiva (oppure prefissali con `uv run`).

Gli extra si possono combinare (es. `uv pip install -e '.[os-capture,audio,vlm]'`)
e sono installabili anche con `uv sync --extra <nome>`.

> **Primo `--check`**: gli esempi Twitch/Teams verificano che il setup esista,
> quindi danno errore appena scaricati. Gli adapter Twitch richiedono
> `TWITCH_BOT_USERNAME` / `TWITCH_OAUTH_TOKEN` in `.env` (`cp .env.example .env`);
> gli esempi OS-capture e Teams richiedono un modello ONNX di speaker embedding
> locale (`speaker_embedding.model_path`) — vedi le sezioni sotto.
> `examples/llamacpp-local.example.yaml` passa `--check` senza setup extra.

## Segreti via `.env`

La CLI carica un file `.env` **all'avvio**, prima di leggere i segreti: prima
accanto al file di config, poi nel `cwd`. Le variabili già esportate nel
terminale hanno la precedenza sul file (semantica dotenv standard). Il loader è
minimale e a zero dipendenze; `.env` è gitignored — non committare mai valori
reali. Il template è [`.env.example`](.env.example) (`cp .env.example .env`).

| Variabile | Quando serve |
|-----------|--------------|
| `OPENROUTER_API_KEY` | Con `llm_provider: grok`/`deepseek` (OpenRouter). NON serve con `llm_provider: llamacpp` (LLM locale). |
| `TWITCH_BOT_USERNAME` | Con `adapter: twitch` + `twitch.chat: true` (ingestione IRC in lettura). |
| `TWITCH_OAUTH_TOKEN` | Con `adapter: twitch` + `twitch.chat: true` o invio live — token di **lettura** (`chat:read`). |
| `TWITCH_SEND_OAUTH_TOKEN` | **Solo** per `twitch.send.mode: live` — token di **scrittura** (`chat:edit`) dell'account bot dedicato. |

Il token di lettura e quello di scrittura sono deliberatamente distinti: una
config read-only non deve mai avere il potere di inviare messaggi. In `live`
entrambi devono appartenere a `TWITCH_BOT_USERNAME`: quello di lettura richiede
`chat:read`, quello di invio `chat:edit`. Sono validati all'avvio, non oltre ogni
ora e prima di un `expires_in` breve con margine di sicurezza. Deadline assolute
evitano drift dovuto alla latenza HTTP; token già nel margine falliscono chiusi
senza retry rapido. Un errore read
disarma il live, ferma il sender e la run; un errore send ferma il sender e
mantiene definitivamente in shadow la sessione ancora attiva. `off` e `shadow`
non leggono il token di invio. I valori non entrano in log, errori o artefatti;
`--check` resta offline.

## Controllo qualità

```bash
uv sync --extra dev
make quality

# esegui a richiesta tutti gli hook su tutto il repo
uv run --extra dev pre-commit run --all-files

# fai partire gli hook automaticamente al commit — in alternativa:
git config core.hooksPath .githooks   # ponte a .pre-commit-config.yaml
# ...oppure l'installazione standard di pre-commit:
uv run --extra dev pre-commit install
```

`make quality` esegue `ruff format --check`, `ruff check`, Vulture, Deptry e
Pylint limitato a `duplicate-code` (`R0801`, solo su `src` — la ripetizione di
setup nei test è ammessa). Gli stessi tool girano al commit via
[`.pre-commit-config.yaml`](.pre-commit-config.yaml) (hook locali `uv run`;
`ruff check --fix` e `ruff format` correggono anche in automatico). Il codice di
riferimento in `spike/` è escluso da tutti.

Per contributor e code agent che lavorano sui prompt esternalizzati esiste una
skill Claude Code locale al repo in [`.claude/skills/minnarone-prompts/`](.claude/skills/minnarone-prompts/SKILL.md):
documenta la mappa dei file e i vincoli non ovvi (placeholder obbligatori,
token di controllo, il confine di sicurezza cablato, la byte-invarianza dei
default impacchettati) e prescrive il flusso sicuro — modifica →
`minnarone validate-prompts` → test mirati → render di anteprima.

### Prerequisiti runtime

- **`OPENROUTER_API_KEY`**: mettila in `.env` (o esportala nell'ambiente).
  Non serve con `llm_provider: llamacpp` (vedi [LLM locale](#llm-locale-llamacpp)).
- **Permessi macOS**: la cattura di percezione richiede di autorizzare il
  processo (es. il terminale) in *Impostazioni di sistema → Privacy e sicurezza*
  per **Microfono** (audio) e **Registrazione schermo** (video/schermo). L'audio
  di sistema può richiedere tooling aggiuntivo (loopback). Senza i permessi il
  loop di reazione gira ma non riceve percezioni.

### Loop di percezione live (adapter)

`Agent.run()` fa girare CONCORRENTEMENTE tre cose: il loop di reazione, il loop
del Summarizer (memoria a breve termine, cadenza `summarizer_interval`) e la
*pompa di percezione*, che instrada ogni `RawEvent` dell'adapter al perceiver del
suo canale (`chat`/`audio`/`video`) → store.

- Il canale **chat** è cablato sempre (nessun modello): `adapter: twitch`
  costruisce il runtime Twitch dalla config e dalle credenziali in ambiente.
- Il canale **audio** usa VAD locale + faster-whisper + speaker embedding
  `sherpa-onnx` quando `twitch.audio: true` (o `os_capture.audio: true`) e i
  backend locali sono installati/configurati.
- Il canale **video** usa Streamlink + PyAV + un backend di captioning locale
  quando `twitch.video: true` e l'extra `video` è installato. Il backend è scelto
  da `vlm.backend`: `qwen` (Qwen2-VL torch, richiede `vlm.model` + extra `vlm`) o
  `llamacpp` (llama-server multimodale, extra leggero `vlm-llamacpp`).
- L'adapter **`os_capture`** (mic + audio di sistema loopback + registrazione
  schermo) osserva la macchina locale invece di uno stream remoto.

## Modalità di output e commentatore

Lo **switch `mode`** è solo configurazione (stesso motore):

- `public` instrada l'output sul canale pubblico (console e, se abilitato,
  `twitch.send`). Su Twitch in modalità public la persona è **sempre**
  `original_chat` (vedi sotto).
- `private` mantiene l'output sulla sola **console locale** (`[PRIVATE]`): nessun
  messaggio pubblico viene mai inviato, indipendentemente da `twitch.send`.

Il commentatore locale si configura con `commentator.profiles`: un dizionario di
**profili** indicizzati per stile. Un profilo presente attiva il reattore
corrispondente; un dizionario di profili vuoto = commentatore spento.

| Stile (`commentator.profiles.<stile>`) | Cosa fa | Modalità |
|----------------------------------------|---------|----------|
| `operator` | Telecronaca/commento locale privato per l'operatore. | `private` |
| `original_chat` | Persona pubblica per la chat Twitch (contratto `RE:`/`MSG:`). | `public` (Twitch) o `private` (dry-run locale) |
| `meeting_synthesizer` | Riassunti strutturati periodici di una riunione. | `private` |
| `suggester` | Suggerimenti contestuali su ogni percezione. | `private` |

`meeting_synthesizer` e `suggester` richiedono `mode: private` (validato al
`--check`). Su `adapter: twitch` + `mode: public` è ammesso solo `original_chat`:
un profilo diverso viene rifiutato con un errore chiaro.

## Output pubblico in chat Twitch (`twitch.send`)

L'invio pubblico in chat è **gated** e spento di default. Il blocco
`twitch.send` (dentro `twitch:`) ha tre modalità:

- `off` (default): nessun `PRIVMSG` inviato.
- `shadow`: prova senza rete — l'agente decide cosa scriverebbe ma non invia
  nulla. È il passo di rodaggio raccomandato (shadow-first).
- `live`: invio reale in chat.

Guardrail (default conservativi): **allow-list** di canali (`allowed_channels`;
`mode: live` richiede che il canale sia in lista), **budget** ben sotto i limiti
IRC di Twitch (`max_per_minute: 1`, `max_per_hour: 20`), **kill-switch** con
auto-degrado a shadow dopo `failure_threshold` invii falliti consecutivi (default
3), e un **token di scrittura separato** (`TWITCH_SEND_OAUTH_TOKEN`) di un
account bot dedicato. Nella TUI premi `p` due volte entro 3 secondi per
promuovere e `k` una volta per il kill-switch. Procedura completa nella
[guida operatore Twitch](docs/twitch-operator.md).

## Commentatore locale su Teams (cattura SO)

Minnarone può fare da **commentatore locale** o **assistente meeting** su una
call Teams a cui partecipi: osserva l'**audio di sistema** (le voci degli altri
partecipanti, catturate dal loopback dell'uscita audio) e lo **schermo** (slide,
volti, testo condivisi), e produce output solo sulla **console locale**
(`[PRIVATE]`). Non invia nulla dentro la riunione: nessun messaggio, nessun
audio, nessun output pubblico.

Preset pronti all'uso:

- [examples/teams-commentator.yaml](examples/teams-commentator.yaml) — profilo `operator`.
- [examples/teams-meeting-assistant.yaml](examples/teams-meeting-assistant.yaml) — profili `meeting_synthesizer` + `suggester`.
- [examples/teams-meeting-full.yaml](examples/teams-meeting-full.yaml) — configurazione completa.

Dettagli operativi (profili, TUI, troubleshooting) nella
[guida assistente meeting](docs/meeting-assistant-operator.md).

### Installazione

La cattura del SO vive nell'extra `os-capture` (audio di sistema via `soundcard`,
schermo via `mss`):

```bash
pip install -e '.[os-capture]'   # oppure: uv sync --extra os-capture
```

L'extra `os-capture` copre solo la **cattura raw**. Per far girare davvero i
modelli servono anche:

- l'extra `audio` (faster-whisper + sherpa-onnx) perché l'audio venga trascritto
  e diarizzato (ASR/speaker);
- l'extra `vlm` (transformers + torch) perché lo schermo venga descritto dal
  captioner Qwen2-VL (import lazy: il modello si carica alla prima descrizione).

```bash
pip install -e '.[os-capture,audio,vlm]'
```

Con il solo `os-capture` puoi fare diagnostica di cattura (sotto) ma non ASR/VLM.

### Setup

1. **Uscita audio di default**: il loopback cattura l'**uscita audio predefinita
   del sistema**. Imposta come dispositivo di uscita di default quello su cui
   Teams riproduce l'audio (Windows: *Impostazioni → Audio → Uscita*; Linux: il
   sink PulseAudio corrispondente). Se Teams suona su un altro dispositivo, il
   loopback catturerà il silenzio.
2. **Permesso di cattura schermo**: autorizza il processo (es. il terminale) a
   registrare lo schermo. Su macOS è *Impostazioni di sistema → Privacy e
   sicurezza → Registrazione schermo*; senza il permesso i frame arrivano
   vuoti/neri.
3. **Selezione del monitor**: scegli quale schermo catturare con
   `os_capture.monitor` (indice `>= 1`; 1 = monitor primario). Lo stesso indice è
   esposto dallo smoke come `--monitor`.

### Diagnostica (`minnarone-oscapture-smoke`)

Prima di attivare ASR/VLM conviene verificare che audio e schermo vengano
davvero catturati. Lo smoke della cattura SO è **capture-only** (nessun ASR/VLM,
non richiede `OPENROUTER_API_KEY`) e scrive artifact bounded nella directory
`--output`: `raw/audio/*.pcm` (PCM mono 16 kHz s16le), `raw/video/*.jpg`, e
`stats.json` con conteggi ed eventuali failure.

> L'entry point `minnarone-oscapture-smoke` vive nel virtualenv, quindi è sul
> tuo `PATH` solo con la venv **attivata** (vedi la sezione di installazione).
> Altrimenti lancialo senza attivazione con
> `python -m minnarone.oscapture_smoke ...` oppure
> `uv run minnarone-oscapture-smoke ...`. Richiede l'extra `os-capture`.

Verifica la cattura audio dal loopback dell'uscita di default:

```bash
minnarone-oscapture-smoke \
  --duration 30 \
  --output ./.smoke/os-audio \
  --audio \
  --audio-chunk-seconds 1.0
```

Verifica la cattura dello schermo dal monitor scelto:

```bash
minnarone-oscapture-smoke \
  --duration 30 \
  --output ./.smoke/os-video \
  --video \
  --video-fps 1.0 \
  --monitor 1
```

Per controllare solo la segmentazione VAD sull'audio (conteggi/durate senza
ASR), usa `--vad-diagnostic` (abilita anche l'audio): `stats.json` includerà
`vad_utterances` e `vad_utterance_durations_ms`.

```bash
minnarone-oscapture-smoke \
  --duration 30 \
  --output ./.smoke/os-vad \
  --vad-diagnostic
```

### Avvio

Valida prima a secco (nessun hardware aperto, nessuna rete), poi avvia il loop:

```bash
python -m minnarone examples/teams-commentator.yaml --check
python -m minnarone examples/teams-commentator.yaml
```

### Limiti multi-platform

- **Windows** (WASAPI) e **Linux** (monitor PulseAudio): loopback dell'uscita di
  default **nativo**, nessun tooling aggiuntivo.
- **macOS**: `soundcard` **non** supporta il loopback. Serve un device di
  loopback esterno (es. BlackHole) impostato come uscita di default per far
  arrivare l'audio di sistema alla cattura.

## Diarizzazione degli speaker

La pipeline audio (VAD → ASR → speaker tagging) etichetta ogni utterance con una
di **tre etichette canoniche**:

- `streamer` — l'operatore locale / chi conduce la sessione;
- `altro` — qualsiasi altra voce (ospiti, audio di un video riprodotto, ecc.); il
  clustering interno resta per-cluster, ma l'etichetta esposta collassa in
  un'unica identità "altro";
- `?` — utterance troppo breve o non attribuibile.

Le vecchie etichette `speaker_N` non esistono più. L'operatore può **marcare
manualmente lo streamer** durante una run con la TUI premendo `s` ("Marca
streamer"): fissa il cluster dell'ultima utterance assegnata come streamer e
disabilita la scelta automatica per quel cluster (supporta anche più streamer).

Il modello di speaker embedding va scelto **coerente con la lingua** dell'audio.
`speaker_embedding.dimension` deve **corrispondere al modello scelto**:

- modello CAM++ inglese raccomandato
  `3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx` → `dimension: 512`.

Minnarone non scarica alcun modello: punta `speaker_embedding.model_path` a un
file ONNX locale. Per il modello VoxCeleb raccomandato parti da
`speaker_clustering.threshold: 0.5`: più alto significa più splitting; taralo su
audio rappresentativo.

## Esempio di config (`config.yaml`)

Esempio Twitch chat-only (basato su
[examples/twitch.example.yaml](examples/twitch.example.yaml)). Per altri scenari
vedi gli esempi in [examples/](examples/): `twitch-commentator.example.yaml`,
`twitch-original-chat.example.yaml`, `teams-commentator.yaml`,
`teams-meeting-assistant.yaml`, `teams-meeting-full.yaml`.

```yaml
mode: public              # public | private (private = solo console locale)
soul_path: soul.md        # identità dell'agente
facts_dir: facts          # directory di fatti permanenti (uno o più file)
adapter: twitch           # sorgente di percezione (twitch | os_capture)
llm_provider: grok        # grok | deepseek (slug via llm_params.model) | llamacpp (locale, modello fissato dal server)
agent_name: minnarone     # nome a cui l'agente risponde (rilevamento menzioni)

twitch:
  channel: minnarone
  quality: best
  chat: true
  audio: false            # true = percezione audio locale (richiede extra audio + model_path)
  video: false            # true = frame video (richiede extra video/vlm + vlm.model)
  audio_chunk_seconds: 1.0
  video_fps: 1.0
  # Invio pubblico gated. Default off. Vedi docs/twitch-operator.md prima di live.
  send:
    mode: off             # off | shadow | live  (quota il valore: YAML legge on/off come bool)
    allowed_channels: []
    max_per_minute: 1
    max_per_hour: 20
    failure_threshold: 3

llm_params:
  model: x-ai/grok-4.5
  reasoning:
    effort: low             # low | medium | high

senser_interval: 0.5
idle_interval: 150.0
summarizer_interval: 30.0   # cadenza del Summarizer (memoria a breve termine)
recent_chat_window: 15
perception_queue_size: 32   # tetto della work queue percezioni (backpressure)
perception_shutdown_timeout: 5.0

vad:
  mode: 2                   # 0 meno aggressivo, 3 più aggressivo
  frame_ms: 30              # 10 | 20 | 30
  padding_ms: 300           # ring/hangover VAD
  max_utterance_seconds: 30.0

asr:
  model: large-v3-turbo
  device: auto
  compute_type: default
  language: null
  beam_size: 5
  condition_on_previous_text: false

speaker_embedding:
  model_path: null          # raccomandato: 3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
  provider: cpu
  num_threads: 1
  dimension: 512            # CAM++ inglese VoxCeleb; deve combaciare col modello.

speaker_clustering:
  threshold: 0.5            # punto di partenza VoxCeleb; tara su audio rappresentativo.
  warmup_seconds: 60.0
  min_update_seconds: 1.0

video:
  sample_every: 1              # ulteriore sampling prima del captioner
  dedup_change_threshold: 0.0  # 0 = salta solo frame byte-identici

vlm:
  backend: qwen                # qwen (torch locale) | llamacpp (llama-server multimodale)
  model: null                  # percorso/id locale Qwen2-VL-compatible (solo backend qwen)
  device: auto
  device_map: auto
  torch_dtype: auto
  max_new_tokens: 48
  timeout_seconds: 30.0
  language: en                 # caption concise in inglese di default

commentator:
  language: it
  # Nessun profilo = commentatore spento. Per attivarlo aggiungi un profilo, es.:
  #   profiles:
  #     original_chat:        # persona chat pubblica (unica ammessa con twitch + public)
  #       idle_interval: 30.0

# --- punti di estensione v2 (presenti ma INERTI nell'MVP) ---
disclosure:
  announce_ai: false    # l'unico cablato: stance di disclosure nel prompt
retention:
  perceptions_days: 7   # inerte in MVP
auto_memory: false      # inerte in MVP
```

I punti `retention` e `auto_memory` sono presenti nello schema ma non alterano
il comportamento (estensione v2). Le run locali possono contenere
`perceptions.jsonl`, sommari e `debug/prompts` / `debug/events.jsonl`: dopo un
opt-out o una revoca elimina manualmente la directory pertinente
`.local/<agente>/runs/run-*`. Non pubblicare questi artefatti.

## File di prompt (persona, regole, formato)

Il testo di prompt **tunabile** (persona, regole per-stile, formato di risposta,
le varianti di situazione e l'istruzione del summarizer) vive in file Markdown
esterni, non nel codice Python. Sono impacchettati nel wheel sotto
`src/minnarone/prompts/` e letti all'avvio:

| File | Cos'è |
|------|-------|
| `rules.md` | Regole persona/stile original-chat. Usa `{{channel}}`. |
| `intro.md` | Banner "situazione attuale" + riga canale. Usa `{{channel}}`. |
| `situations.md` | Le 6 varianti di situazione (a chiavi `## <chiave>`). Usa `{{user}}`, `{{mention}}`, `{{reason}}`; deve mantenere il token `#end_conv`. I corpi citano gli header di sezione via `{{header_memoria}}`, `{{header_tuoi_ultimi_messaggi}}`, `{{header_conversazione_recente}}` (risolti da `headers.md`, ammessi in ogni sezione). |
| `headers.md` | Gli header di sezione e le righe di framing del prompt di reazione (a chiavi `## <chiave>`: `regole`, `memoria`, `memoria_suffix`, `situazione`, `chat_recente`, …, più `riassunto_std`/`conversazione_recente_std`/`situazione_std` per gli stili non-original-chat, dove il prefisso markdown `## ` resta strutturale). `{{channel}}` obbligatorio solo in `cosa_sai`. I riferimenti nei corpi si risolvono dagli stessi valori: rinominare un header qui aggiorna ogni testo che lo cita. |
| `format.md` | Il contratto di risposta `RE:`/`MSG:`. Deve mantenere `RE:`, `MSG:`, `#end_conv`. |
| `operator.md` | Regole del commentatore locale. Usa `{{language}}`. |
| `meeting_synthesizer.md` | Regole della sintesi riunione. Usa `{{language}}`. |
| `suggester.md` | Regole del suggeritore privato. Usa `{{language}}`; deve mantenere il token `#nothing`. |
| `summarizer.md` | Testo del summarizer della memoria a breve termine (sezioni a chiavi). |

### Sovrascrivere i prompt (`prompts_dir`)

Imposta `prompts_dir` nella config, nello stesso spirito di `soul_path` /
`facts_dir` (il percorso è relativo al file di config):

```yaml
prompts_dir: my-prompts   # una directory accanto al file di config
```

La risoluzione è **per-file**: per ogni file di prompt, se esiste sotto
`prompts_dir` vince, altrimenti si usa il default impacchettato. Puoi
sovrascrivere un solo file e lasciare che gli altri cadano sul default. Se
`prompts_dir` è assente, si usano solo i default impacchettati: un fresh install
funziona senza configurazione.

Il loader è **fail-fast**: un file mancante, un placeholder mancante o ignoto, un
token di controllo mancante o una sezione obbligatoria vuota fanno fallire
l'avvio — un prompt tunabile non può mai degradare a testo vuoto.

Per validare un override senza avviare l'app:
`minnarone validate-prompts --prompts-dir my-prompts` (oppure `--config
config.yaml` per leggere `prompts_dir` dalla config): exit 0 se tutto è valido,
una riga per file rotto altrimenti.

### Placeholder

La sostituzione usa le doppie graffe `{{nome}}`. I nomi in whitelist sono
`{{channel}}`, `{{language}}`, `{{user}}`, `{{mention}}`, `{{reason}}` e i
riferimenti agli header `{{header_memoria}}`, `{{header_tuoi_ultimi_messaggi}}`,
`{{header_conversazione_recente}}` (risolti da `headers.md`). I loro
valori vengono da config/codice (dati fidati, mai contenuto percepito), le graffe
singole `{ }` e i `<...>` sopravvivono intatti, e un valore iniettato non viene
mai ri-scansionato (niente injection ricorsiva via template).

`{{channel}}` segue `twitch.channel` del file di config — non cablare un nome di
canale dentro i file di prompt.

### Canale non italiano / multi-canale

L'esternalizzazione dei prompt **È** il meccanismo di localizzazione — non c'è
alcun motore i18n e il progetto non fornisce set tradotti. Per un canale in
un'altra lingua: copia `src/minnarone/prompts/` in una nuova directory, riscrivi
i `.md` nella tua lingua (mantenendo placeholder e token di controllo) e punta
`prompts_dir` lì. Nessuna modifica al codice. Un esempio minimo e parziale sta in
[examples/prompts-en/](examples/prompts-en/).

### Confine di sicurezza (cosa NON puoi sovrascrivere)

Le regole **anti-injection** e di **disclosure** sono cablate in `prompt.py` e
volutamente NON stanno tra i file editabili. Le regole di stile tunabili sono
rese prima e la stance configurata viene aggiunta dopo: un override non può
diventare l'ultima istruzione contraddittoria. Con `announce_ai: false` Minnarone
non si annuncia spontaneamente ma non deve mentire se interrogato; `true`
permette una risposta esplicita.

## LLM locale (llama.cpp)

Con `llm_provider: llamacpp` il Reactor genera le reazioni contro un
`llama-server` locale ([llama.cpp](https://github.com/ggml-org/llama.cpp)) con
API OpenAI-compatibile: **niente `OPENROUTER_API_KEY`**, nessuna dipendenza
runtime nuova. Il server va avviato **a mano** prima del loop live (minnarone
non gestisce il processo, fa solo un health-check su `GET /health` all'avvio):

```bash
llama-server -m gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf --port 8080 -ngl 99 -c 8192 --reasoning off --parallel 1
```

Config (esempio completo in
[examples/llamacpp-local.example.yaml](examples/llamacpp-local.example.yaml)):

```yaml
llm_provider: llamacpp
llamacpp:
  base_url: http://127.0.0.1:8080   # default; porta esplicita richiesta
```

Note:

- Niente `model` in config né nel body: il server serve il solo modello
  caricato (lo slug reale compare nei meta di osservabilità della risposta).
- Gli `llm_params` (`temperature`, `max_tokens`, `timeout`, ...) passano come
  per i provider cloud; `thinking` viene droppato (il reasoning si spegne
  server-side con `--reasoning off`).
- `--check` resta un dry-run senza rete: valida solo la forma di `base_url`.
  Se all'avvio live il server è giù o sta ancora caricando il modello (503),
  la CLI esce con un errore che include il comando qui sopra.

### Captioning video locale via llama.cpp (`vlm.backend: llamacpp`)

Il canale video può descrivere i frame usando un `llama-server` **multimodale**
(modello + proiettore `--mmproj`, es. Gemma multimodale) invece del backend
torch Qwen2-VL. Vantaggio decisivo su GPU piccole (~4 GB): **una sola istanza
`llama-server` multimodale serve sia le reazioni testo (`llm_provider:
llamacpp`) sia il captioning**, evitando la doppia residenza in VRAM di
torch-VLM + LLM. Nessuna dipendenza runtime nuova (transformers/torch non
servono con questo backend): il trasporto è lo stesso urllib del provider LLM
locale.

Avvia l'istanza multimodale a mano, aggiungendo il proiettore `--mmproj` e
`--parallel 2` (così testo e visione girano in concorrenza sulla stessa
istanza, costo ~10 MiB VRAM):

```bash
llama-server -m <modello.gguf> --mmproj <mmproj.gguf> --port 8080 -ngl 99 -c 16384 --reasoning off --parallel 2
```

> **Contesto e `--parallel`**: `llama-server` divide `-c` tra gli slot, quindi
> il contesto per-richiesta è `n_ctx / n_slots`. Con `--parallel 2` serve
> `-c 16384` per avere 8192 token a slot: un prompt multi-canale (chat + audio +
> video + soul/facts) supera facilmente i 2048 che darebbe `-c 4096 --parallel 2`,
> e llama-server risponderebbe `400 "exceeds the available context size"`. La KV
> cache di E2B è piccola: quadruplicare il contesto costa ~+80 MiB VRAM.

Config: il backend riusa `llamacpp.base_url` (stessa istanza del provider LLM),
mentre `prompt`/`language`/`max_new_tokens`/downscale/`max_caption_chars`
restano nel blocco `vlm:`:

```yaml
vlm:
  backend: llamacpp     # captiona i frame via l'istanza llama-server multimodale
llamacpp:
  base_url: http://127.0.0.1:8080   # condiviso col provider LLM locale
```

Note:

- All'avvio del loop live (mai in `--check`) la CLI verifica via `GET /props`
  che l'istanza esponga la visione (`modalities.vision == true`). Se manca il
  proiettore, esce con un errore azionabile che ricorda `--mmproj`. Il check
  gira anche con `llm_provider` cloud (il captioner usa comunque
  `llamacpp.base_url`).
- Contratto best-effort: su errore di trasporto/HTTP a runtime il captioner
  ritorna una caption vuota (salta il frame) e logga l'evento, senza uccidere
  il canale video. Il backend `qwen` resta invariato per chi lo seleziona.
- **Installazione leggera**: questo backend richiede solo l'extra
  `vlm-llamacpp` (`pip install -e '.[vlm-llamacpp]'` → solo Pillow), non l'extra
  `vlm` pesante (torch/transformers), che serve solo al backend `qwen`.

## Smoke Twitch capture-only

Lo smoke Twitch è separato dal CLI dell'agente e non richiede
`OPENROUTER_API_KEY`. La guida completa per operatori, artifact, troubleshooting
e runtime chat-only `adapter: twitch` con output console è in
[docs/twitch-operator.md](docs/twitch-operator.md).
Per la chat servono le credenziali bot in ambiente (via `.env` o esportate):
`TWITCH_BOT_USERNAME` e `TWITCH_OAUTH_TOKEN`.

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-chat
```

Per abilitare anche la cattura audio raw servono `streamlink` e `ffmpeg`
installati sul sistema e disponibili su `PATH`:

```bash
streamlink --version
ffmpeg -version

minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-audio \
  --audio \
  --audio-chunk-seconds 1.0 \
  --quality audio_only
```

Per validare solo la segmentazione VAD sull'audio Twitch, senza ASR:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-vad \
  --no-chat \
  --vad-diagnostic \
  --quality audio_only
```

Per campionare anche frame video JPEG a bassa frequenza:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-video \
  --video \
  --video-fps 1.0 \
  --quality best
```

Gli artifact sono scritti nella directory passata a `--output`:
`perceptions.jsonl` per la chat, `raw/audio/*.pcm` per un numero limitato di
sample PCM mono 16 kHz signed 16-bit little-endian, `raw/video/*.jpg` per un
numero limitato di frame JPEG, e `stats.json` con conteggi ed eventuali failure.
Con `--vad-diagnostic`, `stats.json` include anche `vad_utterances` e
`vad_utterance_durations_ms`. I file `.pcm` e `.jpg` provano solo la cattura raw
da FFmpeg: lo smoke capture-only non esegue ASR, diarizzazione o captioning VLM.
La guida operatore include anche smoke manuali per trascrivere un `.pcm` con
`faster-whisper`, estrarre speaker embedding con `sherpa-onnx`, e avviare il
runtime console con `twitch.audio: true`. È disponibile anche uno smoke
chat-only dedicato: `minnarone-twitch-chat-smoke`.

## Stato

Il runtime core è **implementato**: percezione Twitch (chat/audio/video) con
invio pubblico gated (shadow/live), commentatore locale e assistente meeting su
Teams (profili `operator`, `meeting_synthesizer`, `suggester`), diarizzazione
degli speaker (`streamer`/`altro`/`?` + marcatura manuale), dashboard TUI di
osservabilità e replay offline delle run.

Il lavoro rimanente è centrato sulle **run di accettazione live con
human-in-the-loop** (HITL). Vedi la
[roadmap](docs/SPECIFICATION.md#10-roadmap-per-priorità) per MVP / v2 / v3.

## Offrimi un caffè

Se il progetto ti è utile, puoi offrirmi un caffè ☕

[![Offrimi un caffè — PayPal](https://img.shields.io/badge/Offrimi%20un%20caff%C3%A8-PayPal-00457C?logo=paypal&logoColor=white)](https://paypal.me/CarloSergi)

## Licenza

Distribuito con licenza [MIT](LICENSE).
