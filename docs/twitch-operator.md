# Twitch Operator Handoff

This guide covers the capture-only Twitch smoke workflow, the audio VAD
diagnostic, and the `adapter: twitch` main runtime path for chat-only, local
audio perception, and PyAV video frame capture. The smoke command is
deliberately separate from `python -m minnarone`: it does not call an LLM, does
not need
`OPENROUTER_API_KEY`, does not run ASR, and does not send chat messages.

## System Prerequisites

Minnarone requires Python 3.11 or newer. The repo workflows below use `uv`; if
you use another environment manager, keep the same optional extras and commands
semantics.

Install the Streamlink CLI and `ffmpeg` as system tools for capture-only smoke.
They must be available on `PATH`. The main PyAV video runtime additionally uses
the Python `streamlink` package from the `video` extra.

```bash
# macOS
brew install streamlink ffmpeg

# Debian/Ubuntu
sudo apt-get install streamlink ffmpeg

# Checks
python --version
uv --version
streamlink --version
ffmpeg -version
```

Chat-only smoke does not use Streamlink or FFmpeg, but audio and video capture
do.

## Python Extras Matrix

Install only the local perception pieces you are validating. The base package is
enough for config parsing, chat perception, prompt/reaction code, and console
output; local audio/video models are opt-in.

```bash
uv sync --extra dev      # tests, lint, quality checks
uv sync --extra asr      # faster-whisper transcription smoke
uv sync --extra speaker  # isolated sherpa-onnx speaker embedding dependency
uv sync --extra audio    # faster-whisper + sherpa-onnx speaker embeddings
uv sync --extra video    # Python streamlink + PyAV + NumPy frame decode
uv sync --extra vlm      # transformers + torch/torchvision + accelerate + Pillow Qwen2-VL captioning
uv sync --extra tui      # Textual read-only dashboard view
```

Dependency ownership:

- VAD uses `webrtcvad-wheels`, currently installed with the base package because
  the VAD config/runtime boundary is always importable.
- ASR uses `faster-whisper`; it is imported only when `FasterWhisperAsr` is
  constructed.
- Speaker embeddings use `sherpa-onnx` and `sherpa-onnx-core`; they are imported
  only when the speaker backend is constructed.
- Twitch video runtime uses the Python `streamlink` package, `av`, and NumPy;
  capture-only smoke still relies on the system Streamlink CLI and FFmpeg.
- VLM captioning uses `transformers`, `torch`, `torchvision`, `accelerate`, and
  Pillow; no VLM is downloaded by tests.

## Model Setup

Minnarone does not commit model binaries or secrets. Configure model ids/paths
in YAML and keep large downloads in a local model directory outside the repo if
possible.

Recommended starting points:

- ASR: `asr.model: large-v3-turbo`, `condition_on_previous_text: false`, and
  `language: null` or `language: it` if the stream is consistently Italian. If
  your `faster-whisper` install expects the CTranslate2 shorthand, use
  `model: turbo`.
- Speaker embedding: a local sherpa-onnx CAM++/3D-Speaker-style ONNX model with
  `speaker_embedding.dimension: 192`, `provider: cpu`, and `num_threads: 1` or
  `2`. Set `speaker_embedding.model_path` to the actual `.onnx` file.
- VLM: a local Qwen2-VL-compatible Hugging Face model directory or model id in
  `vlm.model`. Captions are concise English by default because they are internal
  context for the LLM, not final user-facing prose.

Apple Silicon starting points for a MacBook/Mac Studio class M2 Max with 32 GB
RAM:

- Start reliable, then optimize: first run ASR with `device: cpu` and
  `compute_type: int8`; then try faster settings only after the isolated smoke
  succeeds.
- Speaker embeddings are lightweight; keep `provider: cpu` and start with
  `num_threads: 2`.
- For VLM, begin with a smaller Qwen2-VL-compatible model before attempting a
  larger model. Use `device: cpu` for the first smoke. If you explicitly try
  Apple GPU acceleration, use `device: mps` with `device_map: null`; do not leave
  `device_map: auto` with an explicit device.
- Keep `video_fps: 1.0`, `video.sample_every: 1`, and
  `video.dedup_change_threshold: 0.0` for the first run; tune only after you can
  see captions and queue stats.
- Reserve disk for Hugging Face/PyTorch caches. 280 GB free is comfortable for
  experiments, but individual model families can still consume many GB.

## Twitch Credentials

Chat capture uses Twitch IRC in read-only mode and reads credentials from
environment variables:

