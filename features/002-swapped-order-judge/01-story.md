# 002 — Swapped-Order Judge Check: Story

```
Status: Approved
Tier: complex       (tier approved by the user on 2026-09-30)
Approved: natank (the user), 2026-09-30
```

_From backlog item 002 and PRD Q8. The wording of the requirement changes
below is draft, for the user to shape at this gate._

**As a** person evaluating Debate AI, **I want** each verdict to be checked
again with the two arguments presented to the judge in the opposite order,
**so that** I can tell whether a verdict reflects the arguments or only the
order in which the judge read them.

**Why now.** The first real batch (feature 001, 6 debates) put the judge on
"Against" for both halves of two pairs of opposite motions. The judge always
reads the proposition first and the opposition second, so that pattern could
come from the debaters or from the reading order, and nothing today can tell
which. FR-8.6 says exactly that.

## Tier
**Complex**, approved by the user on 2026-09-30. Reasons: it changes an existing rule (FR-4: a debate has one
verdict from one judge call), it changes the run report (FR-7), the batch
summary (FR-8), and the meaning of the limit sentence in FR-8.6, and it
probably needs a second judge call, which is a reasoning-core change under
step 2 of the agent design. There is more than one credible design.

## Acceptance criteria
- [ ] The check runs **only when asked**, with a `--check-order` flag. It works with a single motion and, with `--batch`, is applied to every debate in the batch.
- [ ] After the normal verdict, the judge is asked again about the **same two arguments** with their order swapped, and the second answer is made **without seeing the first**.
- [ ] Both verdicts are recorded, and the run says whether they **agree** (the same side's argument won in both orders) or are **order-sensitive** (the winner followed the reading order).
- [ ] The **official verdict stays the first-order verdict**, even when the two orders disagree. A disagreement only flags the run as order-sensitive.
- [ ] If the swapped judge call fails after its retries, the run still succeeds with its official verdict and the check is marked **not completed**.
- [ ] The swapped verdict is saved next to the other artifacts, so a run can be audited.
- [ ] The extra call's attempts and tokens are counted in the run report and against the batch budget.
- [ ] The extra call follows the same limits and validation as the first judge call.
- [ ] The batch summary reports how many completed debates were order-stable, order-sensitive, and not checked, **separately from the for-win rate, which stays based on the official verdict**.
- [ ] Debates run without `--check-order` behave **exactly as they do today**.
- [ ] Existing tests still pass.

## Out of scope
- Any change to the debaters or to how arguments are written.
- More than one swap: with two arguments there are only two orders.
- More than one judge, a panel, or a different judge model.
- Statistical significance tests.
- Explaining *why* the judge's answer flipped.
- Anything else in `_docs/config`, beyond what this check needs.

## Requirement changes
Draft wording, as they would read in `_docs/prd.md` at delivery. Not yet in the PRD.

**Objective**
- **O9** Tell whether a verdict depends on the order in which the arguments are presented.

**FR-9: Order check** _(numbers to be settled at the design gate)_
- FR-9.1 A debate can be run with an order check, requested with `--check-order` (for a single motion, or for every debate in a `--batch`). After the verdict, the judge is asked again about the same two arguments with their order swapped, without seeing the first verdict. Without the flag, no check is made.
- FR-9.2 The run records both verdicts and whether the winning side's **argument** was the same in both orders (**order-stable**) or not (**order-sensitive**).
- FR-9.3 The swapped verdict is saved as an artifact.
- FR-9.4 The extra call's attempts and tokens are included in the FR-7 report and the FR-8.4 budget.
- FR-9.5 The extra call has the same attempt limit and validation as the first judge call.
- FR-9.6 The batch summary reports the order-stable and order-sensitive counts, separately from the for-win rate.
- FR-9.7 Without the order check, behavior is unchanged.
- FR-9.8 The official verdict is always the first-order verdict (FR-4). If the two orders disagree, the run is flagged order-sensitive and the official verdict is not changed.
- FR-9.9 If the swapped judge call fails after its retries, the run does not fail: it keeps its official verdict and the order check is reported as **not completed**.
- FR-9.10 The FR-8.5 for-win rate is based on the official verdict only. Order sensitivity is reported separately (FR-9.6).

**Changes to existing requirements** (wording to settle at the design gate)
- FR-8.6 currently says a skew cannot be told apart from an ordering effect. With order-check data, the summary should say what the data does and does not show. Without it, the sentence stays.
- PRD Q8 is closed by this feature.

## Open questions
All five were answered by the user on 2026-09-30, each as proposed:
1. **Where it runs:** only when asked, with `--check-order` (not on every debate). Resolved.
2. **Official verdict when the orders disagree:** the first-order verdict stays official and the run is flagged order-sensitive. Resolved.
3. **If the swapped call fails:** the run still succeeds and the check is marked "not completed". Resolved.
4. **For-win rate:** unchanged. Order sensitivity is reported separately. Resolved.
5. **Tier:** complex. Resolved.

**One reading of question 1 to confirm at approval:** `--check-order` is accepted both for a single motion and together with `--batch`, where it applies to every debate in the batch. The cost is about 1,000 extra tokens per debate, so with the default 20,000-token budget a checked batch covers about 6 or 7 debates instead of about 10. A larger `--budget` is the way around that.

Nothing else is open. Story approved by the user on 2026-09-30 (gate 1 passed).

## Change log
- 2026-09-30: approved by the user (gate 1). Design work may start.
- 2026-09-30: recorded the user's answers to all five questions (each as proposed), including approval of the complex tier. Added the `--check-order` flag, the official-verdict rule, the failed-check rule and FR-9.8 to 9.10. Story is still Draft: gate 1 needs the user's explicit approval.
- 2026-09-30: story drafted from backlog item 002. Draft, awaiting the user's answers and approval (gate 1).
