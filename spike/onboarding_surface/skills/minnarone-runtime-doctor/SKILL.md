---
name: minnarone-runtime-doctor
description: Diagnose a Minnarone runtime profile before shadow. Use to check extras, tools, pinned models, config, lazy model probes and Twitch safety gates without downloading weights or starting live.
---

# Minnarone runtime doctor prototype

Read the profile matrix and pinned manifest before checking a machine. Be
read-only by default: do not install tools, download/delete weights, start a
stream or contact Twitch without a separate explicit request.

## Checks

1. Select P0, P2, or one full profile P3-P5; do not assume “all extras”.
2. Report PASS/FAIL/SKIP for Python, `uv`, profile extras, Streamlink, FFmpeg,
   free disk, model paths, byte sizes, revision and SHA-256.
3. For Italian audio require CAM++ English VoxCeleb `dimension: 512`; reject a
   zh-cn 192 model/config mismatch. Treat threshold 0.5 as a starting point.
4. Make lazy boundaries explicit: `--check` does not prove a Qwen load, usable
   CUDA/MPS memory, or the first caption.
5. Verify dedicated bot account, broadcaster-consent status, disclosure choice,
   retained artifacts/manual deletion and `send.mode: shadow`.
6. Propose isolated smoke commands, then `minnarone <config> --check` and a
   bounded shadow run. Never press `p` or promote live.

The disposable `../../doctor.py` and `../../manifest.json` exercise the
contract; canonical profiles live in
`../../../../docs/research/runtime-model-profiles.md`. Production should keep
docs canonical and let the skill orchestrate checks; a core `minnarone doctor`
command remains deferred.
