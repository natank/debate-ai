# 001 — Batch and Bias Summary: Delivery Plan

```
Status: Draft
Approved: pending
Design: 02-design.md (must be Approved before this is worked on)
```

_New under the workflow: the pre-workflow drafts had no delivery plan._

## Subtasks

| # | Subtask | Acceptance check / test | Depends on | Done |
|---|---|---|---|---|
| 0 | **Unique run folders** (design review R1). In `run.py`, append `-2`, `-3`, ... when the run folder already exists, so no run overwrites another. | Test: two identical motions run in the same second get different folders. Existing tests still pass. | - | [ ] |
| 1 | **Input parser.** Read the motions file into entries (single or pair), ignoring blanks and comments. Reject an empty file or a malformed line (more than one `\|`, or an empty side) with its number. | Parse tests: blanks, comments, pairs, a line with two `\|`, `A \|`, `\| B`, `\|` alone, empty file. No model call on rejection. | - | [ ] |
| 2 | **`write_summary` capability.** Atomic, derived-path write of `summary.md`, with the same safety rules as `write_artifact`. | Tests: unsafe `batch_id`, empty content, idempotent replace, cleanup on failure. | - | [ ] |
| 3 | **Summary computation.** From a list of run results: per-motion rows, for-win rate, pair consistency (four cases), totals, the fixed limit sentence, and the small-sample line. Pure function, no model calls. | Tests: rate with an excluded exhausted run; all four pair cases and the not-analyzed case; limit sentence present; small-sample line under 10 runs. | - | [ ] |
| 4 | **Batch driver.** Run motions sequentially through `run_debate` into the batch folder, continue past failed runs, check the budget between runs, list skipped motions, and rewrite the summary after every debate (`in progress`, then `complete`). | Tests: three succeed; one exhausted continues; budget passed after run two skips run three; an interrupt during run two leaves a valid `in progress` summary. | 0, 1, 2, 3 | [ ] |
| 5 | **CLI `debate batch`.** Arguments `--budget` and `--output-dir`, exit codes 0, 1 and 2, a progress line as each debate finishes (FR-8.8) and a final line, with the streams as in the design's interface section. Existing single-motion command unchanged. | CLI tests for each exit code; progress line format, shortening and order; stdout and stderr split; and a test that `debate "<motion>"` still works. | 4 | [ ] |
| 6 | **Real check.** One small batch (a pair and one single motion) against the real model, to confirm the flow and the summary read sensibly. Costs a few cents; run only with the user's go-ahead. | Manual review of `summary.md` recorded here. | 5 | [ ] |

## Branch and PR plan
`feature/001-batch-and-bias`. **One PR** for the whole feature, including subtask 0 (unique run folders). The user chose on 2026-09-30 not to ship that fix separately. The subtasks are small and only make sense together: the subtasks
are small and only make sense together. The documents (story, design, plan)
are the first commits on the branch, and the code and documentation updates
follow.

## Documentation to update (part of delivery)
- [ ] `_docs/prd.md`: add O8, FR-8 (8.1 to 8.7), Q8 and Q9, and the note on the side-bias metric, exactly as written in the story.
- [ ] `_docs/design/03-capability-contracts.md`: add the `write_summary` contract.
- [ ] `README.md`: document `debate batch`, the file format, the budget, and the summary.
- [ ] `features/README.md`: set this feature's state to Delivered in the index.
- [ ] `CLAUDE.md`: add `debate batch` to the commands if it adds anything a new session needs.

## Definition of Done
See `features/README.md`, section 6. Every item applies.

## Deviations
- none yet

## Change log
- 2026-09-30: recorded the user's decision that subtask 0 ships in the feature's single PR, not on its own. Still Draft.
- 2026-09-30: added subtask 0 (unique run folders) and updated subtasks 1 and 4 after the design review. Still Draft.
- 2026-09-30: subtask 5 now covers progress lines (FR-8.8). Still Draft.
- 2026-09-30: written during migration. Draft.
