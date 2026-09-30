# Feature Workflow

How features are added to Debate AI. This document is the source of truth for
the process. It is written to be followed by someone (or a Claude session)
with no memory of how it was agreed.

**The process is the backbone. The rigor is tailored per feature.** Every
feature goes through the same stages in the same order. What changes is how
many documents and approval gates it takes to get there.

```
  Story  ------>  Design  ------>  Delivery plan  ------>  Delivery
  (what, why)     (how)            (subtasks, checks)       (code + tests + docs)
     |               |                   |
   gate 1          gate 2              gate 3            done = Definition of Done
```

Simple features pass all three gates at once, in one document. Complex
features pass them one at a time, in three documents.

## 1. Where things live

| Location | Holds |
|---|---|
| `_docs/prd.md` | Product requirements, **as currently delivered**. Updated as part of delivery (section 6). |
| `_docs/design/01` to `05` | The original agentic system design (stages, configurations, contracts, control, framework). Reference for later designs. |
| `_docs/agentic-systems-and-workflows.md` | The general design process and checklist that feature designs draw on. |
| `features/NNN-slug/` | One folder per feature: its story, design and delivery plan. This is the history and the record of decisions. |
| `features/_templates/` | Templates for the documents below. Copy them, do not edit them in place. |

## 2. The tiers

The **user decides the tier by hand for every feature.** The agent proposes a
tier with its reasons at the start; the user approves or changes it. The
approved tier is recorded in the document header.

| | Simple | Complex |
|---|---|---|
| Documents | One: `feature.md` (story, design, delivery plan as three sections) | Three: `01-story.md`, `02-design.md`, `03-delivery-plan.md` |
| Gates | One approval covers all three sections | One approval per document, in order |
| Typical shape | Small, contained, one PR, no change to existing contracts | Touches contracts or requirements, adds a stage or agent configuration, has real design choices, or needs several PRs |

**Guidance for proposing a tier** (a guide, not a rule; the user decides). The
feature probably deserves *complex* if it does any of these:

- adds a stage or a reasoning-core configuration (see `_docs/design/`)
- changes an existing requirement, capability contract or control rule
- has more than one credible design, or a risk worth writing down
- needs more than one PR or more than about three subtasks

Otherwise propose *simple*. When unsure, propose *complex*: skipping rigor
costs more than writing one extra document.

## 3. Folder layout and naming

```
features/
  README.md
  _templates/
  001-batch-and-bias/
    01-story.md
    02-design.md
    03-delivery-plan.md
  002-some-small-thing/
    feature.md
```

- Folders are numbered in creation order: `NNN-kebab-slug`. Never renumber.
- Feature branch: `feature/NNN-slug`.
- The feature index in section 9 lists every feature and its state.

## 4. Documents

Every document starts with a status header (section 5). The templates in
`_templates/` have the exact headings. In short:

**Story** (`01-story.md`, or section 1 of `feature.md`)
- Who wants this, what they get, and why (the user story).
- Acceptance criteria: observable, testable statements.
- Out of scope: what this feature will not do.
- Requirement changes: the FR, NFR and objective entries this adds or
  changes, **written as they will read in the PRD** but not yet added to it.
- Open questions for the user.

**Design** (`02-design.md`, or section 2)
- The approach and why, and the alternatives considered.
- Impact on existing contracts, requirements and design documents.
- For features touching the agent system: which steps of
  `_docs/agentic-systems-and-workflows.md` apply (stages, configurations,
  capabilities, control relationships, framework mapping) and the checklist
  items that matter.
- Risks, and how each will be checked.
- Test approach.

**Delivery plan** (`03-delivery-plan.md`, or section 3)
- Subtasks, each small enough to finish and check, with its own acceptance check
  and the test that proves it.
- Order and dependencies.
- Branch and PR plan (one PR for the feature or one per subtask).
- **Documentation to update** as its own list (section 6).
- Progress: a checkbox per subtask, ticked as each merges.

## 5. Gates and statuses

Every feature document has this header:

```
Status: Draft | Approved | Superseded
Tier: simple | complex        (tier approved by <name> on <date>)
Approved: <name>, <date>      (or "pending")
```

Rules:

1. **Approval is explicit.** It is a message from the user saying so. Silence,
   a question, or "continue" is not approval of a gate. The agent records the
   name and date in the header and commits it.
2. **No skipping ahead.** Design work does not start until the story is
   approved. Code does not start until the design and the delivery plan are
   approved. For a simple feature that means the single approval.
3. **Changing an approved document reopens it.** If implementation shows that
   the story, design or plan is wrong, stop, edit the document with a short
   dated note in its change log, set its status back to Draft, and ask for
   approval again. Later documents that depend on it are reopened too.
4. **Small fixes** (typos, links, wording that changes no meaning) do not
   reopen a document.
5. **Documents are committed before the code they describe**, on the feature
   branch, so the history shows the order.

## 6. Definition of Done

A feature is delivered when **all** of these are true. Documentation is part
of delivery, not a follow-up.

- [ ] Every acceptance criterion in the story is met and has a test or a recorded manual check.
- [ ] All tests pass.
- [ ] **`_docs/prd.md` is updated** to describe the feature as delivered (new
      or changed FR, NFR, objectives, open questions, success metrics).
      The PRD must not describe undelivered features as current.
- [ ] Any design document the feature changed is updated (`_docs/design/`, and
      the README if usage changed).
- [ ] The delivery plan's checkboxes are all ticked, and any deviation is noted
      in the plan.
- [ ] The feature index (section 9) shows the feature as Delivered.
- [ ] The PRD and doc updates are in the **same PR** as the code, so `main`
      never has code and docs that disagree.

## 7. Git and PR flow

- One branch per feature: `feature/NNN-slug`. Documents are the first commits.
- Push, open a PR and merge **only when the user asks.** Merge with
  `gh pr merge --merge --delete-branch`, then pull `main`.
- Commit messages end with the attribution line given by the session.
- Never commit `.env`. The repo is public.

## 8. Working across sessions

A new session should be able to continue any feature from the files alone:

1. Read this file, then `features/<the feature>/` in order.
2. The status headers say which gates are passed. The delivery plan's
   checkboxes say what is built.
3. Open questions and the change log say what is still undecided.
4. If the state is unclear, ask the user rather than guess.

The root `CLAUDE.md` points to this file, so Claude Code loads the pointer at
the start of a session.

## 9. Feature index

| # | Feature | Tier | State |
|---|---|---|---|
| 001 | [Batch and bias summary](001-batch-and-bias/) | complex | Story approved; design in review (gate 2) |
| 002 | Swapped-order judge check (separates debater bias from ordering effects; adds a second judge call and a step 2 change) | not set | Backlog (no folder until work starts) |

States: Backlog, Proposed, Story approved, Design approved, Planned (all gates passed), In delivery, Delivered, Dropped.

**Work that predates this process** (not migrated unless noted): the core app
(PRD, `_docs/design/01` to `05`, orchestrator, CLI) and the run report (PRD
O7 and FR-7, design 04 section 2.5a). The batch and bias summary (PRD O8 and
FR-8, `_docs/design/06`) was documented but not built. It was migrated into
`001-batch-and-bias/` and its PRD entries wait there until delivery. The
drafts remain on the unmerged branch `docs/batch-and-bias` for reference only.
