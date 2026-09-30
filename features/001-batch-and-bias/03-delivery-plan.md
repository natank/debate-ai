# 001 — Batch and Bias Summary: Delivery Plan

```
Status: Approved
Approved: natank (the user), 2026-09-30
Design: 02-design.md (Approved, gate 2 passed)
```

_New under the workflow: the pre-workflow drafts had no delivery plan._

## TL;DR

**What:** run many motions in one command and get one summary of who won, how
often, and what it cost, so we can see whether the judge favors a side.

**How you use it:** put motions in a text file, one per line. Write `A | B` on
one line for a pair of opposite motions. Then run:

```
debate --batch motions.txt [--budget 20000]
```

**What you get:** a progress line as each debate finishes, and a `summary.md`
with a row per motion, the for-win rate, whether the judge stayed consistent on
each pair, and total attempts and tokens. The summary is rewritten after every
debate, so an interrupted batch still leaves a valid one.

**Boundaries:**
- Each debate is an ordinary single run. The batch only calls it and never changes how a debate works.
- It stops once tokens spent reach the budget (default 20,000, about 10 debates). A failed run doesn't stop the batch.
- It reports rates, not a verdict of bias. The judge always sees the proposition first, so a skew can't be blamed on the debaters alone (the swapped-order check is backlog item 002).

**What gets built:** seven subtasks in one PR. One is a small fix so no run
overwrites another's folder. The rest are an input parser, a summary writer,
the summary maths, the batch driver, and the `--batch` flag. An optional real
check at the end costs about 6,000 tokens.

**Touches existing code in two small places:** `run.py` (unique folders) and
`cli.py` (the flag). The single run does not depend on the batch.


## Subtasks

| # | Subtask | Acceptance check / test | Depends on | Done |
|---|---|---|---|---|
| 0 | **Unique run folders** (design review R1). In `run.py`, append `-2`, `-3`, ... when the run folder already exists, so no run overwrites another. | Test: two identical motions run in the same second get different folders. Existing tests still pass. | - | [x] |
| 1 | **Input parser.** Read the motions file into entries (single or pair), ignoring blanks and comments. Reject an empty file, a file with no usable motions (only blanks and comments), or a malformed line (more than one `\|`, or an empty side) with its number. | Parse tests: blanks, comments, pairs, a line with two `\|`, `A \|`, `\| B`, `\|` alone, empty file, a file of only comments. No model call on rejection. | - | [ ] |
| 2 | **`write_summary` capability.** Atomic, derived-path write of `summary.md`, with the same safety rules as `write_artifact`. | Tests: unsafe `batch_id`, empty content, idempotent replace, cleanup on failure. | - | [ ] |
| 3 | **Summary computation.** From a list of run results: per-motion rows, for-win rate, pair consistency (four cases), totals, the fixed limit sentence, the small-sample line, `skipped` rows, and the header line (`in progress (k of N done)` or `complete`). Pure function, no model calls. | Tests: rate with an excluded exhausted run; all four pair cases and the not-analyzed case; limit sentence present; small-sample line under 10 runs; skipped rows shown; both header states. | - | [ ] |
| 4 | **Batch driver.** Run motions sequentially through `run_debate` into the batch folder, continue past failed runs, check the budget between runs, list skipped motions, and rewrite the summary after every debate (`in progress`, then `complete`). The driver takes the debate function and the model factory as parameters (defaulting to `run_debate` and the real model), so tests can inject fakes. | Tests: three succeed; one exhausted continues; budget passed after run two skips run three; an interrupt during run two leaves a valid `in progress` summary. | 0, 1, 2, 3 | [ ] |
| 5 | **CLI `--batch` flag.** `debate --batch FILE` with `--budget` and `--output-dir`, exit codes 0, 1 and 2, a progress line as each debate finishes (FR-8.8) and a final line, with the streams as in the design's interface section. Existing single-motion command unchanged. | CLI tests for each exit code; parsing (`--batch` alone, a motion alone, neither, both, `--budget` without `--batch`, and the one-word motion `batch` as an ordinary motion); progress line format, shortening and order; stdout and stderr split; and a test that `debate "<motion>"` still works. | 4 | [ ] |
| 6 | **Real check.** One small batch (a pair and one single motion) against the real model, to confirm the flow and the summary read sensibly. Three debates, about 6,000 tokens at the roughly 2,000 measured per debate, which is within the 20,000 default budget. Not priced in currency. Run only with the user's go-ahead. | Manual review of `summary.md` recorded in Deviations or here. | 5 | [ ] |

