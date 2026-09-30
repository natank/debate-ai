# 002 — Swapped-Order Judge Check: Story

```
Status: Draft
Tier: complex       (proposed by the agent, tier approval pending; see "Proposed tier" below)
Approved: pending
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

## Proposed tier
**Complex.** Reasons: it changes an existing rule (FR-4: a debate has one
verdict from one judge call), it changes the run report (FR-7), the batch
summary (FR-8), and the meaning of the limit sentence in FR-8.6, and it
probably needs a second judge call, which is a reasoning-core change under
step 2 of the agent design. There is more than one credible design.
The user decides the tier.

## Acceptance criteria
- [ ] After the normal verdict, the judge is asked again about the **same two arguments** with their order swapped, and the second answer is made **without seeing the first**.
- [ ] Both verdicts are recorded, and the run says whether they **agree** (the same side's argument won in both orders) or are **order-sensitive** (the winner followed the reading order).
- [ ] The swapped verdict is saved next to the other artifacts, so a run can be audited.
- [ ] The extra call's attempts and tokens are counted in the run report and against the batch budget.
- [ ] The extra call follows the same limits and validation as the first judge call.
- [ ] The batch summary reports how many completed debates were order-stable and how many were order-sensitive, separately from the for-win rate.
- [ ] Debates run without the check behave **exactly as they do today**.
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
- FR-9.1 A debate can be run with an order check: after the verdict, the judge is asked again about the same two arguments with their order swapped, without seeing the first verdict.
- FR-9.2 The run records both verdicts and whether the winning side's **argument** was the same in both orders (**order-stable**) or not (**order-sensitive**).
- FR-9.3 The swapped verdict is saved as an artifact.
- FR-9.4 The extra call's attempts and tokens are included in the FR-7 report and the FR-8.4 budget.
- FR-9.5 The extra call has the same attempt limit and validation as the first judge call.
- FR-9.6 The batch summary reports the order-stable and order-sensitive counts, separately from the for-win rate.
- FR-9.7 Without the order check, behavior is unchanged.

**Changes to existing requirements** (wording to settle at the design gate)
- FR-8.6 currently says a skew cannot be told apart from an ordering effect. With order-check data, the summary should say what the data does and does not show. Without it, the sentence stays.
- PRD Q8 is closed by this feature.

## Open questions for the user
1. **Where does it run?** Options: (a) on every debate, (b) only when asked, for example a `--check-order` flag, or (c) only inside batches. The measured cost is about 1,000 tokens per debate (the judge call took 1,010 tokens in a real run), so **(a) roughly adds 50% to each debate** and cuts the default 20,000-token batch budget from about 10 debates to about 6 or 7. _Proposal: (b), opt-in._
2. **What is the official verdict when the two orders disagree?** Options: (a) keep the first-order verdict as the official one and flag the run as order-sensitive, (b) declare no clear winner, which breaks the rule that the judge always names exactly one winner. _Proposal: (a), so nothing about a normal verdict changes._
3. **If the swapped judge call fails after its retries,** should the run (a) still succeed with its official verdict and mark the check "not completed", or (b) end as exhausted? _Proposal: (a), because the check is extra information and shouldn't cost you a good debate._
4. **Should the swapped verdict change the for-win rate in a batch?** _Proposal: no. The for-win rate stays on the official verdict, and order sensitivity is reported separately._
5. **Tier:** do you agree with complex?

## Change log
- 2026-09-30: story drafted from backlog item 002. Draft, awaiting the user's answers and approval (gate 1).
