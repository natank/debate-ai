# 002 — Swapped-Order Judge Check: Delivery Plan

```
Status: Approved
Approved: natank (the user), 2026-09-30
Design: 02-design.md (Approved, gate 2 passed)
```

## TL;DR

**What:** an optional check on a debate's verdict. After the normal verdict,
the judge is asked again about the same two arguments in the opposite order.
If the same side wins both times the verdict is **stable**; if the winner
follows the reading order it is **order-sensitive**.

**How you use it:** add `--check-order` to a single debate or to a batch:

```
debate "<motion>" --check-order
debate --batch motions.txt --check-order
```

**What you get:** an `Order check:` line for a single debate; for a batch, a
tag on each progress line and an `Order check` column and section in
`summary.md`. The swapped verdict is saved as `decide_swapped.md`.

**Boundaries:**
- Off by default. Without the flag, everything is exactly as it is today.
- The official verdict is always the first one. The check never changes it and never fails a debate.
- It costs about 1,000 extra tokens per debate. A checked batch fits about 6 or 7 debates in the default 20,000-token budget.
- A flip can be the reading order or ordinary variation between judge calls, and the summary says so. A same-order repeat to measure the noise is backlog item 003.

**What gets built:** seven subtasks in one PR: the stage list and artifact, the
verdict comparison, the fourth stage with its success paths, the failure rule,
the summary changes, the CLI flag, and an optional real-model check (about
18,000 tokens).

**Touches existing code:** `run.py`, `artifacts.py`, `summary.py`, `cli.py`.
`batch.py` needs no change.

## Subtasks

| # | Subtask | Acceptance check / test | Depends on | Done |
|---|---|---|---|---|
| 0 | **Per-run stage list and artifact stage.** `write_artifact` accepts `decide_swapped`. Each run uses its own stage list (three stages, four with the check), and the failing-stage lookup uses it. The report labels this stage `swapped`. | Tests: `write_artifact` accepts `decide_swapped` and still rejects unknown stages; a normal run can never report `decide_swapped` as its next stage; the report label is `swapped` and stays aligned. All existing tests pass unchanged. | - | [x] |
| 1 | **`OrderCheck` and the comparison.** Add `OrderCheck` (status, swapped verdict, favored, reason) and `RunResult.order_check` (default `None`). A pure function compares the official and swapped winners. | Tests: all four rows of the design's table (stable for/for and against/against; sensitive favored `first`; sensitive favored `last`); the not-completed builder carries a reason; constructing a `RunResult` without the field still works. | - | [x] |
| 2 | **Fourth stage, success paths.** `run_debate(..., check_order=False)`. When true, build S4 from the existing `decide` task config with `context=[oppose, propose]` and the same verdict guardrail; render and save `decide_swapped.md`; compute the `OrderCheck`; count the stage's attempts and tokens. | Tests (fake model): check off makes no S4 call and creates no `order_check`; on and same winner gives `stable`, four stages, both artifacts; each flip direction; the swapped prompt equals the official prompt apart from argument order (E4) and reverses the arguments (E1) and never contains the first verdict (E2); attempts and tokens appear under `decide_swapped` and in the total; at most 12 model calls; S3 failing with the flag on ends the run as today and S4 never starts. | 0, 1 | [ ] |
| 3 | **The check never fails the run.** One shared helper, used by every ending path: if `decide` completed and only `decide_swapped` did not, the run succeeds with `not_completed` and a reason. Paths: S4 exhausted after 3 attempts, the wall-clock limit during S4, and a failed write of `decide_swapped.md` after retries. | One test per path: run succeeds, `not_completed` with the right reason, the official verdict and `decide.md` intact, and (for exhaustion) exactly 3 S4 attempts. | 2 | [ ] |
| 4 | **Summary changes.** With the check requested: an `Order check` column, an `Order check` section (checked, stable, sensitive with first/last counts, not completed), and the data-aware closing paragraph when at least one check completed. Otherwise the existing FR-8.6 sentence. For-win rate and pair consistency stay on official verdicts. | Tests: column, section and paragraph appear only when the flag was used and a check completed; the counts are right; for-win rate and pairs unchanged by the check; **a batch without the flag produces byte-for-byte the same summary as before**. | 1 | [ ] |
| 5 | **CLI flag.** `--check-order` for a single motion and for `--batch`. The CLI passes `check_order` to `run_debate` **only when the flag is given**. Single run prints the `Order check:` line for all three results; batch progress lines get the `stable` / `sensitive` / `no check` tag and stay within 80 columns; exit codes unchanged. | Tests: the existing CLI tests pass unchanged (their fakes take only `(motion, output_dir)`); the flag reaches every debate in a batch; each `Order check:` line; the tag and line width; a not-completed check leaves the exit code at 0. | 2, 3, 4 | [ ] |
| 6 | **Real check.** Run the existing `motions.txt` (six debates) with `--check-order`, about 3,000 tokens each, so about 18,000 tokens, just inside the default budget. Run only with the user's go-ahead. | Manual review of the results, recorded here. | 5 | [ ] |

