---
ticket_schema: 1
ticket_id: "04"
execution_mode: AFK
blocked_by:
  - "03"
---

# Implement the bounded AI-disclosure and repository-link policy

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Implement the design selected by ticket 03 so qualifying interactions can
produce a truthful, contextual AI disclosure and a frequency-capped Minnarone
repository link. Preserve all existing prompt, routing, authorization, budget,
shadow, and live-send boundaries.

Cover the feature spec's Target Behavior, Interaction Contract, External
Contracts and Safety, Failure Modes, and Verification Strategy.

## Acceptance Criteria

- [ ] Approved qualifying interactions can produce the approved disclosure and
      repository URL while answering the user's actual question.
- [ ] Generic mentions and unrelated conversation cannot trigger repository
      promotion.
- [ ] Per-session and per-conversation caps and dedup match ticket 02 exactly,
      including reset boundaries.
- [ ] Perceived prompt-injection content cannot change the trigger, URL, caps,
      authorization, or routing decision.
- [ ] `announce_ai: false` remains truthful without proactive disclosure;
      approved canary configuration is explicit and tested.
- [ ] No path bypasses `TwitchPublicOutputRouter`, the allow-list, public-send
      budget, shadow state, manual promotion, or kill-switch.
- [ ] Unit, integration, fake-sender system tests, configuration docs, and the
      operator guide cover the behavior.
- [ ] Any prompt override work follows the repository's
      `minnarone-prompts` validation workflow and preserves the disclosure
      safety floor.

## Frontier

Dependency-blocked on the prototype decision in ticket 03. AFK implementation
ends at a validated candidate and does not authorize a live run.

## Step-by-Step Implementation Plan

1. Locate the narrow production owner selected by ticket 03 and write the
   approved behavior as failing tests.
2. Implement qualifying-interaction classification and cap/dedup state without
   coupling perception, prompt construction, output routing, and safety gates.
3. Compose the approved disclosure/link content with normal response,
   human-likeness, and conversation-window behavior.
4. Add observability that records decision reasons without copying credentials
   or unnecessary chat content.
5. Update configuration and operator documentation, then run the full project
   quality checks.

## Testing Plan

Use red-green-refactor for the narrow contract. Run targeted prompt/policy,
router, app, configuration, TUI, and operator-doc tests; then run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The system boundary uses fake Twitch streams/senders only.

## Out of Scope

- Contacting or selecting a broadcaster.
- Real Twitch credentials or live sends.
- Changing general public-send rates, weakening safety gates, or adding
  unattended/multi-channel operation.
