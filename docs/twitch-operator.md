# Twitch Operator Handoff

This guide covers the capture-only Twitch smoke workflow and the future
`adapter: twitch` config shape. The smoke command is deliberately separate from
`python -m minnarone`: it does not call an LLM, does not need
`OPENROUTER_API_KEY`, and does not send chat messages.

## System Prerequisites

Install `streamlink` and `ffmpeg` as system tools, not Python package
dependencies. They must be available on `PATH`.

```bash
# macOS
brew install streamlink ffmpeg

# Debian/Ubuntu
sudo apt-get install streamlink ffmpeg

# Checks
streamlink --version
ffmpeg -version
```

Chat-only smoke does not use Streamlink or FFmpeg, but audio and video capture
do.

## Twitch Credentials

Chat capture uses Twitch IRC in read-only mode and reads credentials from
environment variables:

```bash
export TWITCH_BOT_USERNAME=nome_bot
export TWITCH_OAUTH_TOKEN=oauth:token_o_senza_prefisso
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
- `raw/video/*.jpg`: capped raw JPEG frames, useful only to prove FFmpeg
  produced image frames.
- `stats.json`: counts for chat/audio/video events, saved raw sample counts, and
  failures collected during capture/cleanup.

Raw audio and raw video artifacts are capture diagnostics. They do not mean ASR,
VAD, diarization, VLM captioning, or main-agent Twitch integration is complete.

Quick checks:

```bash
wc -l ./.smoke/twitch-chat/perceptions.jsonl
ls -lh ./.smoke/twitch-audio/raw/audio
ls -lh ./.smoke/twitch-video/raw/video
python -m json.tool ./.smoke/twitch-full/stats.json
```

## Future Config Shape

The validated YAML shape for the future main CLI integration is:

```yaml
adapter: twitch
twitch:
  channel: nomecanale
  quality: best
  chat: true
  audio: true
  video: true
  audio_chunk_seconds: 1.0
  video_fps: 1.0
```

See `examples/twitch.example.yaml` for a complete file that still includes the
normal app fields (`mode`, `soul_path`, `facts_dir`, `llm_provider`, cadence
settings, and v2 inert settings). The config parser validates this shape now,
but `python -m minnarone config.yaml` does not yet wire `adapter: twitch` into
the running reference app. Use `minnarone-twitch-smoke` for live capture
verification until that integration lands.

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
