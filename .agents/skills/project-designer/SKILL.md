---
name: project-designer
description: >
  Interactive project design skill that guides users through a structured 3-phase process to produce
  a complete software specification document. Use when a user wants to: (1) plan a new software project
  from scratch, (2) design the architecture of an application, (3) create a technical specification,
  (4) do requirements gathering for an app or system, (5) produce a project blueprint or design doc.
  Triggers on phrases like "design a project", "plan an app", "create a specification", "architect a system",
  "help me plan a software project", "requirements gathering", "technical design", "system design document".
  Do NOT use for existing codebases, code reviews, debugging, or general coding tasks.
---

# Project Designer

Interactive 3-phase process to design a software project from idea to complete specification document.

## Core Behavior

- **Always interactive**: ask one question at a time, wait for user response
- **Never assume**: always ask, never go off on tangents
- **Summarize and confirm**: at the end of each phase, present a summary table and get explicit approval
- **Rigid order**: always follow Phase 1 → Phase 2 → Phase 3
- **Output**: generate a single comprehensive Markdown document at the end

## Workflow

```
Phase 1: Requirements → Phase 2: Specifications → Phase 3: System Design → Output MD
```

Each phase has a defined question sequence. See [phases.md](phases.md) for detailed phase instructions.

## Interaction Rules

1. **One question per message** — never overwhelm with multiple questions
2. **Provide options** — offer numbered choices to speed up decisions
3. **Track IDs** — assign IDs to all items (FR01, NFR01, US01, UC01, EC01, QR01)
4. **Use tables** — present summaries as Markdown tables
5. **Confirm before advancing** — at each phase boundary, show full summary, ask for confirmation
6. **Respect scope** — MVP = minimal, enterprise = scale up
7. **Match user language** — respond in the language the user writes in
8. **Challenge gently** — suggest alternatives but respect user's final decision

## Output

See [output-template.md](output-template.md) for final document structure.

When all 3 phases are confirmed, generate a single `.md` file with the complete specification, save to `/mnt/user-data/outputs/`, and present it to the user.
