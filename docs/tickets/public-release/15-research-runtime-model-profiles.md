# Definire profili runtime e acquisizione modelli ripetibile

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

research

## Outcome

Definire una matrice di profili supportati che permetta a un nuovo utente di
scegliere chat-only, CPU-light, Apple Silicon, CUDA o llama.cpp conoscendo
dipendenze, modelli, disco/RAM/VRAM, licenze e comandi di verifica.

## Acceptance Criteria

- [ ] Ogni profilo dichiara canali abilitati, extra `uv`, tool di sistema,
      modello/i, dimensioni indicative e hardware minimo/raccomandato.
- [ ] I modelli consigliati hanno fonte, licenza, checksum/versione o strategia
      di pinning verificabile.
- [ ] È risolto il rischio del modello speaker `zh-cn` usato su audio italiano.
- [ ] Nessun esempio pubblico richiede path assoluti dell'autore.
- [ ] È deciso se download/setup vive in docs, script, `doctor` o skill.

## Blocked By

- [12-research-first-operator-journey.md](done/12-research-first-operator-journey.md) — done

## Frontier

La pipeline completa è stata provata solo perché la macchina conteneva già
circa 1.5 GB di ASR, un ONNX speaker e oltre 4 GB di Qwen2-VL. Un clone pubblico
non può ricostruire questo stato dal README in modo lineare.

## Work Plan

1. Inventariare extra, import lazy, model config e tool di sistema per canale.
2. Verificare fonti/licenze/requisiti dei modelli candidati.
3. Definire profili progressivi e smoke di accettazione per ciascuno.
4. Confrontare docs-only, script di download e doctor guidato.
5. Aggiornare mappa e input del prototipo 16.

## Evidence to Capture

- `pyproject.toml`, example config, operator guide e dimensioni modello.
- Documentazione primaria dei model owner e runtime.
- Esiti smoke per i profili disponibili sull'hardware corrente.

## Out of Scope

- Scaricare e committare pesi nel repository.
- Garantire tutte le GPU/OS.
- Ottimizzazione prestazionale profonda dei modelli.
