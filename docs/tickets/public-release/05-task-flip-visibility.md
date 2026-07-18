# Flip della visibilità GitHub a public e verifica post-flip

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

Il repo è pubblico su GitHub e verificato dall'esterno: clone anonimo
funziona, README renderizza con link relativi validi, licenza riconosciuta da
GitHub, nessun contenuto inatteso in issue/PR pubbliche.

## Acceptance Criteria

- [ ] Visibilità cambiata a public (Settings → Danger Zone → Change visibility,
      oppure `gh repo edit --visibility public`).
- [ ] GitHub mostra il badge "MIT license" nella pagina del repo.
- [ ] Clone anonimo (senza credenziali) riesce.
- [ ] I link relativi del README (docs/, examples/, .env.example) funzionano
      nella pagina GitHub.
- [ ] Issue e PR esistenti riviste: nessun contenuto da nascondere.

## Blocked By

- [01-task-license-and-cleanup.md](done/01-task-license-and-cleanup.md)
- [02-grilling-screenshots-review.md](done/02-grilling-screenshots-review.md)
- [03-grilling-readme-language.md](done/03-grilling-readme-language.md)
- [04-task-security-preflight.md](done/04-task-security-preflight.md)
- [06-task-fix-failing-tests-on-main.md](done/06-task-fix-failing-tests-on-main.md)
- [07-task-fresh-install-verification.md](done/07-task-fresh-install-verification.md)
- [08-task-readme-english.md](done/08-task-readme-english.md)
- [10-grilling-skill-catalog-and-rename.md](done/10-grilling-skill-catalog-and-rename.md)
- [11-task-rename-prompts-skill.md](done/11-task-rename-prompts-skill.md)
- [12-research-first-operator-journey.md](done/12-research-first-operator-journey.md)
- [13-grilling-persona-facts-onboarding.md](done/13-grilling-persona-facts-onboarding.md)
- [14-research-public-twitch-safety.md](done/14-research-public-twitch-safety.md) — done
- [15-research-runtime-model-profiles.md](15-research-runtime-model-profiles.md)
- [16-prototype-agent-and-human-onboarding.md](16-prototype-agent-and-human-onboarding.md)
- [17-task-readme-skill-catalog-onboarding.md](17-task-readme-skill-catalog-onboarding.md)
- [18-task-fix-operator-journey-drift.md](18-task-fix-operator-journey-drift.md)

## Frontier

Azione finale e di fatto irreversibile: dal momento del flip la history è
copiabile da chiunque. Va eseguita solo a mappa completamente verde, con
conferma esplicita dell'utente al momento del flip.

## Work Plan

1. Confermare con l'utente che 01–04 sono chiusi e che si procede.
2. Rileggere rapidamente issue/PR esistenti su GitHub.
3. Eseguire il flip (UI o `gh repo edit --visibility public`).
4. Verifica post-flip da sessione anonima: pagina repo, badge licenza, link
   README, clone.
5. Chiudere la mappa (Status: Done) e registrare l'esito.

## Evidence to Capture

- URL pubblico del repo.
- Screenshot o esito testuale delle verifiche post-flip.

## Out of Scope

- Promozione (social preview, topics, description GitHub) — post-flip
  opzionale.
- CONTRIBUTING.md, code of conduct, CI badge.
