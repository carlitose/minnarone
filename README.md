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
  `export OPENROUTER_API_KEY=...`
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

La pompa funziona quando si **inietta una `SourceAdapter`** in `build_agent(..., adapter=...)`:
il canale **chat** è cablato sempre (nessun modello). I canali **audio/video**
richiedono i rispettivi backend (VAD/ASR/VLM) e si attivano solo iniettando
`audio_perceiver=` / `video_perceiver=`. Il backend **device** dell'`os_capture`
(mic + audio di sistema, registrazione schermo) e i modelli audio/video restano
il **passo manuale** da cablare: senza un adapter iniettato, `run()` gira il solo
motore di reazione + summarizer.

### Smoke Twitch capture-only

Lo smoke Twitch e' separato dal CLI dell'agente e non richiede
`OPENROUTER_API_KEY`. Per la chat servono credenziali bot in ambiente:

```bash
export TWITCH_BOT_USERNAME=nome_bot
export TWITCH_OAUTH_TOKEN=oauth:token_o_senza_prefisso

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
I file `.pcm` e `.jpg` provano solo la cattura raw da FFmpeg: queste slice non
implementano ASR, VAD, diarizzazione o captioning VLM.

### Esempio di config (`config.yaml`)

```yaml
mode: public            # public (operativo) | private (accettato, whisper = v2)
soul_path: soul.md      # identità dell'agente
facts_dir: facts        # directory di fatti permanenti (uno o più file)
adapter: os_capture     # sorgente di percezione (cattura del SO)
llm_provider: grok      # grok | deepseek (slug modello override via llm_params.model)
agent_name: minnarone   # nome a cui l'agente risponde (rilevamento menzioni)
llm_params:
  temperature: 0.7
# --- punti di estensione v2 (presenti ma INERTI nell'MVP) ---
disclosure:
  announce_ai: false    # l'unico cablato: stance di disclosure nel prompt
retention:
  perceptions_days: 7   # inerte in MVP
auto_memory: false      # inerte in MVP
```

Lo **switch `mode`** è solo configurazione (stesso motore): `public` instrada
sul canale pubblico (console); `private` è **accettato** ma l'output whisper non
è implementato nell'MVP — il percorso esiste e segnala chiaramente
"non implementato" se usato. I punti `retention` e `auto_memory` sono presenti
nello schema ma non alterano il comportamento (estensione v2).

## Stato

Fase di design. Vedi la [roadmap](docs/SPECIFICATION.md#10-roadmap-per-priorità) per MVP / v2 / v3.
