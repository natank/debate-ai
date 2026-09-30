# 001 — Batch Validation Tool (bias summary): Story

```
Status: Draft          (reopened 2026-09-30, see change log; was Approved)
Tier: complex          (tier approved by the user on 2026-09-30)
Kind: tooling          (validation tool for developers, not product functionality)
Approved: pending      (re-approval needed)
```

_Migrated from the pre-workflow drafts on branch `docs/batch-and-bias`
(PRD O8, FR-8, Q8, Q9 and `_docs/design/06`). Those drafts treated this as a
product feature. On 2026-09-30 the user redefined it as a **validation tool**
that is modular and independent of the single debate. This story reflects that._

**As a** developer validating Debate AI, **I want** to run many motions in one
go and get a summary of who won, how often, and what it cost, **so that** I can
check whether the judge favors a side (a PRD success metric that one debate
cannot answer) **without adding anything to the product or coupling the debate
code to this check**.

## The independence rule

This is the rule the rest of the feature is built on:

- The validation tool **depends on** the single debate, through its public
  interface only (`run_debate`, `RunResult`, `StageStats` as exported by
  `debate_ai`).
- The single debate **does not depend on** the tool in any way, and no code under
  `src/debate_ai/` changes for this feature.
- The tool is **not part of the product**: it is not in the `debate` command, not
  shipped in the package, and adds no requirements to the PRD.

## Acceptance criteria
- [ ] Given a text file of motions, one debate runs per motion, one after another, each as an ordinary `run_debate` call (same limits, artifacts and per-run report).
- [ ] A line may declare a pair of opposite motions, and pairs are analyzed together.
- [ ] A run that fails or is exhausted is recorded, and the batch continues.
- [ ] The batch stops early and says so once the tokens spent have reached a budget (default 20,000), before starting the next debate. Motions not started are listed as skipped.
- [ ] A summary is written with a row per motion, the for-win rate, the pair consistency result, and total attempts and tokens.
- [ ] The summary is rewritten after every debate, so an interrupted batch still leaves a valid summary.
- [ ] The summary states that a skew toward one side cannot be told apart from an ordering effect, and reports rates without claiming bias.
- [ ] An empty file, one with no usable motions, or a malformed line is rejected before any model call (the line is named by number).
- [ ] While a batch runs, one progress line is printed as each debate finishes, so the terminal is never silent.
- [ ] **Independence, enforced by tests:** no module under `src/debate_ai/` imports the tool; the tool imports only from the top level of `debate_ai`; the tool is not included in the built package.
- [ ] **No production change:** no file under `src/debate_ai/` is modified, the `debate` command behaves exactly as before, and the existing tests pass unchanged.

## Out of scope
- Anything that changes production code or the `debate` command.
- Adding this tool to the product, the PRD's functional requirements, or the user-facing README usage.
- Running the judge with the argument order swapped, to separate debater bias from ordering effects. It needs a second judge call, which is a new reasoning-core configuration. Planned as a later feature (backlog 002).
- Running debates in parallel.
- Cost in currency. Reporting stays in tokens.
- Statistical significance tests. The summary shows rates and flags small samples only.
- Storing results across batches.

## Requirements (feature-local)
These live in this feature, **not in `_docs/prd.md`**. IDs use the prefix BV
(batch validation) so they cannot be confused with the PRD's FR numbers.

- **BV-1** The tool reads a text file of motions and runs one debate per motion, one after another, each through `run_debate`.
- **BV-2** A line may declare a **pair** of opposite motions (for example "Remote work is better than office work | Office work is better than remote work"). Pairs let the summary test consistency (BV-5).
- **BV-3** A failed or exhausted run is recorded, and the batch continues.
- **BV-4** The batch stops early, and says so, once the tokens spent have reached a budget (default 20,000), before starting the next debate. Motions not started are listed as skipped. The budget is checked between debates, so a batch can pass it by at most one debate.
- **BV-5** The tool writes a summary with:
  - one row per motion: outcome, winner (for or against), attempts, tokens, and the run folder;
  - the **for-win rate** over completed runs;
  - for each pair, whether the judge was **position-consistent** (it picked the same position both times, so the winner flipped from for to against or the reverse) or **not** (it picked the same side of the debate both times);
  - the totals of attempts and tokens.
- **BV-6** The summary states that a skew toward one side cannot be told apart from an ordering effect, so it reports a rate and does not assert bias.
- **BV-7** A file that is empty, has no usable motions, or has a malformed line is rejected before any model call.
- **BV-8** While a batch runs, one progress line is printed as each debate finishes, showing its position in the batch, the motion, its winner or outcome, and its tokens. A final line gives the completed count, attempts, tokens and the summary path.
- **BV-9** The summary is rewritten after every debate, so an interrupted batch leaves a valid summary covering the debates done so far.
- **BV-10** The independence rule above holds, and tests enforce it.

## Open questions
1. **PRD pointer.** The PRD's side-bias metric ("proposition wins ≈ opposition wins") is measured by this tool. Should the PRD get a single-line pointer at that metric, "measured with the validation tool in `features/001-batch-and-bias`", or nothing at all? _Proposed: the one-line pointer. It adds no requirement, only says where the metric is checked._
2. **Location and command.** The tool would live in a top-level `tools/batch_check/` package, outside `src/debate_ai/`, and run as `uv run python -m tools.batch_check motions.txt`. Is that the right place and name?

Already decided by the user on 2026-09-30: pairs are written as `A | B` on one line; the default budget is 20,000 tokens; the swapped-order judge check is a later feature; and this is a modular validation tool, independent of the single debate.

## Change log
- 2026-09-30: **reopened** (was Approved) after the user redefined the feature as a validation tool that is modular and independent of the single debate, not part of the product. Changes: added the independence rule and two independence acceptance criteria; removed the criterion that the `debate` command gains behavior; requirements renamed from FR-8 to feature-local BV-1 to BV-10 and no longer go into the PRD; removed PRD objective O8 and open questions Q8, Q9 (their decisions are recorded in the sections above); replaced the open questions. Gate 1 needs re-approval.
- 2026-09-30: approved by the user (gate 1) in its earlier form. Superseded by the reopening above.
- 2026-09-30: recorded the user's answers: `A | B` pair lines, a 20,000-token default budget, and the swapped-order judge as a later feature.
- 2026-09-30: added the progress-line criterion.
- 2026-09-30: migrated from the pre-workflow drafts.
