# Minnarone Framework

Framework riusabile per costruire agenti AI che **percepiscono un contesto live multimodale** (audio, video/schermo, chat, eventi di piattaforma) e **reagiscono proattivamente** — sia come partecipante pubblico (co-host streamer, commentatore di gruppo) sia come assistente privato (suggerimenti per venditori, presentatori).

Nasce dalla generalizzazione di **Minnarone**, un bot che osservava live stream Twitch e interagiva in chat in modo indistinguibile da un umano.

## Documentazione

- **[Specifica di progetto](docs/SPECIFICATION.md)** — requisiti, user stories, use case, edge case, system design e roadmap.
- **[Materiale sorgente](docs/source/)** — transcript e screenshot da cui è stata derivata la specifica.

## Avvio dell'app di riferimento

L'app "Minnarone" si avvia da un **file di configurazione** YAML (soul, facts,
adapter, provider, cadenze, modalità) — senza scrivere codice.

```bash
pip install -e .            # core
pip install -e '.[tui]'     # + dashboard di osservabilità (textual)
pip install -e '.[audio]'   # + runtime audio Twitch: faster-whisper + sherpa-onnx
pip install -e '.[video]'   # + runtime video Twitch: Streamlink Python + PyAV
pip install -e '.[vlm]'     # + captioning video locale: transformers + torch/torchvision + Pillow

# Valida la config e costruisci l'agente (dry-run, niente loop né rete):
python -m minnarone path/al/config.yaml --check

# Avvia il loop di reazione live:
python -m minnarone path/al/config.yaml
```

## Controllo qualità

```bash
uv sync --extra dev
make quality

# abilita l'hook git pre-commit tracciato nel repo
git config core.hooksPath .githooks
```

Il target esegue Ruff, Vulture, Deptry e Pylint limitato a `duplicate-code`
(`R0801`).

### Prerequisiti

- **`OPENROUTER_API_KEY`**: esportala nell'ambiente — il provider LLM
  (OpenRouter, `grok`/`deepseek` via config) la legge da lì.
  `read -r -s -p "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo; export OPENROUTER_API_KEY`
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

La pompa funziona quando si **inietta una `SourceAdapter`** in
`build_agent(..., adapter=...)`; inoltre `adapter: twitch` costruisce oggi il
runtime Twitch dalla config e dalle credenziali in ambiente. Il canale **chat**
è cablato sempre (nessun modello). Il canale **audio** usa VAD locale +
faster-whisper + speaker embedding `sherpa-onnx` quando `twitch.audio: true` e i
backend locali sono installati/configurati; in test si può ancora iniettare
`audio_perceiver=`. Il canale **video** usa Streamlink + PyAV + un backend locale
Qwen2-VL quando `twitch.video: true`, `vlm.model` è configurato e gli extra
`video`/`vlm` sono installati; in test si può ancora iniettare `video_perceiver=`.
Il backend **device**
dell'`os_capture` (mic + audio di sistema, registrazione schermo) resta il
**passo manuale** da cablare: senza un adapter iniettato o `adapter: twitch`,
`run()` gira il solo motore di reazione + summarizer.

Per usare Minnarone come commentatore locale, abilita `commentator.enabled:
true` e usa `mode: private`: l'output resta sulla console locale (`[PRIVATE]`)
e non esiste un path di invio pubblico Twitch.

### Smoke Twitch capture-only

Lo smoke Twitch e' separato dal CLI dell'agente e non richiede
`OPENROUTER_API_KEY`. La guida completa per operatori, artifact, troubleshooting
e runtime chat-only `adapter: twitch` con output console e' in
[docs/twitch-operator.md](docs/twitch-operator.md).
Per la chat servono credenziali bot in ambiente:

```bash
read -r -p "TWITCH_BOT_USERNAME: " TWITCH_BOT_USERNAME; export TWITCH_BOT_USERNAME
read -r -s -p "TWITCH_OAUTH_TOKEN: " TWITCH_OAUTH_TOKEN; echo; export TWITCH_OAUTH_TOKEN

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
runtime console con `twitch.audio: true`.

### Esempio di config (`config.yaml`)

```yaml
mode: public            # public | private+commentator = console locale; private solo = whisper v2
soul_path: soul.md      # identità dell'agente
facts_dir: facts        # directory di fatti permanenti (uno o più file)
adapter: os_capture     # sorgente di percezione (cattura del SO)
llm_provider: grok      # grok | deepseek (slug modello override via llm_params.model)
agent_name: minnarone   # nome a cui l'agente risponde (rilevamento menzioni)
llm_params:
  temperature: 0.7
vad:
  mode: 2                  # 0 meno aggressivo, 3 più aggressivo
  frame_ms: 30             # 10 | 20 | 30
  padding_ms: 300          # ring/hangover VAD
  max_utterance_seconds: 30.0
asr:
  model: large-v3-turbo
  device: auto
  compute_type: default
  condition_on_previous_text: false
speaker_embedding:
  model_path: null         # percorso locale a un modello ONNX sherpa-onnx
  provider: cpu
  num_threads: 1
  dimension: 192
speaker_clustering:
  threshold: 0.6
  warmup_seconds: 60.0
  min_update_seconds: 1.0
video:
  sample_every: 1              # ulteriore sampling prima del captioner
  dedup_change_threshold: 0.0  # 0 = salta solo frame byte-identici
vlm:
  model: null                  # percorso/id locale Qwen2-VL-compatible
  device: auto
  device_map: auto
  torch_dtype: auto
  max_new_tokens: 48
  timeout_seconds: 30.0
  language: en                 # caption concise in inglese di default
commentator:
  enabled: false               # true + mode: private = commenti locali in console
  language: it
  idle_interval: null          # override opzionale per commenti proattivi
# --- punti di estensione v2 (presenti ma INERTI nell'MVP) ---
disclosure:
  announce_ai: false    # l'unico cablato: stance di disclosure nel prompt
retention:
  perceptions_days: 7   # inerte in MVP
auto_memory: false      # inerte in MVP
```

Lo **switch `mode`** è solo configurazione (stesso motore): `public` instrada
sul canale pubblico (console). `private` senza `commentator.enabled: true` resta
il percorso whisper v2 e segnala chiaramente "non implementato" se usato;
`private` con `commentator.enabled: true` è invece supportato oggi come
commentatore locale su console (`[PRIVATE]`). I punti `retention` e
`auto_memory` sono presenti nello schema ma non alterano il comportamento
(estensione v2).

## Stato

Fase di design. Vedi la [roadmap](docs/SPECIFICATION.md#10-roadmap-per-priorità) per MVP / v2 / v3.