**Order of work.** Subtask 0 first, because it changes shared code and the
existing tests must keep passing. Then 1, 2 and 3 in any order (they do not
depend on each other), then 4, then 5, then 6. Subtasks 0 to 5 use the fake
model only: no network and no API key.

## Traceability

Every acceptance criterion in the story is covered by at least one subtask.

| Story acceptance criterion | Subtask(s) |
|---|---|
| One debate per motion, one after another, each an ordinary run | 4 |
| A line may declare a pair, and pairs are analyzed together | 1, 3 |
| A failed or exhausted run is recorded and the batch continues | 4 |
| Stops early once the budget is reached, skipped motions listed | 4 |
| Summary: per-motion rows, for-win rate, pair consistency, totals | 2, 3, 4 |
| Summary states the skew cannot be told apart from an ordering effect | 3 |
| Empty file, no usable motions, or a malformed line rejected before any model call | 1 |
| Progress line as each debate finishes (FR-8.8) | 5 |
| `debate "<motion>"` behaves as before | 0, 5 |
| _Design R1: no run overwrites another_ | 0 |
| _Design R3: interrupted batch leaves a valid summary_ | 3, 4 |

## Branch and PR plan
`feature/001-batch-and-bias`. **One PR** for the whole feature, including subtask 0 (unique run folders). The user chose on 2026-09-30 not to ship that fix separately. The subtasks are small and only make sense together. The documents (story, design, plan)
are the first commits on the branch, and the code and documentation updates
follow.

## Documentation to update (part of delivery)
- [ ] `_docs/prd.md`: add O8, FR-8 (**8.1 to 8.8**, including the progress lines), the resolved Q8 and Q9 as decided in the story (later feature 002; 20,000-token budget), and the note on the side-bias metric, exactly as written in the story.
- [ ] `_docs/design/03-capability-contracts.md`: add the `write_summary` contract.
- [ ] `features/README.md`: also remove backlog item 002 from Backlog only if it has been started; otherwise leave it.
- [ ] `README.md`: document `debate --batch`, the file format, the budget, and the summary.
- [ ] `features/README.md`: set this feature's state to Delivered in the index.
- [ ] `CLAUDE.md`: add `debate --batch` to the commands if it adds anything a new session needs.

## Review (2026-09-30)

The plan was checked against the approved story and design.

**What holds up:** every acceptance criterion is covered (see Traceability);
every subtask has its own check; the dependency order is sound; the work is
one PR as the user decided; subtasks 0 to 5 need no network or API key.

**Findings, and what was done**

| # | Severity | Finding | Disposition |
|---|---|---|---|
| P1 | Medium | The documentation list said FR-8.1 to 8.7, but the story now has FR-8.8 (progress lines). The PRD would have been updated without it. | **Fixed.** Also lists the resolved Q8 and Q9. |
| P2 | Medium | Subtask 3 did not cover the `skipped` rows or the `in progress` / `complete` header that the design requires. | **Fixed** in subtask 3, with tests. |
| P3 | Medium | Subtask 4 had no way to inject a fake debate or model, so its tests could not run without the network. | **Fixed:** the driver takes the debate function and model factory as parameters. |
| P4 | Low | Subtask 1 did not test a file containing only comments (FR-8.7 "no usable motions"). | **Fixed.** |
| P5 | Low | Subtask 6 said "a few cents", which is an unpriced guess. | **Fixed:** stated as about 6,000 tokens, within the default budget. |
| P6 | Low | No traceability from story to subtasks, and no stated order. | **Fixed:** added both. |
| P7 | Low | The documentation list had no explicit rule for the backlog item 002 entry. | **Fixed:** left alone unless started. |

## Definition of Done
See `features/README.md`, section 6. Every item applies.

## Deviations
- none yet

## Change log
- 2026-09-30: approved by the user (gate 3 passed). All three gates passed; delivery may start.
- 2026-09-30: added the TL;DR at the top. No change to scope. Still Draft.
- 2026-09-30: plan review. Fixes P1 to P7 applied. Still Draft, pending gate 3 approval.
- 2026-09-30: CLI form is the `--batch` flag (design approved). Still Draft.
- 2026-09-30: recorded the user's decision that subtask 0 ships in the feature's single PR, not on its own. Still Draft.
- 2026-09-30: added subtask 0 (unique run folders) and updated subtasks 1 and 4 after the design review. Still Draft.
- 2026-09-30: subtask 5 now covers progress lines (FR-8.8). Still Draft.
- 2026-09-30: written during migration. Draft.
