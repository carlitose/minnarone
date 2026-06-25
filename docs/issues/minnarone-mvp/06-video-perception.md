## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

La **percezione video** end-to-end: l'`OSCaptureAdapter` (parte screen) alimenta il `VideoPerceiver` che campiona i frame, salta quelli quasi-identici via hashing, e genera caption testuali via VLM, scritte come `Perception(source=video, type=caption)`. Da qui l'agente può integrare ciò che vede a schermo dentro un messaggio (es. riconoscere un oggetto mostrato).

Demo: mostro qualcosa a schermo → l'agente produce un messaggio che fa riferimento a ciò che vede.

Riferimenti PRD: *Step-by-Step* 3 (parte screen), 6; *Implementation Decisions* (VideoPerceiver); FR02, UC06.

## Step-by-step implementation plan

1. **Implementa la parte screen di `OSCaptureAdapter`** (screen capture). Perché ora: il `VideoPerceiver` ha bisogno dei frame. Dipende dall'adapter già introdotto in slice 05. Trappola: permessi macOS per la cattura schermo.
2. **Implementa il `VideoPerceiver`**: sampling → hashing (salta frame ~uguali) → VLM caption → `Perception`. Verifica: frame quasi identici saltati; frame nuovi producono caption sensate. Trappola: non fare caption a ogni frame (costo/latenza) — campionare.
3. **Verifica l'integrazione nel prompt:** le caption video entrano nella sezione percezioni recenti del prompt. Verifica end-to-end: mostrando un oggetto, l'agente lo menziona in un messaggio.

## Acceptance criteria

- [ ] I frame quasi-identici vengono saltati (hashing); i frame nuovi producono caption.
- [ ] Le caption finiscono nello store come `Perception(source=video, type=caption)`.
- [ ] L'agente integra ciò che vede a schermo in un messaggio.
- [ ] Il captioning è campionato, non per-frame (vincolo costo/latenza rispettato).
- [ ] Test di contratto su `VideoPerceiver` (fake VLM) incluso il salto-frame da hashing.

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)
- Blocked by [05-audio-perception.md](./05-audio-perception.md)

## User stories addressed

- User story 9
- User story 18
