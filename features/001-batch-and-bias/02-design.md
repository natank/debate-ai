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

- A line is **malformed** if it has more than one `|`, or a `|` with an empty side (`A |`, `| B`, or `|` alone). The whole file is rejected before any model call, and the message names the first malformed line number.
- The tool does not check that B really is the opposite of A. A badly written pair gives a meaningless consistency result; writing good pairs is the user's job.
- Motions are trimmed. Duplicates are not removed: a repeat is a legitimate way to measure noise.

### Control relationships (step 4 vocabulary)

| Relationship | Decision |
|---|---|
| **Memory** | The driver holds the list of `RunResult`s for the batch. Nothing passes between debates: each run starts with only its own motion. Persisted: `summary.md` and each run's own folder. |
| **Validation** | The input file is checked before the first call. No validation of debate content beyond what each run already does. |
| **Termination** | **Success:** every motion was attempted. **Stopped early:** the token budget was exceeded, and unstarted motions are listed as skipped. **Failed:** the input was invalid, or the summary could not be written. A run that ends exhausted or failed does **not** end the batch. |
| **Human interface** | No approvals or questions. The batch prints a progress line as each debate finishes (FR-8.8) and a final line at the end. The user can interrupt it, and results already written stay on disk. |

**Budget rule.** Default 20,000 tokens (about 10 debates), overridable with `--budget`. Checked **between** runs against tokens spent so far. It
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
- **The summary is written after every debate, not only at the end.** Each write replaces the file atomically, so a batch that is interrupted (Ctrl-C) or crashes still leaves a valid `summary.md` covering the debates done so far. Its header line reads `in progress (2 of 3 done)` until the batch ends, then `complete`. The cost is one small file write per debate.
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
debate batch motions.txt [--budget 20000] [--output-dir output]
```

The existing `debate "<motion>"` command is unchanged.

**How the command is parsed.** The current CLI takes one positional `motion`, so a naive `debate batch motions.txt` would be read as the motion "batch" plus an unexpected extra argument. The design: if the first argument is exactly `batch`, the command is batch mode and requires a file (`debate batch` alone prints usage and exits 2). Anything else is a single motion, as today. The one thing this rules out is debating the one-word motion "batch", which is not a debatable statement. Alternative considered: a flag, `debate --batch motions.txt`. It has no ambiguity but reads less naturally. _Needs the user's choice at this gate (see Review, R2)._

The examples below are
**mockups** of the intended layout. The numbers are made up.

**Input file** (`motions.txt`):

```
# Pets: a pair, so we can test consistency
Cats make better pets than dogs | Dogs make better pets than cats

# A single motion
Remote work is better than office work
```

**Progress lines** (FR-8.8). One line is printed as each debate finishes:

```
[i/N] <motion, shortened to fit> ..... <winner or outcome>  <tokens> tokens
```

- `i/N` counts entries in the file; a pair counts as two.
- The motion is shortened with `...` so the line fits in 80 columns. The full motion is in the summary.
- The result is `For` or `Against`, or the outcome and the stage that ended it, for example `exhausted (oppose)` or `failed (propose)`.
- Progress lines and the final line go to standard output.
- The reason a batch stopped early, and input errors, go to standard error, following the single-run convention (non-success goes to standard error).

**Complete batch:**

```
$ debate batch motions.txt
[1/3] Cats make better pets than dogs ............ For      2,010 tokens
[2/3] Dogs make better pets than cats ............ Against  1,985 tokens
[3/3] Remote work is better than office work ..... For      2,040 tokens

Batch 20260930-101500: 3 of 3 completed, 9 attempts, 6,035 tokens
Summary: output/batch-20260930-101500/summary.md
```

**A run that fails, and the batch continues:**

```
[1/3] Cats make better pets than dogs ............ For      2,010 tokens
[2/3] Dogs make better pets than cats ............ exhausted (oppose)  1,420 tokens
[3/3] Remote work is better than office work ..... For      2,040 tokens

