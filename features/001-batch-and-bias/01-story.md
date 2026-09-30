# 001 — Batch and Bias Summary: Story

```
Status: Draft
Tier: complex       (tier approved by the user on 2026-09-30)
Approved: pending
```

_Migrated from the pre-workflow drafts on branch `docs/batch-and-bias`
(PRD O8, FR-8, Q8, Q9 and `_docs/design/06`). Those PRD entries were never
merged to `main`. They live here until delivery, then go into the PRD._

**As a** person evaluating Debate AI, **I want** to run many motions in one
go and get a summary of who won, how often, and what it cost, **so that** I can
see whether the judge favors a side, which the PRD lists as a success metric
and which one debate cannot answer.

## Acceptance criteria
- [ ] Given a text file of motions, one debate runs per motion, one after another, each as an ordinary run (same limits, artifacts and per-run report).
- [ ] A line may declare a pair of opposite motions, and pairs are analyzed together.
- [ ] A run that fails or is exhausted is recorded, and the batch continues.
- [ ] The batch stops early and says so once the tokens spent have reached a budget (default 20,000), before starting the next debate. Motions not started are listed as skipped.
- [ ] A summary is written with a row per motion, the for-win rate, the pair consistency result, and total attempts and tokens.
- [ ] The summary states that a skew toward one side cannot be told apart from an ordering effect, and reports rates without claiming bias.
- [ ] An empty file, or one with no usable motions, is rejected before any model call, as is a malformed line (named by line number).
- [ ] While a batch runs, one progress line is printed as each debate finishes, so the terminal is never silent.
- [ ] The existing `debate "<motion>"` command behaves as before.

## Out of scope
- Running the judge with the argument order swapped, to separate debater bias from ordering effects (see Q8 below). It needs a second judge call, which is a new reasoning-core configuration.
- Running debates in parallel.
- Cost in currency. Reporting stays in tokens.
- Statistical significance tests. The summary shows rates and flags small samples only.
- Storing results across batches.

## Requirement changes
As they will read in `_docs/prd.md`. Applied at delivery, not before.

**Objective**
- **O8** Measure whether the judge favors a side, by running many motions in one batch and summarizing the results. _(Serves the side-bias success metric and NFR-1.)_

**FR-8: Batch run and bias summary**
- FR-8.1 The user can run a batch: a list of motions read from a text file, one debate per motion, run one after another.
- FR-8.2 A line may declare a **pair** of opposite motions (for example "Remote work is better than office work | Office work is better than remote work"). Pairs let the summary test consistency (FR-8.5).
- FR-8.3 Each debate in a batch is an ordinary run (FR-1 to FR-7): same limits, same artifacts, same report. A failed or exhausted run is recorded and the batch continues.
- FR-8.4 The batch stops early, and says so, once the tokens spent have reached a budget (default 20,000), before starting the next debate. Motions not started are listed as skipped. The budget is checked between debates, so a batch can pass it by at most one debate.
- FR-8.5 The batch writes a summary with:
  - one row per motion: outcome, winner (for or against), attempts, tokens, and the run folder;
  - the **for-win rate** over completed runs;
  - for each pair, whether the judge was **position-consistent** (it picked the same position both times, so the winner flipped from for to against or the reverse) or **not** (it picked the same side of the debate both times);
  - the totals from FR-7.
- FR-8.6 The summary states that a skew toward one side cannot be told apart from an ordering effect (see Q8), so it reports a rate and does not assert bias.
- FR-8.7 A batch with an empty file, or a file with no usable motions, is rejected before any model call.
- FR-8.8 While a batch runs, one progress line is printed as each debate finishes, showing its position in the batch, the motion, its winner or outcome, and its tokens. A final line gives the completed count, attempts, tokens and the summary path.

**Success metrics** (changed row)
- "Side bias: across a balanced motion set, proposition wins ≈ opposition wins" gains: "Measured with the FR-8 batch summary."

**Open questions to add**
- **Q8** The judge always receives the proposition argument first and the opposition second. A for-win skew could come from the debaters, or from that order. Should the judge also be run with the order swapped? _Decided 2026-09-30: not in this feature. It is planned as a later feature (backlog item 002 in `features/README.md`). Here the summary reports the rate and pair consistency only, and says so (FR-8.6)._
- **Q9** _(Resolved 2026-09-30)_ The default token budget is 20,000 tokens. At about 2,000 per debate (measured on 2 real runs), that allows roughly 10 debates. The user can raise it with `--budget`.

## Open questions
All three were answered by the user on 2026-09-30:
1. **Pairs:** one line, written `A | B` (not two files). Resolved.
2. **Default budget:** 20,000 tokens. Resolved (Q9).
3. **Swapped-order judge check:** planned as a later feature, not part of this one. Resolved (Q8).

Nothing is open. The story still needs the user's approval (gate 1).

## Change log
- 2026-09-30: recorded the user's answers: `A | B` pair lines, a 20,000-token default budget, and the swapped-order judge as a later feature. Budget wording changed from "exceed" to "reach" to match the design's between-runs rule. Story is still Draft.
- 2026-09-30: added the progress-line criterion and FR-8.8 (found while drafting interface examples for the design). Story is still Draft, so no gate was reopened.
- 2026-09-30: migrated from the pre-workflow drafts. Content unchanged apart from format. Story reset to Draft so it is re-approved under the new gates.