```bash
read -r -p "TWITCH_BOT_USERNAME: " TWITCH_BOT_USERNAME; export TWITCH_BOT_USERNAME
read -r -s -p "TWITCH_OAUTH_TOKEN: " TWITCH_OAUTH_TOKEN; echo; export TWITCH_OAUTH_TOKEN
```

`TWITCH_OAUTH_TOKEN` may include or omit the `oauth:` prefix; the reader
normalizes it internally. Do not put these secrets in YAML files, examples,
shell history snippets intended for commits, or issue docs.

Audio-only and video-only smoke runs can be isolated with `--no-chat`, so they
do not require `TWITCH_BOT_USERNAME` or `TWITCH_OAUTH_TOKEN`.

## Smoke Commands

Chat-only, writing chat perceptions:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-chat
```

Audio-only, isolated from chat credentials:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-audio \
  --no-chat --audio \
  --audio-chunk-seconds 1.0 \
  --quality audio_only
```

Audio VAD diagnostic, isolated from chat credentials and without ASR:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-vad \
  --no-chat --vad-diagnostic \
  --quality audio_only
```

## Local ASR Smoke

Local ASR is optional and imports `faster-whisper` only when the backend is
used. For isolated transcription smoke, install the ASR extra. For the full
Twitch audio runtime, install the audio extra because speaker embeddings are
also required:

```bash
uv sync --extra asr
uv sync --extra audio
```

Recommended ASR config defaults:

```yaml
asr:
  model: large-v3-turbo
  device: auto
  compute_type: default
  language: null
  beam_size: 5
  condition_on_previous_text: false
```

If your installed faster-whisper release expects the model shorthand, use
`model: turbo`. For CPU-only smoke, `device: cpu` and `compute_type: int8` are
usually the safest first run.

Capture a short raw PCM sample first:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-asr \
  --no-chat --audio \
  --quality audio_only
```

Then transcribe one captured mono 16 kHz signed 16-bit PCM sample through
`minnarone.asr`:

```bash
uv run --extra asr python - <<'PY'
from pathlib import Path

from minnarone.asr import AsrConfig, FasterWhisperAsr
from minnarone.audio import SpeechSegment

pcm = Path(".smoke/twitch-asr/raw/audio/audio-0001.pcm").read_bytes()
asr = FasterWhisperAsr(
    AsrConfig(
        model="large-v3-turbo",
        device="auto",
        compute_type="default",
        condition_on_previous_text=False,
    )
)
text = asr.transcribe(
    SpeechSegment(samples=pcm, sample_rate=16_000, source_label="twitch", ts=0.0)
)
print({"source": "audio", "type": "speech", "speaker": "?", "text": text})
PY
```

Success means the printed `audio/speech` text is plausible for the captured
audio. Empty output means the ASR backend heard nothing intelligible and should
not write a perception. This isolated ASR smoke still prints speaker `?`
because it does not run speaker embeddings or clustering.

## Local Speaker Embedding Smoke

Speaker tagging is optional until `twitch.audio: true` is enabled, and imports
`sherpa-onnx` only when the embedding backend is constructed. Install the full
audio extra and place a local speaker embedding ONNX model on disk. Minnarone
does not download a model automatically.

```bash
uv sync --extra audio
```

Recommended speaker config defaults:

```yaml
speaker_embedding:
  model_path: /path/to/campp-speaker-embedding.onnx
  provider: cpu
  num_threads: 1
  dimension: 192

speaker_clustering:
  threshold: 0.6
  warmup_seconds: 60.0
  min_update_seconds: 1.0
```

Extract an embedding from the same captured mono 16 kHz signed 16-bit PCM sample:

```bash
uv run --extra audio python - <<'PY'
from pathlib import Path

from minnarone.audio import SpeechSegment
from minnarone.speaker import (
    SherpaOnnxSpeakerEmbeddingBackend,
    SpeakerEmbeddingConfig,
)

pcm = Path(".smoke/twitch-asr/raw/audio/audio-0001.pcm").read_bytes()
backend = SherpaOnnxSpeakerEmbeddingBackend(
    SpeakerEmbeddingConfig(
        model_path="/path/to/campp-speaker-embedding.onnx",
        provider="cpu",
        num_threads=1,
        dimension=192,
    )
)
embedding = backend.embed(
    SpeechSegment(samples=pcm, sample_rate=16_000, source_label="twitch", ts=0.0)
)
print({"dimension": len(embedding), "norm": sum(v * v for v in embedding) ** 0.5})
PY
```

