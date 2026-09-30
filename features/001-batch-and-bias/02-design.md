# 001 — Batch Validation Tool (bias summary): Design

```
Status: Draft          (reworked 2026-09-30 for the independence rule; needs approval)
Approved: pending
Story: 01-story.md (must be Approved before this is approved)
```

_Migrated from `_docs/design/06-batch-and-bias-check.md` on branch
`docs/batch-and-bias`, then reworked after the user redefined the feature as a
modular validation tool that is independent of the single debate._

## Approach

The tool is a **separate package** that calls the single debate as a library,
runs it once per motion, and summarizes the results. It is not a stage, a
reasoning-core configuration, or a capability, and it is not part of the
product.

### The dependency rule

```
   tools/batch_check/   ------ uses ------>   debate_ai   (public interface only:
   (validation tool)                           run_debate, RunResult, StageStats)
                          <---- never ------
   debate_ai does not know the tool exists.
```

- The arrow goes one way. Nothing under `src/debate_ai/` imports, mentions, or is
  changed by the tool.
- The tool reaches the debate only through the names `debate_ai` exports at its
  top level. It does not import `debate_ai.run`, `debate_ai.artifacts` or any other
  submodule, so the debate's internals can change without breaking the tool.
- The tool ships nowhere: `pyproject.toml` builds only `src/debate_ai`, so the
  tool is not in the built package.
- These three facts are checked by tests (see Test approach), so the
  independence cannot erode silently.

### Modules

Small, single-purpose, and mostly pure, so each can be understood and tested on
its own.

```
tools/
  batch_check/
    __init__.py
    parse.py      text file  ->  list of entries (single or pair)      pure
    analyze.py    run results ->  rows, for-win rate, pair results,     pure
                                  totals
    report.py     analysis   ->  summary.md text, progress line,        pure
                                  final line, stop message
    writer.py     atomic write of summary.md (the tool's own; it does   I/O
                  not reuse the product's artifact code)
    runner.py     the driver: runs entries in order through an          control
                  injected run_one, budget, continue on failure,
                  rewrite summary after every debate
    cli.py        arguments, streams, exit codes; supplies the real     edge
                  run_one (a wrapper around run_debate)
    __main__.py   `python -m tools.batch_check`
```

```
  motions file --parse--> entries --runner--> run_one(motion, folder) --> RunResult
                                     |                                       |
                                     |            analyze(results) <---------+
                                     |                 |
                                     +--- report --> summary.md  (rewritten after every debate)
```

**Injected `run_one`.** The runner takes a function `run_one(motion, output_dir)
-> RunResult` instead of calling `run_debate` itself. The CLI passes the real
one. This keeps the driver testable with no model and no reference to the
debate internals, and it is the one seam between the tool and the debate.

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
| **Memory** | The runner holds the list of `RunResult`s for the batch. Nothing passes between debates: each starts with only its own motion. Persisted: `summary.md` and each debate's own folder. |
| **Validation** | The input file is checked before the first call. No validation of debate content beyond what each run already does. |
| **Termination** | **Success:** every motion was attempted. **Stopped early:** the token budget was reached, and unstarted motions are listed as skipped. **Failed:** the input was invalid, or the summary could not be written. A run that ends exhausted or failed does **not** end the batch. |
| **Human interface** | No approvals or questions. A progress line is printed as each debate finishes (BV-8) and a final line at the end. The user can interrupt it, and the summary already written stays on disk (BV-9). |

**Budget rule.** Default 20,000 tokens (about 10 debates), overridable with
`--budget`. Checked **between** debates against tokens spent so far: the batch
stops before starting a debate once spent tokens have reached the budget. It
cannot stop a debate in progress, so a batch can pass the budget by at most one debate.

**Run limits are the debate's own.** Each debate keeps its 5-minute limit and
9-call cap. The tool neither changes nor duplicates them.

**Sequential only.** The budget is checked between debates, and the usage
attribution rule (design 04, 2.5a) relies on one debate at a time per model instance.

