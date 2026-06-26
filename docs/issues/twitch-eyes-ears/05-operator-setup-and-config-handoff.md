## Parent PRD

[twitch-eyes-ears.md](../../prds/twitch-eyes-ears.md)

## What to build

Finish the operator-facing handoff for Twitch eyes and ears: document system
prerequisites, environment variables, smoke commands, expected artifacts,
troubleshooting guidance and the future `adapter: twitch` configuration shape.
Add validation scaffolding for Twitch-specific config without forcing full main
CLI integration yet.

This slice makes the feature usable by an operator and prepares the next PRD or
issue set for wiring the adapter into the reference app.

## Step-by-step implementation plan

1. Document system prerequisites.
   - What to change: explain that Streamlink and FFmpeg must be installed and available on `PATH`.
   - Why now: all capture paths depend on external tools.
   - Affects: operator setup workflow.
   - Verify: docs include concrete install/check commands appropriate for local development.
   - Pitfalls: do not imply these tools are Python package dependencies installed by the project.

2. Document Twitch credentials.
   - What to change: explain `TWITCH_BOT_USERNAME` and `TWITCH_OAUTH_TOKEN`, including accepted token prefix behavior.
   - Why now: chat smoke requires credentials, and future write capability can reuse them.
   - Affects: operator setup workflow and security expectations.
   - Verify: docs make clear that secrets belong in environment variables.
   - Pitfalls: do not include real tokens or encourage committing secrets.

3. Document smoke commands.
   - What to change: provide chat-only, audio-enabled, video-enabled and full adapter smoke examples.
   - Why now: the operator needs narrow commands to isolate failures by channel.
   - Affects: manual verification workflow.
   - Verify: docs show duration, output directory and channel toggles.
   - Pitfalls: do not include `OPENROUTER_API_KEY`; capture smoke is LLM-free.

4. Document smoke artifacts.
   - What to change: describe the expected perception JSONL, raw audio samples, raw video frames and stats file.
   - Why now: operators need to know what success looks like.
   - Affects: debugging and manual QA.
   - Verify: docs explain how to inspect counts and sample files.
   - Pitfalls: do not claim raw audio/video samples mean ASR/VLM are implemented.

5. Add Twitch config validation scaffolding.
   - What to change: introduce or prepare a Twitch-specific config shape that validates channel, quality, enabled flags, audio chunk duration and video FPS.
   - Why now: the main app will later need durable config; this issue should prepare that without forcing full runtime integration.
   - Affects: config schema and examples.
   - Verify: existing non-Twitch configs remain valid; valid Twitch configs parse; invalid Twitch values fail clearly.
   - Pitfalls: do not require Twitch fields for `os_capture` configs.

6. Add or update an example Twitch config.
   - What to change: include a sample config that uses `adapter: twitch` and the future-facing `twitch:` section from the PRD.
   - Why now: examples prevent operators from guessing field names.
   - Affects: example configuration and docs.
   - Verify: the example is syntactically valid and clearly marks credentials as environment variables.
   - Pitfalls: do not make the example imply full `python -m minnarone` integration is complete if it remains out of scope.

7. Add troubleshooting guidance.
   - What to change: document common failures: missing Streamlink, missing FFmpeg, invalid OAuth token, offline channel, zero events, empty audio/video artifacts.
   - Why now: live capture has many environmental failure modes.
   - Affects: operator guide.
   - Verify: each failure points to a concrete check.
   - Pitfalls: avoid vague advice; tell the operator what to inspect.

8. Preserve automated quality.
   - What to change: add config/doc tests where useful and keep existing test and quality gates passing.
   - Why now: documentation and config shape are part of the product surface.
   - Affects: test suite and quality workflow.
   - Verify: automated tests do not require live Twitch, credentials or external tools.
   - Pitfalls: do not turn manual smoke into CI.

## Acceptance criteria

- [ ] Operator docs mention Streamlink and FFmpeg as system prerequisites.
- [ ] Operator docs mention `TWITCH_BOT_USERNAME` and `TWITCH_OAUTH_TOKEN` as environment variables.
- [ ] Docs include smoke command examples for isolated and full capture paths.
- [ ] Docs describe `perceptions.jsonl`, raw audio, raw video and stats artifacts.
- [ ] Twitch config shape is documented and prepared for future CLI integration.
- [ ] Existing `os_capture` config examples remain valid.
- [ ] Troubleshooting covers missing tools, bad credentials, offline channels and zero-event runs.
- [ ] Automated checks do not require live Twitch or external tools.
- [ ] Existing tests and quality checks pass.

## Blocked by

- Blocked by [04-unified-twitchstreamadapter-resilience.md](./04-unified-twitchstreamadapter-resilience.md)

## User stories addressed

- User story 15
- User story 16
- User story 17
- User story 26
- User story 28
- User story 33