Success means the printed dimension matches `speaker_embedding.dimension` and
the norm is close to 1. In the live audio path, embeddings are clustered online:
the dominant cluster after warmup is frozen as `streamer`, other stable clusters
emit `speaker_N`, and short or unreliable utterances may emit `?` without
updating centroids.

## Local Speaker Clustering Smoke

Use this synthetic smoke to isolate the online clustering thresholds without
ASR, sherpa-onnx, audio bytes, or Twitch. It feeds normalized vectors directly
into `OnlineSpeakerClusterer` so you can validate `streamer`, `speaker_N`, and
unknown short-utterance behavior before model-backed audio is enabled.

```bash
uv run python - <<'PY'
from minnarone.speaker import OnlineSpeakerClusterer, SpeakerClusteringConfig

clusterer = OnlineSpeakerClusterer(
    SpeakerClusteringConfig(
        threshold=0.6,
        warmup_seconds=2.0,
        min_update_seconds=1.0,
    )
)

samples = [
    ((1.0, 0.0), 0.5),   # too short -> ?
    ((1.0, 0.0), 1.2),   # first stable speaker
    ((0.99, 0.1), 1.1),  # same speaker
    ((0.0, 1.0), 1.0),   # second speaker
]

for embedding, duration in samples:
    print(clusterer.assign(embedding, duration_seconds=duration))

stats = clusterer.stats()
print(
    {
        "total": stats.total_utterances,
        "unknown": stats.unknown_utterances,
        "streamer_cluster_id": stats.streamer_cluster_id,
        "clusters": [
            (c.cluster_id, c.label, round(c.talk_time_seconds, 2), c.updates)
            for c in stats.clusters
        ],
    }
)
PY
```

Success means the first short utterance prints `?`, later utterances produce
stable `speaker_N` labels, and once `warmup_seconds` is reached the dominant
cluster label becomes `streamer`. If speakers split too much, raise
`threshold`; if speakers merge too much, lower it.

Video-only, isolated from chat credentials:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-video \
  --no-chat --video \
  --video-fps 1.0 \
  --quality best
```

Full adapter/capture smoke with chat, raw audio, and raw video enabled:

```bash
minnarone-twitch-smoke \
  --channel nomecanale \
  --duration 30 \
  --output ./.smoke/twitch-full \
  --audio --video \
  --audio-chunk-seconds 1.0 \
  --video-fps 1.0 \
  --quality best
