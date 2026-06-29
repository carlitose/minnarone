## Parent PRD

[original-live-observability-tui.md](../../prds/original-live-observability-tui.md)

## What to build

Capture the exact prompt and useful LLM metadata for each OpenRouter call, then
save bounded, redacted prompt debug records in the current run directory. The
saved prompt must preserve the real prompt structure sent to the provider, with
only secret and unsafe payload redaction. Keep the latest 50 prompt captures and
cap each saved prompt at 200 KB.

This slice provides the data contract used later by the `PROMPT` tab and replay
mode. It should be implemented at the LLM boundary rather than by reconstructing
prompts from UI state.

## Step-by-step implementation plan

1. Add an LLM-call observation record.
   - What to change: define a small record that can hold the exact prompt,
     trigger/context label when available, model name, timestamps, status,
     response metadata, token/cache fields, cost if available, and sanitized
     error text.
   - Why this comes first: prompt capture needs one stable shape before it is
     stored or rendered.
   - Affects: LLM provider boundary and dashboard state.
   - Verify: pure tests can construct successful and failed call records without
     network.
   - Pitfalls: do not store API keys, bearer tokens, OAuth tokens, raw audio,
     raw frames, or other payloads that are not prompt/debug text.

2. Capture prompts at the provider boundary.
   - What to change: observe the prompt after it is built and before the request
     is sent to OpenRouter, and attach provider metadata after the response or
     failure.
   - Why this comes now: capturing at the boundary avoids duplicate prompt
     generation and keeps the debug output faithful.
   - Affects: LLM provider calls and reactor/summarizer call sites.
   - Verify: fake LLM calls produce one observation with the same prompt text
     the fake transport received.
   - Pitfalls: do not reformat, summarize, or sort prompt sections before
     recording them.

3. Implement secret and unsafe-payload redaction.
   - What to change: apply targeted redaction to prompt/debug display and saved
     records for bearer tokens, Twitch OAuth tokens, OpenRouter keys, obvious
     secrets, control characters, and raw binary-looking data.
   - Why this comes before disk writes: unsafe prompt capture should never hit
     persistent storage.
   - Affects: sanitization utilities, prompt observer, prompt recorder.
   - Verify: tests inject fake secrets and confirm no literal secret appears in
     rendered or saved prompt records.
   - Pitfalls: avoid broad redaction that makes normal chat text or prompt
     instructions unreadable.

4. Write prompt debug records into the current run.
   - What to change: persist each prompt observation under the current run's
     prompt/debug area using deterministic, chronological filenames or metadata.
   - Why this comes now: the run-session manager provides the bounded local
     location.
   - Affects: prompt recorder and run artifact workflow.
   - Verify: tests create a run session, record prompts, and inspect saved
     redacted content.
   - Pitfalls: do not write debug files outside the local run area.

5. Enforce prompt retention and size caps.
   - What to change: keep only the latest 50 prompt captures and truncate each
     saved prompt record at 200 KB with an explicit truncation marker.
   - Why this comes now: prompt debugging must not fill the Mac during long
     experiments.
   - Affects: prompt recorder cleanup and file serialization.
   - Verify: tests write more than 50 records and an oversized prompt; old
     records are deleted and oversized content is capped.
   - Pitfalls: truncation should happen after redaction or preserve redaction
     guarantees either way.

6. Expose latest prompt metadata to the dashboard snapshot.
   - What to change: make the newest prompt observation available in the pure
     dashboard state for later TUI rendering.
   - Why this comes last: rendering should consume the same recorded state that
     persistence uses.
   - Affects: snapshot aggregation and dashboard state.
   - Verify: pure dashboard tests with fake prompt observations populate the
     latest prompt and LLM metadata fields.
   - Pitfalls: do not require a prompt to exist before the first LLM call.

## Acceptance criteria

- [ ] Each fake LLM call can produce an observation containing the exact prompt sent.
- [ ] Prompt observations include model, status, timestamps, token/cache metadata when present, cost when available, and sanitized errors.
- [ ] Secrets and unsafe payloads are redacted before display or persistence.
- [ ] Prompt debug records are saved inside the current run directory.
- [ ] Only the latest 50 prompt captures are retained.
- [ ] Saved prompt records are capped at 200 KB with a clear truncation marker.
- [ ] The latest prompt observation is available through the pure dashboard state.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)
- Blocked by [02-bounded-run-artifacts.md](./02-bounded-run-artifacts.md)

## User stories addressed

- User story 16
- User story 17
- User story 18
- User story 19
- User story 20
- User story 34
- User story 39
- User story 44
