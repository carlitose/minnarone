## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The configuration surface for public Twitch sending: a `twitch.send` block
with `mode` (`off` | `shadow` | `live`, default `off`), `allowed_channels`
(list of channel names, default empty), `max_per_minute`, `max_per_hour`, and
`failure_threshold` (consecutive send failures before auto-degrade). Parsing,
defaults, validation, and `--check` behavior land here — before any policy or
network code exists — so every later slice builds on a validated contract.

`--check` (and startup) must fail with a clear config error when `mode: live`
is configured and either the configured `twitch.channel` is not in
`allowed_channels`, or the write-scope token environment variable (a NEW
variable, distinct from the read token — see the PRD's "Separate write
credential" decision) is missing. `off` and `shadow` must not require the
write token.

## Step-by-step implementation plan

1. Define the send config type.
   - What: a frozen config dataclass for the `twitch.send` block with the five
     fields above, following the validation style of the existing config types
     (explicit error messages, type/range checks: caps > 0, threshold >= 1,
     mode in the three-value set, channels as non-empty lowercase strings).
   - Why now: the type is the contract every other slice imports.
   - Affects: config module and its unit tests.
   - Verify: unit tests for defaults, each invalid field, and unknown mode.
   - Pitfall: normalize channel names case-insensitively (Twitch channels are
     case-insensitive); store them lowercased.

2. Integrate the block into the main `Config` parse path.
   - What: `twitch.send` is optional in YAML; absent means all defaults
     (`off`). Wire it into the existing twitch config parsing.
   - Why now: config must parse before validation semantics are added.
   - Affects: config module, example configs (which should NOT gain the block
     yet, proving the default path).
   - Verify: existing config tests still pass; new tests parse a full block
     and an absent block.
   - Pitfall: keep the block under `twitch`, not top-level — sending is
     Twitch-transport-specific.

3. Add cross-field validation and the `--check` gate.
   - What: validation that runs at config load: `live` requires
     `twitch.channel` ∈ `allowed_channels` and the write-token env var to be
     set (name the variable here; document it in the error message). Errors
     use the established Italian config-error style.
   - Why now: fail-fast misconfiguration is the first safety layer of the PRD.
   - Affects: config validation, the `--check` CLI flow.
   - Verify: `--check` passes on all existing example configs; unit tests
     cover live-without-whitelist, live-without-token, and shadow-without
     token (must pass).
   - Pitfall: read the env var presence only — never its value into any error
     message, log, or artifact.

## Acceptance criteria

- [ ] `twitch.send` parses with defaults (`off`, empty allow-list) when absent.
- [ ] Every field is validated with a clear error on invalid input.
- [ ] `mode: live` fails config validation when the channel is not allow-listed.
- [ ] `mode: live` fails config validation when the write-token env var is missing.
- [ ] `off` and `shadow` never require the write token.
- [ ] `--check` on all existing example configs still passes unchanged.
- [ ] No secret value ever appears in errors, logs, or artifacts.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 3
- User story 4
- User story 19
- User story 20
- User story 33