**Order of work.** Subtasks 0 and 1 first, in either order (0 changes shared
code, so the existing tests must keep passing). Then 2, then 3, then 4 (it needs
only subtask 1 and can be done any time after it), then 5, then 6. Subtasks 0
to 5 use the fake model only: no network and no API key.

**Test tooling.** The subtask 3 timeout test needs a fake model that is slow
only on its fourth call. `tests/fakes.py` gets a per-call delay option for it.

## Traceability

| Story acceptance criterion | Subtask(s) |
|---|---|
| Runs only when asked, with `--check-order`, for a single motion or a batch | 5 |
| The judge is asked again about the same arguments swapped, without seeing its first answer | 2 |
| Both verdicts recorded, and the run says stable or order-sensitive | 1, 2 |
| The official verdict stays the first-order verdict | 2, 3 |
| A failed swapped call: the run succeeds, the check is "not completed" | 3 |
| The swapped verdict is saved as an artifact | 0, 2 |
| The extra call's attempts and tokens count in the report and the budget | 2, 5 |
| The extra call has the same limits and validation | 2 |
| Batch summary reports stable, sensitive and unchecked, separately from the for-win rate | 4 |
| Without the flag, behavior is exactly as today | 0, 2, 4, 5 |
| Existing tests still pass | every subtask |

## Branch and PR plan
`feature/002-swapped-order-judge`. **One PR** for the whole feature, as with
feature 001: the subtasks only make sense together. The documents (story,
design, plan) are the first commits, then one commit per subtask, then the
documentation commit.

## Documentation to update (part of delivery)
- [ ] `_docs/prd.md`: add O9 and FR-9.1 to 9.10 as in the story; rewrite FR-8.6 for when check data exists; mark Q8 as delivered by this feature.
- [ ] `_docs/design/01-stages-and-sequence.md`: add S4 and its dependency on S1 and S2 only.
- [ ] `_docs/design/02-reasoning-core-configs.md`: the Judge serves S3 and S4, with the argument order as a per-call parameter.
- [ ] `_docs/design/03-capability-contracts.md`: `write_artifact` accepts `decide_swapped`.
- [ ] `_docs/design/04-control-relationships.md`: S4's memory allowlist, the 12-call cap, the rule that S4 never fails the run, and the outer-loop comparison step.
- [ ] `README.md`: the flag, what it reports, and its cost.
- [ ] `CLAUDE.md`: mention the flag and its cost if a new session needs it.
- [ ] `features/README.md`: set this feature's state in the index.

## Definition of Done
See `features/README.md`, section 6. Every item applies.

## Review (2026-09-30)

Checked against the approved story and design and against the code.

**What holds up:** every acceptance criterion is covered (see Traceability);
each subtask has its own checks; the order of work is sound; it is one PR;
subtasks 0 to 5 need no network or API key; `batch.py` really needs no change.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| P1 | Medium | The new `RunResult.order_check` field would be needed by both the run loop and the summary. Putting it in the run-loop subtask would block the summary work for no reason. | **Fixed:** the data model and comparison are their own subtask (1), so subtask 4 depends only on it. |
| P2 | Medium | The design's rule that the check never fails the run has to hold on three different ending paths, and would be easy to implement three times. | **Fixed:** subtask 3 is one shared helper with one test per path. |
| P3 | Medium | The wall-clock test needs a fake model that is slow on one specific call, which the current fake cannot do. | **Fixed:** noted as test tooling in the plan. |
| P4 | Medium | Existing CLI tests use fakes that take only `(motion, output_dir)`. Always passing `check_order` would break them. | **Fixed:** the flag is passed only when given, and subtask 5's check requires the existing CLI tests to pass unchanged. |
| P5 | Low | The real check costs about 18,000 tokens, which is close to the 20,000 default budget. | **Noted** in subtask 6 and the TL;DR. If a debate runs long the batch may stop one motion early, which is expected behavior. |

## Deviations
- none yet

## Change log
- 2026-09-30: approved by the user (gate 3 passed). All three gates passed; delivery starts.
- 2026-09-30: written after the design was approved. Draft, pending gate 3.