### Output

```
output/
  batch-<batch_id>/
    summary.md
    001/<run_id>/propose.md, oppose.md, decide.md
    002/<run_id>/...
```

- `batch_id`: a timestamp, safe as a folder name.
- **Each debate gets its own numbered subfolder** (`001`, `002`, ...), passed to `run_debate` as its `output_dir`. Two debates can therefore never share a folder, even if the same motion is repeated within the same second, and the debate's run-id code needs no change.
- **The summary is written after every debate**, replacing the file atomically, so an interrupted or crashed batch leaves a valid `summary.md` covering the debates done so far. Its header line reads `in progress (2 of 3 done)` until the batch ends, then `complete`.
- **The tool writes `summary.md` with its own small atomic writer** (a temporary file in the same folder, then a rename over the target), in `writer.py`. It does not reuse or extend the product's `write_artifact`, so the product's capability contract (design 03) is untouched and the tool stays independent.

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
- **Totals:** attempts and tokens summed across debates.

### Interface

```
uv run python -m tools.batch_check motions.txt [--budget 20000] [--output-dir output]
```

The `debate` command is not touched and knows nothing about this tool. The
examples below are **mockups** of the intended layout. The numbers are made up.

**Input file** (`motions.txt`):

```
# Pets: a pair, so we can test consistency
Cats make better pets than dogs | Dogs make better pets than cats

# A single motion
Remote work is better than office work
```

**Progress lines** (BV-8). One line is printed as each debate finishes:

```
[i/N] <motion, shortened to fit> ..... <winner or outcome>  <tokens> tokens
```

- `i/N` counts entries in the file; a pair counts as two.
- The motion is shortened with `...` so the line fits in 80 columns. The full motion is in the summary.
- The result is `For` or `Against`, or the outcome and the stage that ended it, for example `exhausted (oppose)` or `failed (propose)`.
- Progress lines and the final line go to standard output. The final line is a report of a finished batch, so it goes to standard output even when the exit code is 1.
- The reason a batch stopped early, and input errors, go to standard error.

**Complete batch:**

```
$ uv run python -m tools.batch_check motions.txt
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

**Budget reached** (`--budget 3000`). The batch stops before starting a debate once
tokens spent have reached the budget. The check is between debates, so it can
pass the budget by one debate: here the second debate started at 2,010 (under 3,000)
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
$ uv run python -m tools.batch_check bad.txt
Line 3: a pair uses one "|" (found 2). No debates were run.           (exit code 2, stderr)
```

**Exit codes:** 0 if every motion completed. 1 if any run was exhausted or
failed, or any motion was skipped for budget. 2 if the input was invalid or the
summary could not be written.

**`summary.md`:**

