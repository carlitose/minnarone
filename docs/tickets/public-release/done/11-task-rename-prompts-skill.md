# Rinominare la skill `prompts` end-to-end

## Parent Spec

[public-release-wayfinder.md](../../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

La skill prima chiamata `prompts` usa ovunque il nome canonico
`minnarone-prompts`, senza symlink rotti, self-reference stantie o link README
non validi.

## Acceptance Criteria

- [x] Directory `.agents/skills/minnarone-prompts/`, frontmatter `name:` e
      titolo della skill usano il nome deciso.
- [x] Il symlink `.claude/skills/minnarone-prompts` punta alla directory
      versionata corretta; il vecchio alias è stato rimosso.
- [x] Script e comandi interni non contengono path
      `.claude/skills/prompts` stantii.
- [x] Il riferimento già esistente nei due README continua a funzionare col
      nuovo path, senza anticipare il catalogo del ticket 17.
- [x] Il symlink personale `project-designer` è stato rimosso.
- [x] Validate/try della skill e test mirati dei prompt passano.

## Blocked By

- [10-grilling-skill-catalog-and-rename.md](10-grilling-skill-catalog-and-rename.md) — done

## Frontier

Risolta: rename atomico completato e validato. Il catalogo pubblico completo
resta nel ticket 17.

## Work Plan

1. Applicare rename directory/frontmatter/symlink come operazione coerente.
2. Aggiornare self-reference, README e docs attivi eseguibili.
3. Rimuovere vecchio alias e symlink personale.
4. Eseguire validazione skill, validate-prompts, preview e test mirati.
5. Controllare diff e risoluzione dei symlink.

## Evidence to Capture

- `quick_validate.py`: `Skill is valid!`.
- `minnarone validate-prompts`: 9/9 file validi.
- Preview tramite `.claude/skills/minnarone-prompts/preview_prompt.py`: exit 0.
- Test mirati prompt/CLI: 182 passed.
- `make quality`: format, Ruff, Vulture, Deptry e Pylint passati.
- Due review indipendenti: pass dopo il fix del carve-out `.gitignore`.
- Symlink nuovo risolto; alias `prompts` e `project-designer` assenti.

## Out of Scope

- Aggiungere altre skill.
- Scrivere il catalogo pubblico completo nel README.
- Cambiare i nove prompt default impacchettati.

## Status

Done — 2026-07-18.
