# 001 — Batch and Bias Summary: Design

```
Status: Draft
Approved: pending
Story: 01-story.md (must be Approved before this is worked on)
```

_Migrated from `_docs/design/06-batch-and-bias-check.md` on branch
`docs/batch-and-bias`, reshaped to the design template._

## Approach

A **batch** is a driver above the run. It calls the existing single-debate run
once per motion and summarizes the results. It is not a new stage, a new
reasoning-core configuration, or a new capability the model can request. It is
a second outer loop, sequencing runs the way the run loop sequences stages.
Everything inside a run (isolation, validation, limits, the FR-7 report) is
unchanged.

```
  motions file --> [ Batch driver ] --> run(motion 1) --> RunResult
                        |          --> run(motion 2) --> RunResult
                        |          --> ...
                        v
                  summary.md  (rates, pairs, totals)
```

### Input file

One line per entry. Blank lines and lines starting with `#` are ignored.

| Line | Meaning |
|---|---|
| `Motion text` | A single motion. |
| `Motion A \| Motion B` | A **pair**: B is the opposite of A. Both run, and the pair is analyzed together. |

- A line with more than one `|` is malformed. The batch is rejected before any model call, and the message names the line number.
- Motions are trimmed. Duplicates are not removed: a repeat is a legitimate way to measure noise.

### Control relationships (step 4 vocabulary)

| Relationship | Decision |
|---|---|
| **Memory** | The driver holds the list of `RunResult`s for the batch. Nothing passes between debates: each run starts with only its own motion. Persisted: `summary.md` and each run's own folder. |
| **Validation** | The input file is checked before the first call. No validation of debate content beyond what each run already does. |
| **Termination** | **Success:** every motion was attempted. **Stopped early:** the token budget was exceeded, and unstarted motions are listed as skipped. **Failed:** the input was invalid, or the summary could not be written. A run that ends exhausted or failed does **not** end the batch. |
| **Human interface** | None. The batch reports at the end. The user can interrupt it, and results already written stay on disk. |

**Budget rule.** Checked **between** runs against tokens spent so far. It
cannot stop a run in progress, so a batch can exceed the budget by at most one
debate.

**Run limits are unchanged.** Each debate keeps its 5-minute limit and 9-call cap.

**Sequential only.** The budget is checked between runs, and the usage
attribution rule (design 04, 2.5a) relies on one run at a time per model instance.

### Output

```
output/
  batch-<batch_id>/
    summary.md
    <run_id>/propose.md, oppose.md, decide.md   (one folder per debate)
```

- `batch_id`: timestamp, same rule as `run_id`.
- Each debate uses the existing `output_dir` argument, set to the batch folder, so no run code changes.
- **`write_summary`.** The step 3 `write_artifact` contract takes a fixed stage name, and a summary is not a stage. Rather than loosen that contract, add a sibling capability with the same rules:

| Field | Contract |
|---|---|
| Name | `write_summary` |
| Arguments | `output_dir`, `batch_id` (same safety rules as `run_id`), `content` (non-empty Markdown) |
| Result | Path written, `output/batch-<batch_id>/summary.md`, and bytes |
| Failure modes | `InvalidArgument`, `WriteFailed`, as in step 3 |
| Retry safety | Idempotent, atomic replace |
| Approval | None |

### Summary contents

- **Per-motion table:** motion, outcome, winner, attempts, tokens, run folder. Unfinished runs show their outcome and no winner. Skipped motions show `skipped`.
- **For-win rate:** `for wins / completed runs`. Completed means the run reached a verdict. Exhausted and failed runs are excluded and counted separately.
- **Pair analysis.** A pair is only analyzed when both debates completed.

| Result on A | Result on B | Reading |
|---|---|---|
| for | against | Consistent: sided with A's position both times. |
| against | for | Consistent: sided with B's position both times. |
| for | for | Not consistent: sided with the proposition both times. |
| against | against | Not consistent: sided with the opposition both times. |

  The summary reports `consistent pairs / analyzed pairs` and lists the not-consistent pairs.
