# Documentation

## Start here

**Board:** [Car Maintenance Companion](https://github.com/users/akashungarala/projects/1) — the live status of every slice and epic.
The markdown backlog below is the detail; the board is the state.

| Document                                | What it answers                                     |
| --------------------------------------- | --------------------------------------------------- |
| [Architecture Decision Records](adr/)   | Why is anything the way it is?                      |
| [Phase 0 backlog](backlog/phase-0.md)   | What is being built right now, and when is it done? |
| [UX process](ux/README.md)              | How does a design become a frontend story?          |
| [Testing & TDD](engineering/testing.md) | What counts as tested?                              |

## Written as it is built

These are written in the slice that makes them true, not in advance — documentation that describes
infrastructure which does not exist yet is fiction.

| Document                       | Written in                                     |
| ------------------------------ | ---------------------------------------------- |
| `engineering/architecture.md`  | F5                                             |
| `engineering/environments.md`  | F4                                             |
| `engineering/cicd.md`          | F5                                             |
| `engineering/database.md`      | F6                                             |
| `engineering/observability.md` | F8                                             |
| `engineering/security.md`      | F9                                             |
| `runbook/`                     | F6 (restore), F9 (rollback, incident response) |
| `product/`                     | Phase 1, alongside E1                          |

## Conventions

- **Decisions** go in an ADR, not in prose scattered across documents.
- **Runbooks** are written for a tired operator at 2am: numbered commands, expected output,
  and what to do when the output differs.
- If a document exists only because a checklist demanded it, delete it.
