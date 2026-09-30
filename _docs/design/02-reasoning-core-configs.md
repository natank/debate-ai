# Design Step 2 — Reasoning-Core Configurations

_Status: Draft · 2026-09-29_
_Input: `_docs/design/01-stages-and-sequence.md`. Sources: `_docs/config/agents.yaml`, `_docs/prd.md`._
_Process: `_docs/agentic-systems-and-workflows.md`, Design process, Step 2. No framework is assumed._

## 1. Configurations

Two configurations. Each is the format contract for one kind of call to the
reasoning core. (The existing `agents.yaml` names them `debater` and `judge`.)

| Field | Debater | Judge |
|---|---|---|
| **Role** | An experienced debater who gives concise, convincing arguments. | A fair judge who weighs arguments on their merits and keeps their own views out of it. |
| **Instructions: must** | Argue the assigned **side** of the motion as persuasively as possible. Be clear and concise. Make the case on its own merits. | Compare the two arguments on the merits only. Name exactly one winner. Give reasons that refer to specific points in the arguments. |
| **Instructions: must never** | Argue the other side. Refer to or guess at what the other debater says. State facts it cannot support as certain. | Use its own opinion of the motion. Declare a tie or refuse to choose. Introduce arguments neither side made. |
| **Allowed tools** | None | None |
| **Output shape** | Plain text argument, about 200–300 words (PRD Q5). | Structured verdict: `winner` (`for` or `against`) and `reasoning` (free text that cites the arguments). |
| **Per-call parameters** | `motion`, `side` (`for` or `against`) | `motion`, `argument_for`, `argument_against` |

**Side is a parameter, not a role.** The existing `debater` agent says "either
in favor of or against" and leaves the side to the task text. In this design
the side is an explicit per-call parameter, so one configuration serves both
stages and the two sides cannot drift apart in wording (NFR-1).

## 2. Allocation

```
  Stages                     Configurations
  +-------------+
  | S1 Propose  |---------> [ Debater ]   side = for
  +-------------+
  | S2 Oppose   |---------> [ Debater ]   side = against   (same configuration, reused)
  +-------------+
  | S3 Decide   |---------> [ Judge   ]
  +-------------+
```

One Debater configuration serves S1 and S2 because their role and allowed
tools coincide. Only the `side` parameter differs.

## 3. Rule checks

**Least capability.** Neither configuration exposes a tool. Neither stage
needs the reasoning core to act on the world: it reads its inputs and returns
text.

**Coverage, and the "write artifact" need from step 1.** Step 1 listed
"write artifact" as a capability every stage needs. This design does not give
it to the reasoning core as a tool. The control loop writes each stage's
output file after validation. Reasons:

- The write is fixed and unconditional, so the reasoning core never has to
  decide whether or when to do it.
- Keeping it out of the tool list means a model cannot write to, or choose,
  a file path.
- Coverage is still met: the capability exists, and it is exercised by the
  control loop, not requested by the reasoning core.

Step 3 must still give this capability a contract (arguments, failure modes,
retry safety). Only the caller changes.

**Isolation of inputs (NFR-1).** The Debater's per-call parameters are only
`motion` and `side`. The opposing argument is never among them, so fairness
is enforced by what each call is given, not by an instruction to ignore it.

## 4. Changes to the existing `agents.yaml`

These are recorded here for the framework mapping in step 5. Nothing has been
edited.

| Existing | Issue | Design decision |
|---|---|---|
| `debater.goal`: "either in favor of or against the motion" | Side is left to the task text, so it is implicit. | Side is an explicit parameter. |
| `debater.backstory`: "debator" | Typo. | Fix on mapping. |
| `judge`: no output shape | The verdict cannot be validated automatically (PRD Q3). | Structured `winner` and `reasoning`. |
| `judge.goal`: "based purely on the arguments presented" | Correct intent, but the judge has no rule against ties or against adding its own arguments. | Added to the "must never" list. |
| `llm: openai/gpt-5.4-mini` on both | Model is a framework and deployment detail. | Not part of the configuration at this step. Decide in step 5. |

## 5. Output of step 2

- Configuration table (section 1).
- Stage-to-configuration allocation (section 2).

## 6. Carried forward

| To step | Item |
|---|---|
| 3 | Contract for "write artifact": arguments, result, failure modes, retry safety, approval (none expected). |
| 4 | Validation: the verdict has a valid `winner` and reasoning that cites both arguments; each argument is on the right side and within the length range. Behavior on rejection. |
| 4 | The Judge's inputs come from memory. Memory must expose S1 and S2 outputs to S3 only, and never S1's output to S2 (see step 1, memory scoping). |
| 5 | Which model each configuration uses. |

## 7. Checklist (step 2 items)

- [x] Every stage is allocated to exactly one reasoning-core configuration.
- [x] Every capability a stage needs appears on its configuration, or its owner is recorded (write artifact: the control loop).
- [x] No configuration has a capability none of its stages need.

## 8. Update (feature 002)

No new configuration. The **Judge** now serves S3 and S4 (design 01, section 7).
The per-call parameters are the same (`motion`, `argument_for`,
`argument_against`); for S4 the arguments are presented in the opposite order.
The task text is the existing `decide` task, so the two judge prompts differ
only in that order (checked by a test). Least capability still holds: no tools.
