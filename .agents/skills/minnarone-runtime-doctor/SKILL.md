---
name: minnarone-runtime-doctor
description: Perform a read-only Minnarone runtime readiness check for profiles P0-P5, including tools, configuration, pinned model artifacts, digests, and safety gates. Use when asked to diagnose setup readiness or verify a Twitch shadow profile; do not use to download models, mutate config, or enable live sending.
---

# Minnarone Runtime Doctor

Return a deterministic `PASS`, `FAIL`, or `SKIP` report. Do not modify files,
install dependencies, download weights, start a long-running capture, or call
Twitch live-send APIs.

## 1. Select one profile

Infer the smallest requested profile and state it before checking:

- `P0 chat-only`: core install and Twitch chat in shadow;
- `P1 capture smoke`: Streamlink/FFmpeg and bounded raw chat/audio/video smoke;
- `P2 CPU-light audio`: P1 plus local ASR and English VoxCeleb CAM++;
- `P3 Apple Silicon full`: audio/video/VLM/TUI, Qwen2-VL on MPS;
- `P4 CUDA full`: audio/video/VLM/TUI, Qwen2-VL on CUDA;
- `P5 llama.cpp full/local`: local GGUF/mmproj and multimodal server.

If intent is ambiguous, default to P0 and mark higher-profile checks `SKIP`.
Use `docs/research/runtime-model-profiles.md` for profile budgets and
`docs/runtime-model-manifest.json` for artifact pins and SHA-256 digests.

## 2. Run read-only checks

Check in this order and record the exact command or evidence for each result:

1. Repository and Python: supported Python, `uv.lock`, importability, and the
   selected optional extras.
2. External tools: only those required by the profile, such as Streamlink,
   FFmpeg, or `llama-server`; record versions.
3. Configuration: load the requested YAML, confirm requested channels and
   shadow/off send mode, and run `uv run python -m minnarone <config> --check`.
   Explain that `--check` is local/lazy and does not prove live capture or a
   first VLM inference.
4. Models: treat weights alone as insufficient. Resolve the bundle's pinned
   source owner and revision, then verify all required bundle files. Each file
   must have an authenticated integrity entry: either direct byte size and
   SHA-256 or an artifact reference that resolves to the same filename, owner,
   revision, byte size, and SHA-256. Missing provenance, an unresolved reference,
   or any mismatch must be `FAIL`. Then run the bundle's read-only, offline
   local loader smoke and record its evidence. Primary-weight digest success
   without authenticated bundle completeness and a profile-specific loader
   smoke must be `FAIL`; never fetch replacements.
5. Speaker contract for Italian/non-Mandarin audio: English VoxCeleb CAM++,
   dimension `512`, threshold `0.5`. Treat the old `zh-cn` 192-dimension model
   as incompatible with the public profile.
6. Capacity: report CPU, RAM, disk, and GPU/VRAM evidence against the selected
   profile as measured facts or `SKIP`, never as invented certainty.
7. Public safety: config remains shadow/off; secrets stay in environment; live
   would require a dedicated bot account, broadcaster consent, token
   validation, disclosure choice, attended operation, and immediate stop.

Do not print secret values. It is safe to report only whether expected variable
names are set. Do not access the network merely to establish readiness.

## 3. Classify results

- `PASS`: directly verified and matches the selected profile.
- `FAIL`: required and absent, invalid, incompatible, or unsafe.
- `SKIP`: outside the selected profile or cannot be verified read-only.

Never convert unknowns into `PASS`. A failed higher-profile check does not make
P0 fail when P0 is the selected profile.

## 4. Report

Use this compact structure:

```text
Profile: Pn — name
Overall: PASS|FAIL

[PASS|FAIL|SKIP] check — evidence

Next actions:
1. smallest actionable remediation

Not performed: downloads, writes, live sends
```

Make the overall result `FAIL` when any selected-profile requirement fails;
otherwise `PASS`. Keep skipped optional checks visible.
