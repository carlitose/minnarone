# Follow-up esternalizzazione prompt: canale, header, hardening, skills, igiene

## Type

Wayfinding spec

## Status

Active

## Destination

Chiudere i quattro debiti lasciati aperti dall'esternalizzazione dei prompt
(PR #35, mappa [prompt-externalization-wayfinder](./prompt-externalization-wayfinder.md)):

1. **Canale da config (bug)**: il prompt usa `_DEFAULT_CHANNEL="enkk"` e IGNORA
   `config.twitch.channel` (campo già esistente e obbligatorio quando `twitch:` è
   presente — es. `examples/twitch-original-chat.example.yaml` ha
   `channel: multiplayerit` ma il prompt direbbe "enkk"). Il prompt deve seguire
   la config.
2. **Header di sezione e cambio lingua**: gli header (`[REGOLE]`,
   `[FORMATO RISPOSTA]`, `[SITUAZIONE]`, `[CHAT RECENTE]`, ...) sono ancore
   cablate in italiano → un prompt-set inglese resta "a metà" (corpi inglesi,
   header e riferimenti incrociati italiani). Serve esternalizzarli SENZA perdere
   la coerenza dei riferimenti incrociati.
3. **Hardening validazione + skills di repo**: (a) validazione per-sezione /
   strict-set mode così un override malformato fallisce all'AVVIO, non a runtime;
   (b) skills locali del repo (`.claude/skills/`) perché un code agent possa
   gestire i prompt in autonomia: validarli, modificarli in sicurezza, provarli
   contro l'app.
4. **Igiene pre-esistente**: 35 errori ruff in test non correlati (rompono
   `make quality`) e 5 fail di `test_vlm.py` per extra assente (manca
   `importorskip`).

## Decisions So Far

- **Base**: branch `worktree-prompt-externalization` / PR #35 (o `main` dopo il
  merge). Tutto il follow-up poggia sul loader `prompt_source.py` e sui file in
  `src/minnarone/prompts/`.
- **Punto 1 è un bug, non un enhancement** — verificato 2026-07-17:
  `TwitchConfig.channel` esiste, è obbligatorio quando `twitch:` c'è
  (`config.py:387,466-467`), `config.twitch` è `TwitchConfig | None`
  (`config.py:866`); `app.py:977,1016` costruisce `PromptBuilder` senza passare
  `channel`.
- **Approccio header (punto 2) — riferimenti via placeholder**: esternalizzare
  gli header in un file a chiavi (`headers.md`) e far riferire i corpi delle
  situazioni agli header **tramite placeholder** (es.
  `{{header_self_messages}}`) risolti dal loader DALLA STESSA FONTE che rende
  gli header. Così il riferimento incrociato non può divergere: se l'operatore
  rinomina un header nel suo set, i testi che lo citano si aggiornano da soli.
  I marcatori di SICUREZZA (fence `DATI_PERCEPITI`, prefisso `| `) restano
  cablati: non sono header di sezione tunabili.
- **Fix vlm (punto 4b) = skip, non install**: i test devono *skipparsi* con
  `pytest.importorskip("transformers")` quando l'extra non c'è (oggi falliscono
  hard). Installare l'extra pesante in dev non è richiesto.
- **Ruff (punto 4a)**: 35 errori censiti — 14 E402, 8 I001, 7 F401, 4 F841,
  1 F811, 1 B011; 16 auto-fixabili con `--fix`. Pulizia meccanica, file di test
  non correlati.

## Not Yet Specified

- **Set di skills esatto (punto 3b)** — assunzione di lavoro da confermare col
  ticket: una skill `prompts` (o 2-3 piccole) che copra: *validate* (carica e
  valida un set/override con l'entry-point reale), *edit* (flusso guidato:
  modifica → valida → test render → diff vs default), *try* (costruisce il
  prompt con un set e lo mostra / smoke run dell'app). Prerequisito tecnico: un
  comando invocabile (`minnarone validate-prompts --prompts-dir ...` o
  equivalente) che le skill possano chiamare — oggi la validazione avviene solo
  costruendo l'app.
- **Header per stile non-original-chat** (`## RIASSUNTO`, ...): stessi meccanismi
  o restano cablati? Da decidere nel ticket 03 (probabile: stessa soluzione).
- **Fallback canale** quando `config.twitch` è None (run non-Twitch): resta
  "enkk" o meglio un placeholder neutro? Decisione nel ticket 01 (proposta:
  resta il default attuale, il caso è marginale).

## Out of Scope

- Nuove lingue mantenute dal progetto (l'operatore riscrive i file; qui si
  rimuovono solo gli ostacoli tecnici residui).
- Hot-reload dei prompt a runtime.
- Esternalizzare fence/regole di sicurezza (decisione già presa: cablate).
- CI/pipeline nuove per la validazione (le skill girano in locale).

## Frontier / Blocking Edges

- **Edge #1 — nessuno bloccante per 01/04/05/06**: canale, ruff e vlm sono
  pronti e indipendenti.
- **Edge #2 — design dei riferimenti-via-placeholder (ticket 03)**: è l'unico
  pezzo con rischio di design (tocca byte-invarianza e validazione); va fatto
  dopo il merge di PR #35 per non gonfiarla.
- **Edge #3 — la skill (06) dipende dal comando di validazione (05)**.

## Ticket Plan

| # | Tipo | Titolo | Output atteso |
|---|------|--------|---------------|
| 01 | task | Canale dal config: `twitch.channel` → PromptBuilder | Il prompt usa il canale configurato; default solo se `twitch` assente |
| 02 | task | Validazione per-sezione / strict-set mode | Token/placeholder validati per chiave; override malformato fallisce all'avvio |
| 03 | task | Header esternalizzati con riferimenti via placeholder | `headers.md` + corpi che citano header via `{{header_*}}`; set inglese completo possibile |
| 04 | task | Fix 35 errori ruff pre-esistenti | `uv run ruff check src tests` pulito; `make quality` step ruff verde |
| 05 | task | `test_vlm` skip-if-missing + comando validate-prompts | vlm skippa senza extra; esiste un entry-point CLI di validazione set |
| 06 | task | Skill di repo `prompts` per il code agent | `.claude/skills/prompts*` che valida/modifica/prova i prompt usando il comando del 05 |

Dipendenze: 01, 02, 04 indipendenti e pronti. 03 dopo 02 (la validazione
per-sezione deve coprire anche `headers.md`). 05 pronto (le due parti sono
indipendenti fra loro ma piccole). 06 dopo 05.

## Next Review

Dopo 02+03: verificare con un set inglese COMPLETO (header inclusi) che lo swap
di lingua sia davvero totale e che la byte-invarianza coi default regga. Dopo 06:
provare la skill end-to-end su un override volutamente rotto (deve fallire
all'avvio con messaggio chiaro).
