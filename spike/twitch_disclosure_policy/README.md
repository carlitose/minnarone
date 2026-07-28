# Twitch disclosure policy prototype

Question: which boundary—prompt-only, deterministic, or hybrid—can enforce the
approved disclosure, repository-link, and proactive cadence contract while
keeping answers natural?

Branch: logic.

Assumption: the first canary is English and uses the exact ticket-02 contract.
The corpus is synthetic and secret-free; classifier coverage is intentionally
narrow.

Useful result: one approach produces no false-positive promotion,
false-negative first disclosure, repeated link, or proactive cadence violation
in the corpus, preserves the contextual answer, and composes correctly with a
budget drop.

Run:

```bash
uv run python spike/twitch_disclosure_policy/prototype.py
uv run pytest spike/twitch_disclosure_policy/test_prototype.py -q
```

The script instantiates Minnarone's pure `PublicSendPolicy` in `shadow` mode.
It never creates a sender, credential, socket, or Twitch network path.
