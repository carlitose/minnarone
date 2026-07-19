# Rendere README e repo task-first per umani e code agent

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

I README portano rapidamente a un percorso chat-only e a uno multimodale,
spiegano config/soul/facts/prompt e pubblicano il catalogo delle skill deciso.
Un `AGENTS.md` e contributor pointers rendono il repo utilizzabile da code agent
senza contesto privato.

## Acceptance Criteria

- [ ] README inglese e italiano iniziano con un quickstart task-first e rimandano
      i dettagli lunghi alle guide operative.
- [ ] È spiegata senza ambiguità la differenza tra config, `soul`, `facts` e
      prompt template/override.
- [ ] Il catalogo elenca ogni skill pubblica col nome canonico, trigger, azioni,
      confini e link funzionante.
- [ ] Sono presenti golden path progressivi: chat-only shadow, media smoke,
      full multimodal, live attended-only con doppio `p` e `k`.
- [ ] Il live documenta consenso broadcaster, account bot dedicato, validazione
      token, disclosure e fallback shadow/stop senza promettere il Chat Bot
      Badge sul trasporto IRC; distingue inoltre i limiti Twitch dai budget
      conservativi Minnarone.
- [ ] La guida dichiara `retention.perceptions_days` inerte ed elenca artifact,
      cancellazione manuale e opt-out finché manca enforcement runtime.
- [ ] Config/template pubblici non contengono path personali né credenziali.
- [ ] I golden config italiani usano CAM++ English VoxCeleb con
      `dimension: 512` e spiegano che il vecchio zh-cn 192-dim non è il default.
- [ ] `AGENTS.md`/CONTRIBUTING pointers coprono architettura, comandi quality,
      prompt safety, worktree sporco e skill routing.
- [ ] Percorso umano e code-agent vengono verificati da clone pulito.

## Blocked By

- [11-task-rename-prompts-skill.md](done/11-task-rename-prompts-skill.md) — done
- [12-research-first-operator-journey.md](done/12-research-first-operator-journey.md) — done
- [16-prototype-agent-and-human-onboarding.md](done/16-prototype-agent-and-human-onboarding.md) — done
- [18-task-fix-operator-journey-drift.md](18-task-fix-operator-journey-drift.md)

## Frontier

Il README attuale è ricco ma lungo e reference-first. Il catalogo skill non può
essere scritto prima del rename e del prototipo, altrimenti documenterebbe
nomi/superfici destinati a cambiare.

## Work Plan

1. Ristrutturare la parte alta dei README attorno a risultati e profili.
2. Scrivere il catalogo skill e i confini tra skill/CLI/docs.
3. Aggiungere template/golden config sanitizzati e link alle guide dettagliate.
4. Aggiungere `AGENTS.md` e contributor/security pointers minimi.
5. Verificare link, comandi e due percorsi da clone pulito.

## Evidence to Capture

- Diff README/AGENTS/contributor docs.
- Link checker e log fresh clone.
- Checklist umana e code-agent completate.

## Out of Scope

- Tradurre tutta `docs/`.
- Marketing/social launch.
- Supportare ogni adapter nel quickstart iniziale.
