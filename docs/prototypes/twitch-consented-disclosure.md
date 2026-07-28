# Bounded Twitch disclosure and repository-link prototype

## Question

Which boundary—prompt-only, deterministic, or hybrid—can enforce the approved
qualifying trigger, exact disclosure, repository-link caps, and proactive
cadence while preserving a natural answer to the viewer?

- Branch: **logic**
- Assumption: the first canary is English and uses the exact contract in
  [twitch-consented-discovery.md](../specs/twitch-consented-discovery.md).
- Useful result: one approach must prevent false-positive promotion,
  false-negative first disclosure, repeated links, and proactive messages less
  than ten minutes apart; it must also preserve the contextual answer and
  compose correctly with a public-send budget drop.
- Scope: synthetic, secret-free, non-networked prototype only.

## Runtime Baseline

- `PromptBuilder` currently permits truthful AI disclosure through
  `disclosure.announce_ai`, but it does not own a repository URL, semantic
  promotion trigger, or numeric cap.
- `Senser` opens a per-interlocutor conversation window for a mention or
  continuation, but its structured trigger kinds do not distinguish identity,
  source, generic mention, invitation, or prompt injection.
- The public original-chat path normalizes the LLM's `MSG:` and routes it
  directly. Its existing `HumanLikeness` near-text dedup is not applied on that
  path and, even in isolation, does not treat two different sentences
  containing the same URL as duplicates.
- `PublicSendPolicy` correctly owns shadow/live, manual promotion, allow-list,
  kill-switch, minute/hour budgets, and failure degradation. It does not
  inspect message semantics or own session/conversation promotion state.

Therefore a prompt instruction or the existing general-purpose dedup/budget
cannot enforce the approved one-link contract.

## Prototype

The disposable logic model lives under
[`spike/twitch_disclosure_policy/`](../../spike/twitch_disclosure_policy/README.md).
It compares:

1. **Prompt-only:** the model classifies, renders, and remembers the policy.
2. **Deterministic:** code classifies, gates, caps, and replaces a qualifying
   answer with the exact approved copy.
3. **Hybrid:** the model supplies the contextual answer; deterministic code
   classifies eligibility, owns the exact promotional copy, session/window
   caps, and proactive cadence, then composes the two.

The corpus covers identity and source questions, a generic mention, ordinary
conversation, a moderator invitation, a prompt-injection attempt, repetition
in the same and different conversation windows, session reset, proactive
cadence, and a qualifying candidate dropped by the existing minute budget.

Every candidate crosses Minnarone's real `PublicSendPolicy` in `shadow` mode.
No sender, credential, socket, or Twitch connection exists in the prototype.

Run:

```bash
uv run python spike/twitch_disclosure_policy/prototype.py
uv run pytest spike/twitch_disclosure_policy/test_prototype.py -q
```

## Results

| Measure | Prompt-only | Deterministic | Hybrid |
| --- | ---: | ---: | ---: |
| False-positive promotions | 3 | 0 | 0 |
| False-negative first disclosures | 1 | 0 | 0 |
| Repeated session links | 6 | 0 | 0 |
| Repeated same-conversation links | 2 | 0 | 0 |
| Proactive cadence violations | 1 | 0 | 0 |
| Natural contextual answers | 1/1 | 0/1 | 1/1 |
| Existing minute-budget drops | 1 | 1 | 1 |
| Network sends | 0 | 0 | 0 |

Eight focused tests passed. The budget composition case proves that a definite
`drop` must not consume the promotion cap: the next eligible attempt after the
minute window may still include the link. Conversely, a `shadow` decision or a
live send attempt consumes the cap; a later sender failure must not create an
automatic promotional retry.

## Decision

Select the **hybrid boundary** for ticket 04.

The model remains responsible for a short contextual answer. A narrow,
opt-in deterministic policy owns:

- conservative English interaction classification for identity/source
  questions and broadcaster/moderator invitations;
- rejection of generic mentions, ordinary conversation, proactive promotion,
  and perceived instructions that attempt to force a link;
- rejection of an unexpected model-generated repository URL and insertion of
  the exact approved disclosure and URL only through policy;
- one promotional disclosure/link per channel session and per conversation
  window;
- the ten-minute minimum between accepted non-promotional proactive messages;
- a prepare/commit transition: `drop` does not consume state, while `shadow` or
  a live send attempt does;
- a session reset that restores the one-link allowance without carrying state
  across runs.

The policy belongs between normalized original-chat output and
`TwitchPublicOutputRouter`. It must receive the structured trigger and
conversation identity but must not send directly. The existing router remains
the sole public-output boundary and continues to enforce shadow/live state,
allow-list, budgets, manual promotion, failure degradation, and kill-switch.

## Production Work for Ticket 04

- Add an explicit, default-off canary/promotion configuration; existing
  workspaces must not begin promoting because this feature exists.
- Introduce a typed promotion decision and bounded session/window state in a
  module separate from perception, prompt construction, and public routing.
- Compose the deterministic decision with `OriginalChatResponse` in the
  Reactor while keeping the router as the only send path.
- Record reason codes and cap state without copying chat content, credentials,
  or private authorization evidence.
- Test classifier negatives, exact-copy ownership, same/cross-window
  repetition, reset, injection, budget drop, shadow, live send attempt,
  allow-list, manual promotion, kill-switch, and `announce_ai: false`.
- Set or enforce the canary's proactive interval at 600 seconds; the generic
  minute/hour send budgets remain an independent stricter-or-looser safety
  layer, not a substitute.

## Evidence Limits

- The classifier corpus is intentionally small, English-only, and synthetic.
  Zero prototype errors do not establish general natural-language accuracy.
- Naturalness is a single observable composition check, not a human
  evaluation.
- Shadow policy composition is simulated with the real pure policy; no Twitch,
  sender, model provider, credentials, broadcaster permission, or live
  environment was exercised.
- Ticket 05 remains the authorization gate, and ticket 06 remains the only
  owner of live evidence.
