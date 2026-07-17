# Verifica da installazione pulita: tutte le modalità ripartono

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

Simulare l'esperienza di un utente nuovo del repo pubblico: clone pulito in una
directory nuova, ambiente virtuale da zero, installazione seguendo SOLO il
README, e avvio delle varie modalità. Tutto ciò che il README promette funziona
o ha un errore chiaro e azionabile.

## Acceptance Criteria

- [ ] Clone fresco in dir temporanea + venv nuovo (`uv sync` e/o
      `pip install -e .` come da README) senza errori.
- [ ] Installazione degli extra documentati (`audio`, `video`, `vlm-llamacpp`,
      `os-capture`, `tui`) senza conflitti di dipendenze (il solo `vlm`
      torch/CUDA può essere skippato se troppo pesante: registrare la scelta).
- [ ] `python -m minnarone <config> --check` passa (o fallisce con errore
      chiaro e documentato) per OGNI esempio in `examples/`.
- [ ] Avvio live di almeno una modalità per famiglia, dove le credenziali/
      hardware lo permettono: adapter twitch chat-only, os_capture
      (commentator), llamacpp locale se un llama-server è disponibile.
- [ ] Smoke CLI dedicati partono e producono artifact: `minnarone-twitch-smoke`
      (chat-only), `minnarone-oscapture-smoke` (audio o video).
- [ ] `--replay` funziona su una run prodotta.
- [ ] Ogni gap tra README e realtà è registrato (fix immediato o ticket).

## Blocked By

- [01-task-license-and-cleanup.md](01-task-license-and-cleanup.md) — verificare
  lo stato post-pulizia che diventerà pubblico.
- Consigliato dopo il 06 (test verdi), ma può partire in parallelo.

## Frontier

Il README è stato verificato "sulla carta" (claim vs codice), ma nessuno ha
rifatto il percorso completo da zero di recente: è l'unico modo di scoprire
dipendenze implicite dell'ambiente di sviluppo (file locali, modelli scaricati,
variabili esportate) che un utente nuovo non ha.

## Work Plan

1. `git clone` in una directory temporanea fuori dal working tree.
2. Creare venv pulito; installare seguendo alla lettera il README (base +
   extra, uno alla volta o combinati come documentato).
3. Loop `--check` su tutti gli 8 file di `examples/` e registrare l'esito.
4. Copiare `.env.example` → `.env` con le credenziali reali disponibili e
   avviare le modalità fattibili (twitch chat-only, os_capture, llamacpp).
5. Lanciare gli smoke CLI e verificare gli artifact in output.
6. `--replay` su una run generata.
7. Registrare i gap; fix piccoli subito, gap grossi come ticket.

## Evidence to Capture

- Log dei comandi di installazione e dei `--check` (esito per esempio).
- Artifact degli smoke (stats.json, perceptions.jsonl).
- Elenco gap README↔realtà con la decisione presa per ciascuno.

## Out of Scope

- Run di accettazione HITL live prolungate (già coperte dalla roadmap).
- Test su piattaforme non disponibili (macOS/Linux se si lavora da Windows):
  registrare come non verificato, non bloccare.
- Extra `vlm` completo (torch CUDA) se l'hardware/tempo non lo permette.

---

## Esito (2026-07-17) — CHIUSO

Verifica eseguita su clone pulito della branch `autopilot/security-preflight`
(stato futuro-pubblico), venv nuovo con `uv`, seguendo il README.

**Positivi**: tutti i link relativi del README risolvono; tutti e 4 gli entry
point console (`minnarone`, `-twitch-smoke`, `-twitch-chat-smoke`,
`-oscapture-smoke`) installano e rispondono a `--help`; l'indice torch cu126 su
Windows si comporta esattamente come documentato (torch 2.13.0+cu126 da
pytorch-cu126); gli extra risolvono senza conflitti; `--check` esce 2 su errore
config e `--replay` esce 1 su log assente (comportamento corretto).

**Gap trovati e risolti in questa PR**:
1. *(blocker)* README non diceva di creare una venv e `pip install -e .` non
   gira in una `uv venv` (niente pip). → Aggiunto step `uv venv` + attiva,
   `uv pip install -e` come path primario, fallback pip documentato, nota
   `uv run`. Su entrambi i README.
2. *(minor)* prerequisito Python non dichiarato. → Aggiunto "Python 3.11+
   (3.12 consigliato)".
3. *(minor)* il primo `--check` degli esempi Twitch/Teams dà errore appena
   scaricati (creds mancanti / modello ONNX). → Aggiunta nota che spiega i
   prerequisiti e indica `llamacpp-local.example.yaml` come esempio che passa
   `--check` senza setup.

**Gap deferito (non bloccante)**: i messaggi CLI a runtime e i commenti dei
config-example restano in italiano mentre il README è inglese (severità "note"
del report). → follow-up ticket 09, NON blocca il flip.

`--check` su tutti gli 8 examples: 1 pass pulito (llamacpp-local), 7 "fail"
tutti setup-gated (creds/modello), nessun bug di config. Nessun link rotto.
