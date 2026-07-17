# Tradurre il README in inglese, conservare l'italiano come README.it.md

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

`README.md` è in inglese (prima impressione per il pubblico globale del repo),
la versione italiana attuale è conservata come `README.it.md`, con link
incrociati in testa a entrambi. Deriva dal grilling 03 (decisione utente
2026-07-17: "Inglese + README.it.md").

## Acceptance Criteria

- [ ] `README.md` interamente in inglese, contenuto equivalente all'attuale
      (nessuna sezione persa, link relativi invariati e funzionanti).
- [ ] `README.it.md` = versione italiana attuale (spostata, non riscritta).
- [ ] Link incrociati in testa: "🇮🇹 [Versione italiana](README.it.md)" /
      "🇬🇧 [English version](README.md)".
- [ ] Termini di dominio coerenti col codice (Perceptor, Reactor, Summarizer,
      soul/facts, shadow/live — restano in inglese come già sono).
- [ ] Il test docs che verifica il wording del README
      (`test_twitch_operator_docs.py`) aggiornato se guarda stringhe italiane
      — coordinarsi con il ticket 06.
- [ ] `pyproject.toml` `readme = "README.md"` continua a puntare al file giusto
      (nessun cambio necessario, solo verifica).

## Blocked By

- Consigliato dopo il [06](06-task-fix-failing-tests-on-main.md): il test docs
  sul wording del README va sistemato una volta sola, dopo la traduzione.

## Frontier

Il README inglese è l'ultima modifica di contenuto prima del flip: farla dopo
la verifica fresh-install (07) rischia di invalidarne l'esito; farla prima del
fix test (06) fa doppio lavoro sul test docs. Ordine consigliato: 06 → 08 → 07.

## Work Plan

1. Copiare l'attuale `README.md` → `README.it.md`.
2. Tradurre `README.md` in inglese, sezione per sezione, mantenendo struttura,
   code block e link identici.
3. Aggiungere i link incrociati in testa a entrambi.
4. Aggiornare i test docs che asseriscono wording italiano del README.
5. `pytest` sui test docs + controllo link relativi.

## Evidence to Capture

- Diff del README + esito pytest docs.

## Out of Scope

- Traduzione dei docs operativi (`docs/*.md`) e dei docs interni — restano in
  italiano.
- Riscrittura/miglioramento dei contenuti (solo traduzione fedele).
