# UX process

UX is a first-class role here, not a step that frontend engineering improvises around.

```
PRODUCT REQUIREMENT → UX MOCKUP → INTERACTION SPEC → FRONTEND STORY READY
                                                   → IMPLEMENTATION (TDD) → TESTS
```

## The rule

**A frontend story is NOT READY until its UX specification is committed.**

A story that says "build the vehicle page" is not a story. It is a request for the engineer to
invent product decisions at implementation time, which is how interfaces end up with no empty
state, no error state, and a loading spinner that covers the whole screen.

### Enforcement

The GitHub Projects board has a required **`UX Ref`** field on every story with Area = `frontend`.
A story cannot enter the `Ready` column without it pointing at a committed file in this directory.
A missing `UX Ref` is a blocker, not a formality — implementation does not begin.

### Ready checklist (frontend)

- [ ] Product requirement is clear and testable
- [ ] UX specification committed at `docs/ux/<story-id>-<name>.md`
- [ ] All seven states specified (below)
- [ ] API contract known — endpoint, request, response, error shapes
- [ ] Acceptance criteria unambiguous
- [ ] Dependencies satisfied

## Every specification covers seven states

Interfaces are judged on their worst state, not their best. All seven are required:

| State            | The question it answers                                               |
| ---------------- | --------------------------------------------------------------------- |
| **Default**      | What does a normal user with normal data see?                         |
| **Loading**      | What is on screen while we wait? (Skeletons, not full-page spinners.) |
| **Empty**        | First run — no vehicles, no history. What is the call to action?      |
| **Error**        | The request failed. What happened, and what can the user do about it? |
| **Validation**   | Bad input. Which field, what is wrong, how to fix it?                 |
| **Success**      | It worked. How does the user know, and where are they now?            |
| **Confirmation** | Destructive or irreversible. How do we ask, and how do we allow undo? |

Plus, in every spec:

- **Responsive** behaviour at **375px** (primary — people use this standing next to the car),
  768px, and 1280px
- **Keyboard** focus order, focus trapping in dialogs, and visible focus rings
- **Accessibility** — ARIA roles, labels, live-region announcements, WCAG 2.1 AA contrast
- **What happens after the action** — navigation, optimistic update, or refetch

## Mockups

Low-fidelity HTML + Tailwind pages in [`mockups/`](mockups/), openable in a browser.

**No Figma.** A design tool outside the repository becomes a second source of truth that silently
drifts from the code, and drift is discovered by users. Mockups live beside the code, are reviewed
in the same PR, and use the same Tailwind tokens the implementation uses.

## Template

Copy [`_template.md`](_template.md) to `docs/ux/<story-id>-<name>.md`.
