## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The operator documentation for public sending, and the repository-wide
rewrite of the "no send path exists" safety claims that slices 05–08 made
obsolete. After this slice, an operator can go from zero to a compliant
attended live run using only the docs.

Content: dedicated bot account setup; write-scope token generation into the
NEW env var (never in YAML); allow-list workflow (explicit streamer
authorization before adding a channel); shadow rehearsal workflow; live
enablement checklist (attended-only, TUI-only, manual promotion, kill-switch
at hand); budget/cap guidance; and the updated safety summary: "sending
exists behind shadow-default, allow-list, budget, kill-switch and a separate
credential".

## Step-by-step implementation plan

1. Write the public-send operator guide sections.
   - What: extend the Twitch operator guide with the content above, in the
     same layered style as the existing smoke/commentator sections (isolated
     checks before full runs). Include an example `twitch.send` YAML block
     with `shadow` (never `live`) as the example value.
   - Why now: slices 07/08 fixed the final workflow; docs can now be exact.
   - Affects: operator guide, example configs (a commented `send` block in
     the commentator example, defaulting off/shadow).
   - Verify: a dry read-through executes cleanly against the real TUI; docs
     tests pass if the repo has them for this guide.
   - Pitfall: never show a real token or a live-mode example config.

2. Rewrite stale safety claims.
   - What: find every doc sentence promising "no PRIVMSG write path exists" /
     "does not send chat messages" and rewrite it to the gated-sender claim,
     preserving what is still true per-runtime (e.g. smoke commands still
     never send; `off`/`shadow`/private runtimes still never send).
   - Why now: false safety claims are worse than none.
   - Affects: operator guide, README if applicable, example config comments.
   - Verify: a repo-wide search for the old claims returns only historical
     documents (PRDs/issues/ADRs, which are records, not promises).
   - Pitfall: per-mode precision matters — the read-only guarantees of the
     non-live modes are a feature; keep stating them confidently.

3. Document the safety asymmetry for reviewers.
   - What: a short note (operator guide or contributing notes) stating the
     invariant: only `TwitchChatSender` may write `PRIVMSG`; any new direct
     IRC write elsewhere is a defect.
   - Why now: the PRD names this as a standing review rule.
   - Affects: docs.
   - Verify: the invariant is stated once, findable by search.
   - Pitfall: keep it one paragraph; it is a review heuristic, not policy
     prose.

## Acceptance criteria

- [ ] An operator can set up account, token, allow-list, shadow rehearsal, and attended live run from docs alone.
- [ ] All stale "no send path" claims are rewritten with per-mode precision.
- [ ] Example configs show `shadow` at most; live appears only as a documented checklist, not as example YAML.
- [ ] The single-writer invariant (`TwitchChatSender` only) is documented.
- [ ] No secrets or real tokens anywhere in docs.

## Blocked by

- Blocked by [07-live-mode-behind-gates.md](./07-live-mode-behind-gates.md)
- Blocked by [08-promotion-and-kill-switch-keys.md](./08-promotion-and-kill-switch-keys.md)

## User stories addressed

- User story 3
- User story 4
- User story 19
- User story 26
- User story 27
- User story 34
