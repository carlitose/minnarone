# 04 — Task: fix dei 35 errori ruff pre-esistenti

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

`uv run --extra dev ruff check src tests` esce pulito e lo step ruff di
`make quality` torna verde. Censimento (2026-07-17): 35 errori, tutti in file di
test non correlati ai prompt — 14 E402 (import non in testa), 8 I001 (import
disordinati), 7 F401 (import inutilizzati), 4 F841 (variabili inutilizzate),
1 F811 (ridefinizione), 1 B011 (`assert False`); 16 auto-fixabili con `--fix`.

## Acceptance Criteria

- [ ] `ruff check src tests` → 0 errori.
- [ ] Fix SOLO meccanici/comportamento-neutri: gli E402 vanno capiti prima di
      spostare gli import (spesso sono `pytest.importorskip` o setup di path
      intenzionali → in quel caso `# noqa: E402` mirato con motivo, non
      riordino cieco).
- [ ] B011 (`assert False`) sostituito con la forma idiomatica
      (`pytest.fail(...)` o `raise AssertionError(...)`).
- [ ] Suite completa verde dopo la pulizia (nessun test cambiato di significato).
- [ ] Niente refactor opportunistici: solo ciò che serve a zero-errori.

## Blocked By

- None — può partire subito.

## Frontier

Igiene: sblocca `make quality` come gate affidabile per tutti i lavori futuri.

## Work Plan

1. `ruff check --fix` per i 16 auto-fixabili; review del diff.
2. Passare a mano i restanti (E402 caso per caso, F841/F811/B011).
3. Suite completa + `make quality` (step ruff).

## Evidence to Capture

- Output ruff prima/dopo; diff.

## Out of Scope

- vulture/deptry/pylint di `make quality` (solo lo step ruff).
- I 5 fail di test_vlm (ticket 05).