Batch 20260930-101500: 2 of 3 completed, 1 exhausted, 8 attempts, 5,470 tokens
Summary: output/batch-20260930-101500/summary.md                      (exit code 1)
```

**Budget passed** (`--budget 3000`). The batch stops before starting a debate once
tokens spent have reached the budget. The check is between runs, so it can
overshoot by one debate: here the second debate started at 2,010 (under 3,000)
and ended at 3,995:

```
[1/3] Cats make better pets than dogs ............ For      2,010 tokens
[2/3] Dogs make better pets than cats ............ Against  1,985 tokens
Stopped: 3,995 tokens used, over the 3,000 budget. Skipped 1 motion.   (stderr)
Batch 20260930-101500: 2 of 3 completed, 1 skipped, 6 attempts, 3,995 tokens
Summary: output/batch-20260930-101500/summary.md                      (exit code 1)
```

**Bad file:** parsed and validated before any model call:

```
$ debate batch bad.txt
Line 3: a pair uses one "|" (found 2). No debates were run.           (exit code 2, stderr)
```

**Exit codes:** 0 if every motion completed. 1 if any run was exhausted or
failed, or any motion was skipped for budget. 2 if the input was invalid or the
summary could not be written.

**`summary.md`:**

```markdown
# Batch summary
Batch 20260930-101500 · 3 motions · 3 completed · 6,035 tokens · 9 attempts

| # | Motion                                 | Outcome | Winner  | Attempts | Tokens | Run folder |
|---|----------------------------------------|---------|---------|----------|--------|------------|
| 1 | Cats make better pets than dogs        | success | For     | 3        | 2,010  | 20260930-…-cats-… |
| 2 | Dogs make better pets than cats        | success | Against | 3        | 1,985  | 20260930-…-dogs-… |
| 3 | Remote work is better than office work | success | For     | 3        | 2,040  | 20260930-…-remote-… |

## For-win rate
2 of 3 completed runs (67%). Too few runs to conclude anything.

## Pairs
| Pair        | Result on A | Result on B | Reading                                  |
|-------------|-------------|-------------|------------------------------------------|
| Cats / Dogs | For         | Against     | Consistent: sided with "cats" both times |

Consistent pairs: 1 of 1.

