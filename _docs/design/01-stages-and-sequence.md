# Design Step 1 — Stages and Sequence

_Status: Draft · 2026-09-29_
_Input: `_docs/prd.md` (requirements). Process: `_docs/agentic-systems-and-workflows.md`, Design process, Step 1._
_Uses only the vocabulary of steps 1–4. No framework is assumed._

## 1. Stage list

The overall goal is to turn a motion into a reasoned verdict. That needs three
distinct pieces of reasoning, each with one responsibility and one output.

| Field | S1 Propose | S2 Oppose | S3 Decide |
|---|---|---|---|
| **Responsibility** | Produce the argument in favor of the motion. | Produce the argument against the motion. | Decide which side is more convincing, and why. |
| **Inputs** | The motion. | The motion. | The motion, the S1 output, the S2 output. |
| **Output** | Proposition argument (`propose.md`). | Opposition argument (`oppose.md`). | Verdict (`decide.md`). |
| **Capabilities needed** | Write artifact. | Write artifact. | Write artifact. |
| **Requirement source** | FR-2, O2 | FR-3, O3 | FR-4, O4 |

**Notes on the stage boundaries**

- **Why three stages, not two.** Propose and oppose each have one output. A
  single "argue both sides" stage would need the word "and" to describe its
  output, so it is two stages (checklist: one responsibility, one output).
- **Why the verdict is its own stage.** It is the only stage that reads other
  stages' outputs, and the only one that must stay impartial about the motion
  (FR-4.4).
- **Not stages.** Receiving the motion (FR-1) and writing it into memory is not
  reasoning work; it is the outer control loop's job, recorded in step 4.
  Files are written by a capability, not by a separate stage.
- **Capability level.** "Write artifact" is named here only as a need. Its
  contract (arguments, failure modes, retry safety) belongs to step 3.

## 2. Dependencies

Read from each stage's Inputs row:

```
  motion  --> S1 Propose
  motion  --> S2 Oppose
  S1, S2  --> S3 Decide
```

- S1 and S2 do not read each other's output. Neither depends on the other.
- S3 depends on both.

## 3. Sequence shape

The simplest shape that satisfies these dependencies is **parallel, then join**.
A linear order (S1 → S2 → S3) would also satisfy them, but it would add a
dependency that is not a requirement: S2 running after S1 makes it a
candidate for reading S1's output, which breaks NFR-1 (fairness).

```
                +--> S1 Propose --+
   motion ------+                 +--> S3 Decide --> verdict
                +--> S2 Oppose  --+
```

- **Fork:** after the motion is in memory, S1 and S2 may start at once.
- **Join:** S3 starts only when both S1 and S2 have produced their outputs
  (FR-5.1).
- **No loop-back in v1.** There is no rebuttal round (out of scope in the PRD).
  Retry on a rejected output is a step 4 concern, inside a stage, not part of
  this sequence.

### Decision: parallel vs. linear

| | Parallel, then join (chosen) | Linear S1 → S2 → S3 |
|---|---|---|
| Satisfies the dependencies | Yes | Yes |
| Fairness (NFR-1) | Both sides argue blind to each other | Side 2 could read side 1 |
| Complexity | Needs a join before S3 | Simplest to run and test |
| Wall-clock time | Two calls overlap | Sequential |

Parallel is chosen because it removes a dependency the requirements do not
want. If parallel execution proves costly in step 5, a linear order that
**withholds** S1's output from S2 is an equivalent fallback; the stages and
their inputs stay the same.

## 4. Output of step 1

- Stage list: S1 Propose, S2 Oppose, S3 Decide (table in section 1).
- Sequence: fork after the motion, join before S3 (section 3).

## 5. Carried forward

| To step | Item |
|---|---|
| 2 | S1 and S2 look like one reasoning-core configuration used twice (the PRD's `debater`); S3 is a second (`judge`). Confirm against the role, instructions, allowed tools and output shape. |
| 3 | Define the "write artifact" capability contract. |
| 4 | Where the motion enters memory and who writes it (outer loop). Validation of each output, e.g. the verdict names exactly one side. Retry, cost and time limits. Behavior when S1 or S2 fails and S3 cannot run (FR-5.2). |
| 4 | Whether any human review follows S3. The PRD does not require one in v1. |
| PRD | Q1 (opposition must not see the proposition) is resolved here as parallel, and Q3 (structured verdict) is picked up in step 4. |

## 6. Checklist (step 1 items)

- [x] Every stage has exactly one responsibility and one output.
- [x] The sequence is the simplest shape the requirements allow.
- [ ] Every stage is allocated to one configuration (step 2).