```

The command exits non-zero if an enabled channel produces zero events or if
required configuration is invalid.

## Smoke Artifacts

The `--output` directory is created if missing. Each run truncates
`perceptions.jsonl`, overwrites `stats.json`, and clears prior `.pcm` / `.jpg`
sample files under `raw/audio` and `raw/video`; treat `stats.json` as the source
of truth for the latest run. The directory contains:

- `perceptions.jsonl`: chat messages normalized into the existing perception
  JSONL contract.
- `raw/audio/*.pcm`: capped raw PCM samples, mono 16 kHz signed 16-bit
  little-endian, useful only to prove FFmpeg produced audio bytes.
- `stats.json` VAD fields: with `--vad-diagnostic`, `vad_utterances` and
  `vad_utterance_durations_ms` report segmentation counts and durations. They
  do not include transcripts.
- `raw/video/*.jpg`: capped raw JPEG frames, useful only to prove FFmpeg
  produced image frames.
- `stats.json`: counts for chat/audio/video events, saved raw sample counts, and
  failures collected during capture/cleanup.

Raw audio and raw video artifacts are capture diagnostics. VAD diagnostic only
means segmentation ran on mono 16 kHz signed 16-bit PCM frames. It does not mean
ASR, diarization, VLM captioning, or main-agent Twitch integration is complete.

Quick checks:

```bash
wc -l ./.smoke/twitch-chat/perceptions.jsonl
ls -lh ./.smoke/twitch-audio/raw/audio
ls -lh ./.smoke/twitch-video/raw/video
python -m json.tool ./.smoke/twitch-full/stats.json
```

## PyAV Video Frame Runtime Validation

The `minnarone-twitch-smoke --video` command remains an FFmpeg JPEG diagnostic:
it saves capped `raw/video/*.jpg` files so capture can be inspected by eye. The
main Twitch video runtime uses Streamlink + PyAV instead and emits
`minnarone.video.VideoFrame` events with decoded frame pixels for local
perception.

`twitch.video: true` enables Twitch video events. The top-level `video:` block
configures perception after frames arrive: extra sampling before the captioner
and byte-based visual dedup sensitivity.

```yaml
video:
  sample_every: 1
  dedup_change_threshold: 0.0
```

Install the optional video runtime dependencies, then run a bounded frame check:

```bash
uv sync --extra video
uv run --extra video python - <<'PY'
import asyncio

from minnarone.twitch_video import TwitchPyAvVideoReader


async def main():
    reader = TwitchPyAvVideoReader(channel="nomecanale", quality="best", fps=1.0)
    seen = 0
    try:
        await reader.start()
        async for event in reader.events():
            seen += 1
            frame = event.payload
            print(
                {
                    "count": seen,
                    "channel": event.channel,
                    "payload": type(frame).__name__,
                    "pixels": type(frame.pixels).__name__,
                    "ts": frame.ts,
                }
            )
            if seen >= 3:
                break
    finally:
        await reader.stop()


asyncio.run(main())
PY
```

Success means a live channel prints a few `VideoFrame` payloads and exits
cleanly. This proves Streamlink + PyAV frame production only; it is not captioning.
It also does not validate deduplication or VLM output.

## Local Qwen2-VL Caption Smoke

The local video caption backend is optional and imports `transformers`, `torch`,
and Pillow only when `Qwen2VlCaptioner` is constructed. Automated tests use
fake captioners and never download a VLM. For a real local run, install both
video capture and VLM extras, then point `vlm.model` at an existing local model
directory or a Hugging Face model id you intentionally want `transformers` to
resolve.

```bash
uv sync --extra video --extra vlm
```

Recommended VLM config defaults:

```yaml
vlm:
  model: /path/to/qwen2-vl-model
  device: auto
  device_map: auto
  torch_dtype: auto
  attn_implementation: null
  max_new_tokens: 48
  timeout_seconds: 30.0
  language: en
  prompt: >-
    Describe the visible Twitch stream scene in one concise English sentence.
    Mention only observable gameplay, UI, people, and readable text.
    Do not speculate.
  max_caption_chars: 240
  max_image_edge: 768
  max_image_pixels: 500000
```

Caption one captured smoke JPEG through `minnarone.vlm`:

```bash
uv run --extra vlm python - <<'PY'
from PIL import Image

from minnarone.video import VideoFrame
from minnarone.vlm import Qwen2VlCaptioner, QwenVlConfig

image = Image.open(".smoke/twitch-video/raw/video/video-0001.jpg").convert("RGB")
captioner = Qwen2VlCaptioner(
    QwenVlConfig(
        model="/path/to/qwen2-vl-model",
        device="auto",
        device_map="auto",
        torch_dtype="auto",
        max_new_tokens=48,
        timeout_seconds=30.0,
    )
)
caption = captioner.caption(
    VideoFrame(pixels=image, source_label="twitch-smoke", ts=0.0)
)
print({"source": "video", "type": "caption", "text": caption})
PY
```

Success means the printed `video/caption` is a short English description of the
visible frame. If it times out or fails to load, the main runtime records that
VLM failure in the bounded perception queue diagnostics and continues handling
chat/audio instead of killing the whole agent.

## Console Runtime Config

The main CLI can run Twitch through the existing public console output. It reads
chat through Twitch IRC when `twitch.chat: true`, writes normal chat perceptions
to the store, and does not send chat messages back to Twitch.

```yaml
adapter: twitch
twitch:
  channel: nomecanale
  quality: best
  chat: true
  audio: false
  video: false
  audio_chunk_seconds: 1.0
  video_fps: 1.0

vad:
  mode: 2
  frame_ms: 30
  padding_ms: 300
  max_utterance_seconds: 30.0

asr:
  model: large-v3-turbo
  device: auto
  compute_type: default
  language: null
  beam_size: 5
  condition_on_previous_text: false

speaker_embedding:
  model_path: null
  provider: cpu
  num_threads: 1
  dimension: 192

speaker_clustering:
  threshold: 0.6
  warmup_seconds: 60.0
  min_update_seconds: 1.0

video:
  sample_every: 1
  dedup_change_threshold: 0.0

vlm:
  model: null
  device: auto
  device_map: auto
  torch_dtype: auto
  attn_implementation: null
  max_new_tokens: 48
  timeout_seconds: 30.0
  language: en
  prompt: >-
    Describe the visible Twitch stream scene in one concise English sentence.
    Mention only observable gameplay, UI, people, and readable text.
    Do not speculate.
  max_caption_chars: 240
  max_image_edge: 768
  max_image_pixels: 500000

commentator:
  enabled: false
  language: it
  idle_interval: null
```

For local audio perception, install the audio extra, set `twitch.audio: true`,
and point `speaker_embedding.model_path` at a local ONNX model. Chat can stay
enabled, or you can run audio-only with `chat: false` to avoid IRC credentials.
For local video captioning, install `--extra video --extra vlm`, set
`twitch.video: true`, and configure `vlm.model`; captions are concise English by
default and pass through the same bounded media queue as audio.

## Local Commentator Mode

Commentator mode keeps the public-chat persona available but adds an
operator-facing stance for private/local commentary. Use `mode: private` plus
`commentator.enabled: true`: output is routed to the local console as
`[PRIVATE]`. The TUI/dashboard remains a separate read-only observability tool;
this CLI path does not start it automatically. There is no Twitch send path and
no `PRIVMSG` write; no public chat write/send scope is required. If
`twitch.chat: true`, IRC credentials are still needed for read-only chat
ingestion.

```yaml
mode: private
adapter: twitch
twitch:
  channel: nomecanale
  quality: best
  chat: true
  audio: false
  video: false

commentator:
  enabled: true
  language: it
  idle_interval: 30.0
```

The prompt stance tells Minnarone to act as a local commentator, write concise
Italian comments for the operator, and use chat/audio/video perceptions as
context. `commentator.idle_interval` overrides the global `idle_interval` only
for this mode, so local commentary can be more proactive without changing the
default public-chat behavior.

See `examples/twitch-commentator.example.yaml` for a complete console-only
commentator config. The existing `examples/twitch.example.yaml` remains the
conservative public-console Twitch config with `commentator.enabled: false`.

### Original-Chat Dry-Run Seed Memory

Use `examples/twitch-original-chat.example.yaml` when you want the private
local dry-run to render what Minnarone would write as a Twitch chat user. The
example keeps `mode: private`, `commentator.enabled: true`, and
`commentator.style: original_chat`; it still has no public Twitch send path.

The example points at committed seed memory with paths relative to the config
file:

```yaml
soul_path: original-chat-memory/soul.md
facts_dir: original-chat-memory/facts
```

`soul` is Minnarone's identity, persona, and style: who he is, how he talks,
and what tone boundaries he should keep. The `facts` files hold stable facts
about channels or interlocutors, split by entity file under the facts directory.
In the repo, these resolve to `examples/original-chat-memory/soul.md` and
`examples/original-chat-memory/facts`, with files such as `facts/enkk.md`.
Both blocks are injected into the original-chat prompt's
`[MEMORIA PERMANENTE]` section.

Facts are manually authored for now. There is no auto-memory, fact extraction
from live streams, or cross-session update workflow in this local dry-run seed.

## Full Commentator Run Workflow

Run the full local commentator in layers. Do not start with every model enabled
until the isolated checks above pass.

1. Install system tools and Python extras:

   ```bash
   streamlink --version
   ffmpeg -version
   uv sync --extra audio --extra video --extra vlm --extra tui
   ```

2. Export only environment secrets; never put them in YAML:

   ```bash
   read -r -s -p "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo; export OPENROUTER_API_KEY
   read -r -p "TWITCH_BOT_USERNAME: " TWITCH_BOT_USERNAME; export TWITCH_BOT_USERNAME
   read -r -s -p "TWITCH_OAUTH_TOKEN: " TWITCH_OAUTH_TOKEN; echo; export TWITCH_OAUTH_TOKEN
   ```

3. Copy `examples/twitch-commentator.example.yaml` to a local config path, set
   `twitch.channel`, then enable channels gradually:

   ```yaml
   mode: private
   adapter: twitch
   twitch:
     channel: nomecanale
     chat: true
     audio: false
     video: false
   commentator:
     enabled: true
     language: it
     idle_interval: 30.0
   ```

4. Validate config without starting capture:

   ```bash
   uv run python -m minnarone path/to/twitch-commentator.local.yaml --check
   ```

5. Start the console commentator:

   ```bash
   uv run python -m minnarone path/to/twitch-commentator.local.yaml
   ```

Success signal for the first full run:

- Console output is prefixed with `[PRIVATE]`.
- `perceptions.jsonl` receives chat/audio/video perceptions as enabled.
- `Agent.observability_snapshot()` would show queue counters and failures if you
  attach the read-only TUI.
- No public Twitch messages are sent. Minnarone does not write `PRIVMSG` lines
  to Twitch in this runtime path, and public Twitch output remains out of scope.

## Live Observability TUI

The live dashboard is the operator view for the normal runtime. It uses the same
runtime wiring as the console command, plus TUI-specific run artifacts and local
dashboard output capture, runs the agent in the background, and renders a
read-only Textual TUI in the foreground. The TUI reads snapshots only; it does
not tick the agent, mutate queues, or send public Twitch messages.

Prerequisites:

- Install the runtime extras for the channels you enable. For the full local
  commentator path, use:

  ```bash
  uv sync --extra audio --extra video --extra vlm --extra tui
  ```

- Keep `OPENROUTER_API_KEY`, `TWITCH_BOT_USERNAME`, and `TWITCH_OAUTH_TOKEN` in
  the shell environment as shown above; do not put them in YAML or committed
  docs. Chat requires the Twitch credentials only for read-only IRC ingestion.
- If `twitch.audio: true` or `twitch.video: true`, verify `streamlink` and
  `ffmpeg` on `PATH`, and configure the local ASR, speaker, and VLM model paths
  before the live run.
- Use `mode: private` with `commentator.enabled: true` for local operator
  commentary. No public Twitch send path is enabled by this workflow.

Validate the config first:

```bash
uv run python -m minnarone path/to/twitch-commentator.local.yaml --check
```

Start the live TUI:

```bash
uv run python -m minnarone path/to/twitch-commentator.local.yaml --tui
```

The command creates a run directory under `.local/minnarone/runs/run-*` relative
to the config's `facts_dir` parent. The TUI is intentionally read-only: panels,
status labels, and the `PROMPT` tab are for operator inspection only. It has no
input for writing Twitch chat, and this runtime does not send public Twitch
messages.

Operational safety summary: the live TUI is read-only and does not send public Twitch messages.

Main dashboard panels:

- `IDLE`: recent idle-comment triggers, or `(nessun idle)` when no proactive
  idle comment was triggered.
- `FINESTRA CHAT`: open conversation windows for chat interlocutors other than
  the streamer. This is conversation-window state, not the raw chat log.
- `STREAMER`: the open conversation window for the diarized `streamer` speaker
  when the audio clustering path has identified one.
- `CHAT`: recent Twitch chat `msg` perceptions with timestamps.
- `EVENTI`: Senser triggers plus technical events such as local failures,
  queue drops/cancellations, adapter drops, and LLM errors.
- `MINNARONE`: recent local Minnarone output messages routed through the
  operator output stream.
- `TRASCRIZIONE`: recent ASR `audio/speech` transcriptions with speaker labels
  such as `streamer`, `speaker_N`, or `?`.
- `VIDEO`: video counters (`frames`, `sampled`, `captioned`, `failed`) followed
  by recent VLM captions.
- `MEMORIA`: the current short-term memory summary from the summarizer, or
  `(nessuna memoria)` before one exists.

The status bar shows source health labels for `chat`, `audio`, `video`, `asr`,
`speaker`, `vlm`, `llm`, `queue`, and `adapter` when those sources are known.
The source health labels are:

- `ok`: the source has produced usable output, such as chat messages,
  transcriptions, captions, clustered speakers, or a successful LLM prompt.
- `idle`: the source is present but has not produced higher-level output yet,
  for example raw audio/video events without transcriptions/captions.
- `busy`: model-backed local work is queued; ASR and VLM busy states come from
  non-zero queue depth.
- `failed`: an adapter, queue, ASR, speaker, VLM, or LLM failure was observed.
- `unknown`: no useful signal has been seen for that source yet.

The same line includes count and failure fields such as `counts chat=...`,
`audio=...`, `video=...`, `queue_depth=...`, queue `failed`, `dropped`,
`abandoned`, `cleanup`, `adapter_dropped`, and a compact `latest_failure` when
available.

The `PROMPT` tab, also referred to as the PROMPT tab in checklist notes, shows
the latest LLM prompt observation. It preserves the exact redacted prompt body,
including prompt order and newlines, and shows
`trigger`, `status`, `model`, token metadata (`prompt_tokens`,
`completion_tokens`, `total_tokens`), cache metadata (`cached_tokens`,
`cache_write_tokens`, `cache_read_tokens` when present), `cost`, and `error`
when present. Token, cache, and cost values are best effort: if the provider did
not return a field, the TUI shows `unknown`, such as `cost=unknown`.

Prompt capture redaction removes known unsafe values before display and before
writing debug files. OAuth tokens, OpenRouter-style keys, bearer authorization
values, secret-looking metadata keys, control characters, raw audio bytes, raw
frame/pixel/sample payloads, and long binary reprs are redacted. Redaction is
for operator safety, not a reason to commit debug artifacts.

## Replay TUI

Replay opens saved local artifacts in the same dashboard without starting
Twitch IRC, Streamlink, ASR, speaker embedding, VLM, or OpenRouter. It accepts a
run directory:

```bash
uv run python -m minnarone --replay .local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa
```

It also accepts a direct perception log path:

```bash
uv run python -m minnarone --replay .local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa/perceptions.jsonl
```

Replay reads `perceptions.jsonl`, optional prompt captures under
`debug/prompts`, and optional replay events from `debug/events.jsonl`. The
status bar says `mode=replay offline`, shows the source path, reconstructed
counts, prompt presence, and replay failures. It is safe to use without live
credentials or model files.

## Run And Prompt Retention

Live TUI runs are local, bounded, and gitignored. The default run root is
`.local/minnarone/runs/`; `.local/` is in `.gitignore`, and run artifacts are not
for commits or issue uploads. Each live run gets a directory named
`.local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa` with a Minnarone ownership
marker, `perceptions.jsonl`, and `debug/`.

These retention limits are the disk safety guardrails:

- Run retention keeps the latest 20 Minnarone-owned run directories, preserving
  active runs and pruning older completed runs. It only prunes directories that
  match Minnarone's run name and marker, so unrelated local folders are left
  alone.
- Prompt retention keeps the latest 50 `debug/prompts/prompt-*.json` captures
  in a run.
- Each prompt capture is capped at 200 KB. Oversized records are truncated with
  an explicit truncation marker.
- `debug/events.jsonl` stores replayable trigger and Minnarone output events,
  with unsafe text redacted.
- If disk space is tight, delete old `.local/minnarone/runs/run-*` directories
  after you finish replay/acceptance; do not copy raw prompt or run artifacts
  into public tickets.

## Manual Live Acceptance Checklist

Use this checklist on a real live channel after the isolated smoke checks pass.
It does not require or expect public Twitch output.

- [ ] Start with a local config using `mode: private`,
  `commentator.enabled: true`, and only the channels you intend to validate.
- [ ] Run `uv run python -m minnarone path/to/twitch-commentator.local.yaml
  --check`; it exits successfully without starting capture.
- [ ] Run `uv run python -m minnarone path/to/twitch-commentator.local.yaml
  --tui`; the Textual app opens and the status bar updates from the live
  snapshot.
- [ ] Confirm the dashboard contains `IDLE`, `FINESTRA CHAT`, `STREAMER`,
  `CHAT`, `EVENTI`, `MINNARONE`, `TRASCRIZIONE`, `VIDEO`, and `MEMORIA`.
- [ ] With chat enabled, `CHAT` shows recent chat perceptions and
  `FINESTRA CHAT` shows conversation windows only when the Senser opens them.
- [ ] With audio enabled, `TRASCRIZIONE` shows speaker-labelled ASR output, and
  source health moves through `busy`, `idle`, `ok`, or `failed` according to
  queue/model state.
- [ ] With video enabled, `VIDEO` shows frame/caption counters and recent
  captions, and VLM failures appear as source health or `EVENTI` diagnostics
  instead of killing the whole run.
- [ ] `MINNARONE` shows local operator-facing comments only; no public Twitch
  chat message is sent.
- [ ] Open the `PROMPT` tab after an LLM call; it shows the exact redacted
  prompt, status/model, best-effort token/cache/cost metadata, and no raw
  secrets.
- [ ] Stop the TUI cleanly, then confirm a bounded run directory exists under
  `.local/minnarone/runs/run-*` with `perceptions.jsonl`, optional
  `debug/prompts`, and optional `debug/events.jsonl`.
- [ ] Replay the saved run with `uv run python -m minnarone --replay
  .local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa` and verify the offline
  dashboard labels the session as replay mode.

## Local Perception Observability

`Agent.observability_snapshot()` and the dashboard text model expose a read-only
debug view for local Twitch perception. It includes recent chat/audio/video
perceptions, audio transcriptions with speaker labels, recent video captions
with timestamps, bounded media queue counters, stage-categorized local failures,
and speaker cluster diagnostics with talk time and frozen streamer cluster id.

The snapshot is intentionally safe for operator display: it never dumps raw
audio bytes (`raw audio bytes`), raw frame payloads, speaker embedding
centroids, Twitch OAuth tokens, or OpenRouter keys. Failure messages are
compacted before rendering.

Useful sections in `DashboardState.render_text()`:

- `Audio`: recent `audio/speech` lines as `speaker: transcript`.
- `Speaker`: utterance totals, unknown count, streamer cluster id, cluster talk
  time, and update counts.
- `Video`: recent `video/caption` timestamps and text.
- `Queue`: queued, processed, dropped, failed, cancelled, and depth counters per
  model-backed channel.
- `Failure locali`: categorized stages such as `vad`, `asr`, `embedding`,
  `clustering`, `pyav`, `dedup`, `vlm`, `capture`, and `output` where practical.

```yaml
adapter: twitch
twitch:
  channel: nomecanale
  quality: audio_only
  chat: false
  audio: true
  video: false
  audio_chunk_seconds: 1.0
  video_fps: 1.0

asr:
  model: large-v3-turbo
  device: auto
  compute_type: default
  language: null
  beam_size: 5
  condition_on_previous_text: false

speaker_embedding:
  model_path: /path/to/campp-speaker-embedding.onnx
  provider: cpu
  num_threads: 1
  dimension: 192

speaker_clustering:
  threshold: 0.6
  warmup_seconds: 60.0
  min_update_seconds: 1.0
```

See `examples/twitch.example.yaml` for a complete file that still includes the
normal app fields (`mode`, `soul_path`, `facts_dir`, `llm_provider`, cadence
settings, bounded local perception queue settings, and v2 inert settings). Live
runtime responses require `OPENROUTER_API_KEY` because the normal agent loop
calls the configured LLM.

Existing `adapter: os_capture` configs do not require a `twitch:` section.

## Troubleshooting

- Missing `streamlink`: run `streamlink --version`; install it if the command is
  not found. Audio/video capture cannot start without it.
- Missing `ffmpeg`: run `ffmpeg -version`; install it if the command is not
  found. Raw PCM and JPEG artifacts cannot be produced without it.
- Bad credentials: verify `TWITCH_BOT_USERNAME` and `TWITCH_OAUTH_TOKEN` are set
  in the same shell that runs the smoke. Regenerate the token if IRC rejects the
  login. Do not add these values to config files.
- Offline channel: open `https://www.twitch.tv/<channel>` in a browser or run
  `streamlink https://www.twitch.tv/<channel> best --stream-url`. If the channel
  is offline, media streams may produce no bytes.
- zero eventi: inspect `stats.json` first. If only chat is zero, confirm the
  channel has live chat activity and credentials are valid. If audio/video are
  zero, check Streamlink/FFmpeg versions and try `--quality best`.
- Empty `raw/audio` or `raw/video`: increase `--duration`, verify the channel is
  live, and lower capture cost with `--quality audio_only` for audio or
  `--video-fps 1.0` for video.
- `OPENROUTER_API_KEY` errors are unrelated to capture-only smoke. The smoke
  command should not require that key.
- Missing ASR model or first-run download failure: run the isolated `Local ASR
  Smoke` command before the full runtime. Try `device: cpu`,
  `compute_type: int8`, and confirm the model name (`large-v3-turbo` or
  `turbo`) matches your installed faster-whisper/CTranslate2 setup.
- Empty ASR output: confirm the `.pcm` file is non-empty, run
  `--vad-diagnostic`, and check that `vad_utterances` is greater than zero. If
  VAD is too strict, lower `vad.mode`; if noise leaks through, raise it.
- Speaker over-segmentation: if one person becomes many `speaker_N` labels,
  raise `speaker_clustering.threshold` toward `0.65` or `0.7`, and require
  longer speech before trusting updates with `min_update_seconds`.
- Speaker under-segmentation: if different people collapse into one label, lower
  `speaker_clustering.threshold` toward `0.5` or `0.55`, then re-check cluster
  talk time in observability.
- Speaker model path errors: verify `speaker_embedding.model_path` points to a
  real ONNX file and that `speaker_embedding.dimension` matches the model.
- No PyAV frames: run the PyAV frame validation command, then try lower
  `twitch.video_fps`, `quality: best`, and a live channel. Capture-only JPEG
  smoke success does not prove PyAV decode success.
- Repeated or stale video captions: inspect `Video` diagnostics for
  `dedup_skipped`, lower `video_fps`, raise `video.sample_every`, or increase
  `video.dedup_change_threshold` to ignore small frame noise.
- VLM setup failure: run `uv run --extra vlm python -c "import transformers,
  torch; from PIL import Image"` first, then run the Qwen2-VL caption smoke with
  a single captured JPEG. Configure `vlm.model`; `null` is accepted for config
  parsing but cannot caption real frames.
- VLM timeout or memory pressure: start with a smaller model, reduce
  `vlm.max_new_tokens`, increase `vlm.timeout_seconds`, keep `video_fps: 1.0`,
  and watch queue `failed`, `dropped`, and `abandoned` counters.
- Public Twitch output: this local runtime intentionally does not send public
  Twitch messages. If you see a `PRIVMSG` write in a custom harness, that path is
  outside this operator workflow.