- **The honest limit.** In every debate the judge receives the proposition argument first. The summary says, in a fixed sentence, that a skew cannot be attributed to debaters or to that order, and reports rates, not a verdict of "biased".
- **Small samples.** Fewer than 10 completed runs adds a "too few runs to conclude anything" line.
- **Totals:** attempts and tokens summed across runs.

### Interface

```
debate batch motions.txt [--budget 100000] [--output-dir output]
```

Exit code: 0 if every motion completed, 1 if any run was exhausted or skipped for budget, 2 if the input was invalid or the summary could not be written. `debate "<motion>"` is unchanged.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Two input files (one per position) instead of `A \| B` lines | Pairing by position in two files breaks silently if the files drift. One line keeps a pair together. Open for the user (story, question 1). |
| Also run the judge with the order swapped | Separates debater bias from ordering effects, but needs a second judge call, which is a new reasoning-core configuration and a step 2 change. Deferred (story, out of scope). |
| Run debates in parallel | Faster, but breaks the between-runs budget check and the usage attribution rule. |
| Loosen `write_artifact` to accept any file name | Weakens the derived-path safety rule of step 3. A sibling capability keeps both contracts narrow. |
| Compute a significance test | Adds statistics the sample sizes cannot support. Rates plus a small-sample warning are more honest. |

## Impact on existing work
- **Requirements and PRD:** adds O8, FR-8, Q8, Q9 and one metric note, at delivery (story, requirement changes).
- **Capability contracts (design 03):** unchanged. `write_summary` is a new sibling, documented here and added to design 03 at delivery.
- **Control relationships (design 04):** unchanged. The batch driver is a new outer loop above the run.
- **Framework mapping (design 05):** unchanged. CrewAI is used only inside each run, as today.
- **Code:** `run_debate` is called as is. No change to `run.py`, `validation.py` or `artifacts.py` apart from adding `write_summary`.

## Agent system design
Not applicable: no change to stages, configurations, or the model calls
inside a run. No new pre-build test against CrewAI is needed, because nothing
new depends on framework behavior.

## Risks
| Risk | How it is checked |
|---|---|
| A for-win skew is read as debater bias when it is an ordering effect | The summary's fixed limit sentence (FR-8.6), and a test that it appears |
| The budget is overshot by one debate | Documented. A test shows the third motion is skipped after the budget is passed |
| A flaky run distorts the win rate | Exhausted and failed runs are excluded from the rate and counted separately. Tested |
| A malformed file wastes money by failing halfway | The whole file is parsed and validated before the first model call. Tested |
| Pair logic misread (which result counts as consistent) | The four-row table is the specification, and each row has a test |

## Test approach
All with the fake model; no network, no API key.

| Case | Expected |
|---|---|
| Parse: blank lines, comments, pair lines, a line with two `\|` | Entries as specified. The malformed line is rejected with its line number and no model call. |
| Empty file | Rejected, no model call, no folder. |
| Three motions, all succeed | Three run folders under the batch folder, and a summary with the correct for-win rate and totals. |
| One run exhausted | Listed, excluded from the rate, and the batch continues. |
| Budget exceeded after the second run | The third motion is listed as skipped, and the exit code is 1. |
| Pair results: (for, against), (for, for), (against, against), and one pair with a failed side | Consistent, not consistent, not consistent, and not analyzed. |
| Fewer than 10 completed runs | The "too few runs" line is present. |
| `write_summary` | Rejects unsafe `batch_id` and empty content, is idempotent, and cleans up on failure. |
| Single-motion command | Behaves as before. |

## Open decisions for review
1. `A | B` pair syntax versus two files (story, question 1).
2. Default budget of 100,000 tokens (story, question 2).
3. Whether the swapped-order judge check becomes its own later feature (story, question 3).

## Change log
- 2026-09-30: migrated from `_docs/design/06` on the pre-workflow branch and reshaped to the template. Content unchanged. Reset to Draft.
