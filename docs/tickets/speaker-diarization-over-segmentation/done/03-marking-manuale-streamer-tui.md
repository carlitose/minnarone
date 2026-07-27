## Parent Spec

[speaker-diarization-over-segmentation.md](../../specs/speaker-diarization-over-segmentation.md)

## What to Build

Dare all'operatore un modo manuale e robusto di indicare chi è lo/gli streamer,
dato che l'identificazione automatica (freeze del cluster dominante dopo il
warmup) è fragile con embedding rumorosi. Vincolo: su Twitch l'audio è un unico
stream mixato, quindi non si può taggare per sorgente — l'unico segnale pratico
è "la voce che sta parlando ora".

Comportamento: un tasto nella TUI marca il cluster della voce corrente/ultima
come `STREAMER` in modo permanente. Premere su voci diverse consente **più
streamer**. L'auto-dominante resta come fallback finché l'operatore non marca
nulla; dopo il primo marking manuale, comanda il manuale. La transizione è
registrata come evento di run (attore `operator`).

Si aggancia al command-surface TUI già esistente per promote/kill-switch
(SendCommandSurface, dallo sviluppo public-send) — stesso pattern comando →
agente, risultato → display.

## Acceptance Criteria

- [ ] Un tasto TUI marca la voce corrente/ultima come `streamer`; il cluster
      relativo viene etichettato `streamer` da lì in poi.
- [ ] Premendo su voci diverse si ottengono più cluster `streamer`
      (multi-streamer).
- [ ] Finché non si marca nulla, l'auto-dominante (freeze warmup) resta attivo
      come fallback.
- [ ] La marcatura manuale ha precedenza sull'auto-dominante e non viene
      sovrascritta dal freeze automatico.
- [ ] Ogni marcatura è registrata come evento con attore `operator` e visibile
      in replay.
- [ ] Il runtime console (non-TUI) non ha questo comando (coerente col fatto che
      le mutazioni stanno nella TUI).
- [ ] Test unitari sul command-surface con una policy/tagger fake; nessuna rete.

## Blocked By

- [01-collasso-altro.md](./01-collasso-altro.md)

## Frontier

Bloccato dal ticket 01 (il modello di etichette `streamer`/`altro`/`?` deve
esistere prima). Implementazione AFK; l'accettazione dal vivo è nel ticket 05.

## Step-by-Step Implementation Plan

1. Estendere il command-surface della TUI (pattern SendCommandSurface) con un
   comando "marca streamer corrente" che delega al tagger/clusterer: promuove il
   cluster dell'ultima utterance a `STREAMER`. Restituire accepted/rejected +
   motivo per il display.
2. Nel clusterer (`src/minnarone/speaker.py`), aggiungere una via per pinnare un
   `cluster_id` come streamer manuale (set di streamer manuali) che `_label_for`
   rispetta e che il freeze automatico non sovrascrive. Supportare più id.
3. Aggiungere il keybinding nella TUI con feedback nello status/pannello; il
   comando è una mutazione esplicita (le altre restano read-only).
4. Registrare la transizione come evento di run (attore `operator`, motivo).
5. Test: command-surface con fake (marca → cluster diventa streamer; seconda
   marca → secondo streamer; console non espone il comando; auto-dominante
   resta finché non si marca).

Pitfall: non far sì che il freeze automatico "scippi" un cluster marcato
manualmente. Non trasformare l'intera TUI in read-write: solo questo comando (e
i comandi send esistenti) mutano. Attenzione all'allineamento temporale: "voce
corrente" = cluster dell'ultima utterance emessa, non un'istantanea audio.

## Testing Plan

- Unit test del command-surface con policy/tagger fake (accept/reject, multi
  streamer, precedenza sul fallback).
- Test TUI del keybinding se esiste un pattern (come per promote/kill-switch).
- Manuale (ticket 05): dal vivo, marcare lo streamer mentre parla e verificare
  che le sue utterance successive diventino `streamer`.

## Out of Scope

- Il collasso `[ALTRO]` (ticket 01, prerequisito).
- Enrollment da campione audio (via alternativa scartata nello spec).
- Hardening merge/tetto del clusterer (ticket 04).
