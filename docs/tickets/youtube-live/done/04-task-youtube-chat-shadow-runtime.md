---
ticket_schema: 1
ticket_id: "04"
execution_mode: AFK
blocked_by:
  - "01"
  - "02"
  - "03"
---

# Implementare il golden path YouTube chat-only shadow

## Parent Spec

[youtube-live-wayfinder.md](../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Minnarone può scoprire e leggere una live chat YouTube, normalizzarla nel core
esistente e generare candidate reaction osservabili, senza possedere né usare
un percorso di invio?

Output atteso: tracer bullet di produzione `adapter: youtube` chat-only shadow,
con config, reader, wiring, test, esempio sanitizzato e guida operatore.

## What to Build

Implementare la verticale minima scelta dai ticket 01–03: target canonico e
discovery, `YouTubeLiveChatReader` fakeabile, composizione `SourceAdapter`,
config fail-closed, build wiring, output shadow, run events/TUI già disponibili
e una golden path locale. La chat emette la shape `RawEvent` già consumata da
`ChatPerceiver`.

Sezioni coperte: `Destination` punto 1 e `Chat-only shadow` nella frontiera.

## Evidence Required

- Contratti 01 e decisione/prova 03 citati nei docstring e nella guida dove
  influenzano pacing, auth, lifecycle e failure.
- Test fake per discovery, cursor/paging/stream, chat vuota, dedup, pacing,
  errori temporanei/fatali, quota, revoca e stop.
- Prova che `--check` resta offline/lazy e che shadow non legge credenziali di
  invio né costruisce un sender.

## Acceptance Criteria

- [ ] `Config` accetta solo una sezione YouTube documentata, rifiuta campi
  ignoti e combinazioni incoerenti e non altera i config Twitch esistenti.
- [ ] Il reader conserva testo e identità pubblica minima necessaria, senza
  portare payload Google nel core o nei prompt.
- [ ] Polling/stream segue il pacing ufficiale, ha retry bounded e non effettua
  busy-loop o consumo quota nascosto.
- [ ] Live terminata/chat disabilitata/auth revocata/quota esaurita producono
  esiti distinti e fail-closed; stop e cleanup sono bounded.
- [ ] La reazione arriva in `[SHADOW]`/TUI e nessun test o runtime shadow può
  chiamare un endpoint di insert.
- [ ] Esempio e guida spiegano secret, artifact, retention inerte, disclosure e
  che una live pubblica non equivale ad autorizzazione al send.
- [ ] Test mirati e quality suite passano senza indebolire test Twitch.

## Frontier

Dependency-blocked by 01, 02 and 03. Diventa il primo ticket di produzione solo
dopo contratto, interfaccia e prova read-only approvati.

## Step-by-Step Implementation Plan

1. Aggiungere test config/reader/wiring che falliscono e fixture API sanitizzate.
2. Implementare target/discovery e transport client dietro protocolli iniettati,
   con pacing e lifecycle dal report 01.
3. Comporre un adapter chat-only con `MergingSourceAdapter` solo se il design 02
   lo richiede; collegarlo in `build_agent` senza branch Twitch regressivi.
4. Cablarlo al percorso `mode: public` original-chat e router shadow senza
   introdurre sender o token write.
5. Aggiungere esempio onboarding e operator guide, poi eseguire test e lint.

## Testing Plan

Test unitari fake del transport e parsing; test config; app-level tracer bullet
RawEvent→Perception→Reactor→shadow; test che fallisce se un sender/insert viene
costruito; regression Twitch/OS capture; `uv run pytest`, Ruff check e format.

## Out of Scope

- Audio/video della live.
- Endpoint di insert, token write, live promotion e self-echo.
- Broadcast creation/transition, moderation, analytics o multi-live.
- Smoke di rete automatica in CI.