## Read this carefully
A skew toward "for" cannot be told apart from an ordering effect: the judge
always sees the proposition first. These are rates, not a finding of bias.
```

Each debate's `propose.md`, `oppose.md` and `decide.md` sit in a subfolder next
to `summary.md`.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Two input files (one per position) instead of `A \| B` lines | Pairing by position in two files breaks silently if the files drift. One line keeps a pair together. Decided by the user on 2026-09-30: one line with `|`. |
| Also run the judge with the order swapped | Separates debater bias from ordering effects, but needs a second judge call, which is a new reasoning-core configuration and a step 2 change. Deferred (story, out of scope). |
| Run debates in parallel | Faster, but breaks the between-runs budget check and the usage attribution rule. |
| Loosen `write_artifact` to accept any file name | Weakens the derived-path safety rule of step 3. A sibling capability keeps both contracts narrow. |
| Compute a significance test | Adds statistics the sample sizes cannot support. Rates plus a small-sample warning are more honest. |

## Impact on existing work
- **Requirements and PRD:** adds O8, FR-8, Q8, Q9 and one metric note, at delivery (story, requirement changes).
- **Capability contracts (design 03):** unchanged. `write_summary` is a new sibling, documented here and added to design 03 at delivery.
- **Control relationships (design 04):** unchanged. The batch driver is a new outer loop above the run.
- **Framework mapping (design 05):** unchanged. CrewAI is used only inside each run, as today.
- **Code:** `run_debate` is called with its existing arguments. Two small changes: (1) `run.py` makes each run's folder unique (see Review, R1), and (2) `artifacts.py` gains `write_summary`. `cli.py` gains batch mode. `validation.py` is unchanged.

## Agent system design
Not applicable: no change to stages, configurations, or the model calls
inside a run. No new pre-build test against CrewAI is needed, because nothing
new depends on framework behavior.

## Risks
| Risk | How it is checked |
|---|---|
| Two debates get the same run folder (same second, and same first 40 characters of the motion) and the second overwrites the first | Run folders become unique (Review, R1). Tested with two identical motions run in the same second |
| A run ended by the wall-clock limit leaves a call in flight whose tokens are not counted, so the budget can be undercounted | Known limit from the run report (design 04, 2.5a). Accepted: the overshoot is bounded by one call |
| The default budget stops a batch at about the 10-run "too few runs" threshold | Documented in the summary line itself. A user who wants a bigger sample passes `--budget`. Tested |
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
| Progress lines | One line per finished debate, in file order, with `i/N`, a shortened motion, the winner or outcome, and tokens. A long motion is shortened to fit 80 columns. A final line gives the counts and the summary path. |
| Streams | Progress and final lines on standard output. The early-stop reason and input errors on standard error. |
| Summary limit sentence | The fixed "cannot be told apart from an ordering effect" sentence is present in every summary. |
| Malformed pair sides | `A \|`, `\| B` and `\|` alone are each rejected with their line number and no model call. |
| Unique run folders | Two identical motions run in the same second produce two different run folders, and neither overwrites the other. |
| Interrupted batch | If the second debate raises `KeyboardInterrupt`, a valid `summary.md` exists covering the first debate and reads `in progress`. |
| Batch command parsing | `debate batch motions.txt` is batch mode; `debate batch` alone exits 2 with usage; `debate "some motion"` is a single run. |
| Single-motion command | Behaves as before. |

## Open decisions for review
None. The user's answers on 2026-09-30 settled all three:
1. Pair syntax: `A | B` on one line.
2. Default budget: 20,000 tokens.
3. The swapped-order judge check is a later feature (backlog 002), not part of this design.

## Review (2026-09-30)

The design was checked against the approved story and against the code it
will call (`run.py`, `cli.py`, `artifacts.py`).

**What holds up**
- Every acceptance criterion in the story maps to a design element and a test.
- Each debate builds its own model instances and its own usage meter, so token totals do not leak between debates. The batch can simply add up each result's total.
- An abandoned run (wall-clock limit) is cancelled after its in-flight call and writes nothing further, so it cannot corrupt the next debate.
- `RunResult` already carries what the summary needs: motion, outcome, stage, verdict winner, stats, artifacts.
- The capability contracts in design 03 and the control rules in design 04 are unaffected. `write_summary` is a new sibling, not a loosening.

**Findings, and what was done**

| # | Severity | Finding | Disposition |
|---|---|---|---|
| R1 | Medium | `make_run_id` is deterministic to the second and truncates the motion to 40 characters. Two debates with the same first 40 characters started in the same second would share a folder, and the second would overwrite the first. The design encourages repeated motions, and a fast failure could finish within a second. Silent data loss is unacceptable in a measurement tool. | **Fixed in this design:** `run.py` appends `-2`, `-3`, ... when the run folder already exists. Small change, with a test. |
| R2 | Medium | `debate batch FILE` conflicts with the CLI's single positional `motion`. | **Design chosen, needs the user's choice:** subcommand form, detected by the first argument being `batch`. Alternative: a `--batch FILE` flag. |
| R3 | Medium | `summary.md` was written only at the end, so an interrupted batch left nothing, contradicting "results already written stay on disk". | **Fixed:** the summary is rewritten atomically after every debate. |
| R4 | Low | Pair lines with an empty side (`A \|`) were not treated as malformed, and would have run an empty motion. | **Fixed:** malformed rule extended, with tests. |
| R5 | Low | The fixed "ordering effect" sentence had no test row. | **Fixed:** test row added. |
| R6 | Low | The budget can be undercounted after a timed-out run. | **Accepted and recorded** as a known limit. |
| R7 | Info | The tool cannot verify that the two motions in a pair are true opposites. | **Recorded** as a stated assumption. |

**Still true after the fixes:** no new agent-system design and no new CrewAI
behavior is depended on, so no pre-build test against CrewAI is needed.

## Change log
- 2026-09-30: design review. Fixes R1, R3, R4, R5 applied; R2 (CLI form) awaits the user's choice; R6, R7 recorded. Still Draft, pending gate 2.
- 2026-09-30: default budget set to 20,000 tokens, and the pair syntax `A | B` confirmed, per the user's answers to the story's open questions. Still Draft.
- 2026-09-30: replaced the interface section with progress lines (FR-8.8) and mockups of every case. Still Draft, so no gate was reopened.
- 2026-09-30: migrated from `_docs/design/06` on the pre-workflow branch and reshaped to the template. Content unchanged. Reset to Draft.