```markdown
# Batch summary
Batch 20260930-101500 · complete · 3 motions · 3 completed · 6,035 tokens · 9 attempts

| # | Motion                                 | Outcome | Winner  | Attempts | Tokens | Run folder |
|---|----------------------------------------|---------|---------|----------|--------|------------|
| 1 | Cats make better pets than dogs        | success | For     | 3        | 2,010  | 001/20260930-…-cats-… |
| 2 | Dogs make better pets than cats        | success | Against | 3        | 1,985  | 002/20260930-…-dogs-… |
| 3 | Remote work is better than office work | success | For     | 3        | 2,040  | 003/20260930-…-remote-… |

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

## Alternatives considered

| Alternative | Why not |
|---|---|
| A `debate batch` subcommand in the product CLI | Makes a validation tool part of the user-facing command, couples the CLI to it, and forces an argument-parsing change (a single positional motion vs a subcommand). The user redefined this as not part of the product. |
| Fix folder collisions by changing the debate's run-id code | Changes production code for the tool's sake. Per-debate numbered subfolders solve it inside the tool. |
| Reuse or extend the product's `write_artifact` for the summary | Couples the tool to the product's internals and either loosens the contract or adds a new capability to design 03. A small writer of the tool's own keeps both sides independent, at the cost of about twenty duplicated lines. |
| Import the debate's submodules for convenience | Ties the tool to internals. Top-level names only. |
| Two input files (one per position) instead of `A \| B` lines | Pairing by position breaks silently if the files drift. Decided by the user on 2026-09-30: one line with `\|`. |
| Also run the judge with the order swapped | Separates debater bias from ordering effects, but needs a second judge call, a new reasoning-core configuration and a step 2 change. Later feature (backlog 002). |
| Run debates in parallel | Faster, but breaks the between-debates budget check and the usage attribution rule. |
| Compute a significance test | Adds statistics the sample sizes cannot support. Rates plus a small-sample warning are more honest. |

## Impact on existing work
- **Production code (`src/debate_ai/`):** **none.** No file is modified, added or removed.
- **Requirements and PRD:** none from this feature. Its requirements are BV-1 to BV-10, kept in the story. The only possible PRD touch is one pointer line at the side-bias metric, pending the story's open question 1.
- **Capability contracts (design 03), control relationships (design 04), framework mapping (design 05):** unchanged. The tool adds no capability to the product and depends on no CrewAI behavior.
- **New code:** `tools/batch_check/` and its tests.
- **Project files:** `pyproject.toml` is not changed if pytest already finds `tools/` from the repo root; if it needs a setting, that is the only edit and it is recorded in the plan.
- **Docs:** a short "validation tools" note in the repo `README.md` and `CLAUDE.md`. Not in the product usage section.

## Agent system design
Not applicable: no change to stages, configurations, or the model calls inside
a run. No pre-build test against CrewAI is needed.

## Risks
| Risk | How it is checked |
|---|---|
| The tool becomes entangled with the product over time (imports of internals, or production code importing the tool) | Boundary tests: production code imports nothing from `tools`; the tool imports only from top-level `debate_ai`; the built package excludes `tools` |
| A run ended by the wall-clock limit leaves a call in flight whose tokens are not counted, so the budget can be undercounted | Known limit from the run report (design 04, 2.5a). Accepted: the overshoot is bounded by one call |
| The default budget stops a batch at about the 10-run "too few runs" threshold | Documented in the summary itself. A user who wants a bigger sample passes `--budget`. Tested |
| A for-win skew is read as debater bias when it is an ordering effect | The summary's fixed limit sentence (BV-6), and a test that it appears |
| The budget is passed by one debate | Documented. A test shows the third motion is skipped after the budget is reached |
| A flaky run distorts the win rate | Exhausted and failed runs are excluded from the rate and counted separately. Tested |
| A malformed file wastes money by failing halfway | The whole file is parsed and validated before the first model call. Tested |
| Pair logic misread (which result counts as consistent) | The four-row table is the specification, and each row has a test |
| Two debates overwrite each other's files | Each debate has its own numbered subfolder. Tested with the same motion twice |
| An interrupted batch leaves no summary | The summary is rewritten after every debate. Tested with a simulated interrupt |

## Test approach
Everything uses an injected fake `run_one` or the fake model; no network, no API key.

| Case | Expected |
|---|---|
| Parse: blank lines, comments, pair lines | Entries as specified. |
| Parse: a line with two `\|`, `A \|`, `\| B`, `\|` alone | Each rejected with its line number and no model call. |
| Empty file, or only comments | Rejected, no model call, no folder. |
| Analyze: rate with an excluded exhausted run | Excluded from the rate and counted separately. |
| Analyze: pair results (for, against), (for, for), (against, against), and a pair with a failed side | Consistent, not consistent, not consistent, and not analyzed. |
| Report: summary text | Per-motion table, rate, pairs, totals, the fixed limit sentence in every summary, and the "too few runs" line under 10 completed runs. |
| Report: progress line | `i/N`, a shortened motion (long motions fit 80 columns), the winner or outcome and stage, tokens. |
| Writer | Atomic replace, idempotent, no temporary file left behind, a clear error on an unwritable folder. |
| Runner: three motions, all succeed | Three numbered subfolders and a `complete` summary with the right rate and totals. |
| Runner: one run exhausted | Listed, excluded from the rate, and the batch continues. |
| Runner: budget reached after the second run | The third motion is listed as skipped. |
| Runner: same motion twice in the same second | Two different subfolders, neither overwrites the other. |
| Runner: interrupt during the second debate | A valid `summary.md` exists covering the first debate and reads `in progress`. |
| CLI: exit codes and streams | 0, 1 and 2 as specified; progress and final lines on standard output; the stop reason and input errors on standard error. |
| Boundary: production imports nothing from `tools` | Scan of `src/debate_ai/` finds no import of `tools`. |
| Boundary: the tool uses only the public interface | Every import of `debate_ai` in `tools/` is from the package top level and only of exported names. |
| Boundary: not shipped | The build configuration includes only `src/debate_ai`. |
| No production change | The existing tests pass unchanged, and `src/debate_ai/` has no diff on the feature branch. |

## Open decisions for review
None open from the earlier round: `A | B` pairs, the 20,000-token default budget, and the swapped-order judge as a later feature were decided on 2026-09-30. The story's two open questions (PRD pointer, and location and command) carry over and affect this design only lightly.

## Review (2026-09-30)

**Original review (before the independence rule), and what became of it**

| # | Finding | Now |
|---|---|---|
| R1 | Two debates in the same second with motions sharing their first 40 characters would share a run folder and overwrite each other. | Solved **without touching production code**: each debate has its own numbered subfolder. The earlier plan to change `run.py` is dropped. |
| R2 | A `debate batch FILE` subcommand conflicts with the CLI's single positional motion. | **No longer applies**: the tool has its own entry point and the `debate` command is untouched. |
| R3 | The summary was written only at the end. | Kept: rewritten after every debate (BV-9). |
| R4 | A pair line with an empty side would run an empty motion. | Kept: such a line is malformed. |
| R5 | The fixed limit sentence had no test. | Kept: test row present. |
| R6 | The budget can be undercounted after a timed-out run. | Kept as an accepted limit. |
| R7 | The tool cannot verify that a pair is a true opposite. | Kept as a stated assumption. |

**Review of the redesign**

- **What holds up.** The dependency runs one way, through three exported names. Each debate builds its own model instances and usage meter, so totals do not leak between debates. An abandoned run is cancelled after its in-flight call and writes nothing further. `RunResult` already carries everything the summary needs. Design 03, 04 and 05 are unaffected.
- **R8 (accepted cost): duplicated code.** The tool has its own atomic writer, about twenty lines that resemble part of the product's `write_artifact`. This is the price of independence. Sharing it would couple the two, so the duplication is deliberate and recorded here.
- **R9 (to confirm at the plan gate): pytest discovery.** Whether `tools/` is importable from the tests without changing `pyproject.toml` is verified while building. If a setting is needed it is a one-line, non-production change and is recorded in the plan's deviations.

## Change log
- 2026-09-30: **reworked** for the independence rule (the user redefined the feature as a modular validation tool independent of the single debate, not part of the product). New: dependency rule with three boundary tests, module breakdown with an injected `run_one`, per-debate subfolders, the tool's own writer, entry point `python -m tools.batch_check`. Removed: any change to production code, the `debate batch` subcommand, the `write_summary` capability in design 03, and PRD requirements. Status Draft, approval pending.
- 2026-09-30: design review. Fixes R1, R3, R4, R5 applied; R2 awaited the user's choice; R6, R7 recorded. Superseded in part by the rework above.
- 2026-09-30: default budget set to 20,000 tokens, and the pair syntax `A | B` confirmed.
- 2026-09-30: replaced the interface section with progress lines and mockups of every case.
- 2026-09-30: migrated from `_docs/design/06` on the pre-workflow branch and reshaped to the template.
