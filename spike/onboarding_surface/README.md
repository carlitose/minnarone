# Ticket 16 onboarding surface spike

Disposable comparison of three onboarding surfaces:

1. tutorial/templates only;
2. one combined skill plus production `init/doctor` CLI;
3. two thin repo-local skills backed by canonical docs and a model manifest.

The spike never downloads models, contacts Twitch or promotes live. It writes
persona/facts only after an exact preview digest is confirmed. `doctor.py` is
read-only and accepts only `send_mode: shadow`.

## Run

```bash
uv run python -m unittest discover -s spike/onboarding_surface -p 'test_*.py'
uv run python spike/onboarding_surface/compare.py
uv run python spike/onboarding_surface/onboarding.py \
  spike/onboarding_surface/fixtures/answers.json
uv run python spike/onboarding_surface/doctor.py \
  spike/onboarding_surface/manifest.json \
  spike/onboarding_surface/fixtures/scenario-p0.json
```

The unit suite uses temporary directories, performs a real
`minnarone <config> --check` with non-secret dummy environment values, and
exercises the production send policy offline to prove shadow cannot promote.

## Disposition

Promote only the decision and, in ticket 17, production versions of the two
skills. Discard `onboarding.py`, `doctor.py`, fixtures and comparison code after
the public surfaces exist. Do not install these spike skills directly.
