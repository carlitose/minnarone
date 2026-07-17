# 02 — Grilling: lifecycle del server, policy GPU, futuro del VLM, build-vs-buy

## Parent Spec

[local-llm-llamacpp-wayfinder.md](../../specs/local-llm-llamacpp-wayfinder.md)

## Type

grilling

## Outcome

Decisioni umane registrate su: (1) chi avvia/ferma `llama-server`; (2) come si
spartiscono la GPU il LLM e il VLM; (3) se il VLM migra a llama.cpp (e in quale
variante); (4) se l'opzione "motore di inferenza da zero" entra in roadmap o
viene archiviata con criteri espliciti.

## Acceptance Criteria

- [ ] Ogni domanda sotto ha una risposta registrata (o un'assunzione esplicita
      con data) nel wayfinder, sezione `Decisions So Far`.
- [ ] Le decisioni citano l'evidenza di 01 (numeri VRAM/tokens/s).
- [ ] L'esito determina la creazione o meno del ticket 06 e il perimetro di 05.

## Blocked By

- 01 (serve l'evidenza hardware/modello per decidere con cognizione).

## Frontier

Le tre scelte architetturali (lifecycle, GPU, VLM) cambiano cosa si implementa
in 05/06; deciderle dopo lo spike sarebbe rework, deciderle senza i numeri di
01 sarebbe tirare a indovinare.

## Work Plan

1. Presentare all'utente l'evidenza di 01 in forma compatta.
2. Porre le domande:
   - **Lifecycle**: minnarone spawna/uccide `llama-server` (pattern
     translate-lector: on-demand, PID file, reap, Job Object su Windows) o si
     assume un server lanciato a mano dall'utente? Primo step semplice
     (user-launched) con 06 come evoluzione?
   - **Policy GPU**: quale opzione del mapa (a–e)? Accettabile il VLM su CPU?
     Accettabile ridurre quant/ctx del LLM per far posto a Qwen2-VL?
   - **VLM su llama.cpp**: sostituire lo stack transformers/torch di `vlm.py`
     con llama-server (Qwen2-VL GGUF) o col multimodale Gemma (`--mmproj`)?
     O restare su torch per ora?
   - **Motore da zero**: quale sarebbe l'obiettivo reale (didattico? controllo?
     performance?)? Quale criterio lo giustificherebbe rispetto a llama.cpp?
     Se resta interessante → spec separata, non blocca questa mappa.
   - **Naming config**: `llm_provider: llamacpp`? Chiavi nuove
     (`llamacpp.base_url`, `llamacpp.model_path`, …) dove nello schema?
3. Registrare risposte/assunzioni nel wayfinder e chiudere il ticket.

## Evidence to Capture

- Risposte testuali dell'utente (o assunzioni marcate come tali).
- Eventuali vincoli nuovi emersi (es. "la GPU serve anche ad altro").

## Out of Scope

- Implementare alcunché; produrre solo decisioni.

---

## Risposte registrate (grilling 2026-07-16)

| # | Domanda | Decisione dell'utente |
|---|---------|----------------------|
| 1 | Policy GPU / destino del VLM | **MVP solo testo** (video spento in locale). Evoluzione designata: server multimodale unico Gemma 4 E2B + `--mmproj` al posto di `vlm.py`, decisa dai numeri dello spike 04 (VRAM mmproj, latenza/frame). Co-residenza torch+LLM esclusa su 4 GB; VLM su CPU scartato. |
| 2 | Lifecycle `llama-server` | **Utente avvia a mano**; minnarone fa solo health-check su `/health` (al `--check` e all'avvio) con errore chiaro. Niente gestione processo nell'MVP → ticket 06 NON attivato (resta slot condizionale). |
| 3 | Motore di inferenza da zero | **Archiviato** per questa mappa. Criterio di riapertura: llama.cpp diventa un limite reale (es. controllo scheduling VRAM non esposto). Interesse didattico → spec separata fuori da minnarone. |
| 4 | Naming config | `llm_provider: llamacpp` + blocco top-level `llamacpp:` con `base_url` (default `http://127.0.0.1:8080`). Niente `model` in config; `base_url` fuori da `llm_params`. |

**Trade-off accettati**: niente percezione video in locale finché la via multimodale non è misurata; l'operatore avvia il server; nessun fallback automatico al cloud.

**Assunzione residua**: qualità del quant QAT sul task reazioni → verificata nello spike 04 (fallback: E2B Q4_K_XL non-QAT).

### Criteri di accettazione

- [x] Ogni domanda ha risposta registrata
- [x] Decisioni informate dall'evidenza di 01 (4 GB VRAM, misure live)
- [x] Esito su 06 (non attivato) e perimetro di 05 (solo testo) determinati
