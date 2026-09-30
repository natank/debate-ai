# 001 — Batch Validation Tool (bias summary): Delivery Plan

```
Status: Draft          (reworked 2026-09-30 for the independence rule)
Approved: pending
Design: 02-design.md (must be Approved before this is worked on)
```

_New under the workflow: the pre-workflow drafts had no delivery plan. Reworked
after the feature was redefined as a modular validation tool._

## Subtasks

Each module is built and tested on its own, pure ones first. Nothing under
`src/debate_ai/` is touched by any subtask.

| # | Subtask | Acceptance check / test | Depends on | Done |
|---|---|---|---|---|
| 1 | **`parse.py`**: read the motions file into entries (single or pair), ignoring blanks and comments. Reject an empty file, a file with only comments, or a malformed line (more than one `\|`, or an empty side) with its line number. | Parse tests: blanks, comments, pairs, `A \|\| B`-style double bars, `A \|`, `\| B`, `\|` alone, empty file. No model call on rejection. | - | [ ] |
| 2 | **`analyze.py`**: from a list of run results and the entries, compute per-motion rows, for-win rate, pair consistency (the four cases and the not-analyzed case), and totals. Pure. | Rate excludes an exhausted run and counts it separately; all four pair cases; a pair with a failed side is not analyzed. | 1 | [ ] |
| 3 | **`report.py`**: render `summary.md` (with `in progress` or `complete`), the progress line, the final line, and the stop message. Pure. | The fixed limit sentence is in every summary; the "too few runs" line under 10 completed runs; long motions fit 80 columns; exhausted and failed lines name the stage. | 2 | [ ] |
| 4 | **`writer.py`**: atomic write of `summary.md` (temporary file in the same folder, then rename), the tool's own. | Idempotent; no temporary file left behind; a clear error for an unwritable folder. | - | [ ] |
| 5 | **`runner.py`**: run entries in order through an injected `run_one(motion, output_dir)`, each into its own numbered subfolder; continue past failed runs; check the budget between debates; list skipped motions; rewrite the summary after every debate. | Three succeed; one exhausted continues; budget reached after run two skips run three; the same motion twice in one second gets two subfolders; a simulated interrupt during run two leaves a valid `in progress` summary. | 1, 2, 3, 4 | [ ] |
| 6 | **`cli.py` and `__main__.py`**: arguments `--budget` and `--output-dir`; the real `run_one` (a thin wrapper around `run_debate`, importing only top-level `debate_ai` names); exit codes 0, 1 and 2; progress and final lines on stdout; the stop reason and input errors on stderr. | Each exit code; streams; progress line order; `python -m tools.batch_check` runs. | 5 | [ ] |
| 7 | **Boundary tests.** (a) no module under `src/debate_ai/` imports `tools`; (b) every `debate_ai` import in `tools/` is from the package top level and only of exported names; (c) the build configuration includes only `src/debate_ai`. | All three pass, and each is shown to fail when the rule is deliberately broken (checked once, then reverted). | 6 | [ ] |
| 8 | **No-production-change check.** Confirm `src/debate_ai/` has no diff against `main` and the existing tests pass unchanged. | `git diff main -- src/debate_ai` is empty; the full test suite passes. | 7 | [ ] |
| 9 | **Real check.** One small batch (a pair and one single motion) against the real model, to confirm the flow and that the summary reads sensibly. Costs a few cents; run only with the user's go-ahead. | Manual review of `summary.md`, recorded here. | 8 | [ ] |

## Branch and PR plan
`feature/001-batch-and-bias`. **One PR** for the whole feature: the modules are
small and only make sense together. The documents (story, design, plan) are the
first commits on the branch, and the code and documentation updates follow.

## Documentation to update (part of delivery)
- [ ] `_docs/prd.md`: **no requirements added.** At most one pointer line at the side-bias metric, only if the user approves it (story, open question 1).
- [ ] `README.md`: a short "Validation tools" section with the command, the file format and the budget. Not in the product usage section.
- [ ] `CLAUDE.md`: add the command to the commands list, marked as a development tool.
- [ ] `features/README.md`: set this feature's state to Delivered in the index.
- [ ] Design 03, 04 and 05: **no change** (confirmed by the design). Record that here at delivery.

## Definition of Done
See `features/README.md`, section 6. Every item applies except the PRD item, which
for a tooling feature means "no requirements added" (see the workflow's note on
feature kinds).

## Deviations
- none yet

## Change log
- 2026-09-30: **reworked** for the independence rule: removed the `run.py` change (former subtask 0), the `write_summary` capability, the `debate batch` subcommand, and the PRD and design 03 updates; split the tool into modules with their own subtasks; added the boundary tests and the no-production-change check. Draft.
- 2026-09-30: added subtask 0 (unique run folders) and updated subtasks 1 and 4 after the design review. Superseded above.
- 2026-09-30: subtask 5 covered progress lines. Superseded above.
- 2026-09-30: written during migration. Draft.
