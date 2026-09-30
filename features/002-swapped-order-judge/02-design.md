# 002 — Swapped-Order Judge Check: Design

```
Status: Draft          (reopened 2026-09-30 for Amendment 1; was Approved)
Approved: pending      (re-approval needed)
Story: 01-story.md (reopened, needs re-approval first)
```

## Approach

After the normal verdict, add one more judge call about the **same two
arguments in the opposite order**, then compare the two answers. It is a
fourth stage, **S4 Decide (swapped)**, run only when `--check-order` is given.
It reuses the existing Judge configuration and the existing `decide` task text,
so the only thing that differs between the two judge prompts is the order of
the two arguments.

```
  Without --check-order:   S1 Propose -> S2 Oppose -> S3 Decide                 (unchanged)

  With --check-order:      S1 Propose -> S2 Oppose -> S3 Decide -> S4 Decide (swapped)
                                                          |             |
                                                    official verdict    reads S1 and S2 in
                                                                        swapped order; never S3
```

S4 depends on S1 and S2, not on S3. It runs after S3 only because stages run one
at a time. The official verdict is written before S4 starts, so nothing S4 does
can change or lose it.

### What "agree" means

The verdict's `winner` is a **side** (`for` or `against`), not a position. Let
W1 be the official winner (proposition argument read first) and W2 the swapped
winner (opposition argument read first).

| W1 | W2 | Result | Reading |
|---|---|---|---|
| for | for | **stable** | The proposition's argument won in both orders. |
| against | against | **stable** | The opposition's argument won in both orders. |
| for | against | **sensitive**, favored `first` | The judge picked the argument it read first, both times. |
| against | for | **sensitive**, favored `last` | The judge picked the argument it read last, both times. |

If S4 does not finish, the result is **not completed** and the run keeps its
official verdict.

### Data model

`run_debate(..., check_order: bool = False)` gains one argument. `RunResult`
gains `order_check`, which is `None` when the check was not requested:

```python
@dataclass
class OrderCheck:
    status: Literal["stable", "sensitive", "not_completed"]
    swapped: Optional[Verdict]                    # None when not completed
    favored: Optional[Literal["first", "last"]]   # only when sensitive
    reason: Optional[str]                         # only when not completed
```

### Building S4 (CrewAI mapping)

- S4 is built from the **existing `decide` task config** (same description and
  expected output), with `context=[oppose, propose]` (reversed) and the same
  verdict guardrail and 3 attempts. No second copy of the task text exists, so
  the two prompts cannot drift apart.
- It is appended to the crew's task list only when `check_order` is true.
- Its artifact is `decide_swapped.md`. The stage name `decide_swapped` is added
  to the stages `write_artifact` accepts. **Each run uses its own stage list:** three stages by default and four with `--check-order`, and the failing-stage lookup uses that list, so a run without the check can never report `decide_swapped` (Review, S2).
- The run report shows this stage as `swapped`, to keep its 8-character label column aligned (Review, S3).
- The CLI passes `check_order` to `run_debate` **only when `--check-order` is given**, so an unflagged run calls it exactly as today (Review, S4).
- The saver renders it as `# Verdict (arguments in swapped order)`, with the
  motion, the winner, the reasoning, and a line pointing to `decide.md` as the
  official verdict.

### Failure handling: S4 never fails the run (FR-9.9)

S1 to S3 keep their rule: an exhausted stage ends the run. S4 is the exception.
In every path that ends the run, if `decide` has completed and only
`decide_swapped` has not, the run is a **success** with
`order_check = not_completed` and a reason:

| What went wrong in S4 | Result |
|---|---|
| Guardrail exhausted after 3 attempts | Success, not completed, reason "the swapped verdict was rejected 3 times". |
| Wall-clock limit reached during S4 | Success, not completed, reason "the run's time limit was reached". |
| Writing `decide_swapped.md` failed after retries | Success, not completed, reason "the swapped verdict could not be saved". The check must never cost you a good debate, so a failed audit file does not fail the run. |
| S1, S2 or S3 fail | As today: exhausted or failed. S4 never starts. |

The official verdict is read from the completed `decide` task, not from S4.

### Memory and validation (design 04 vocabulary)

| | S4 Decide (swapped) |
|---|---|
| **Reads** | `motion`, `argument_for`, `argument_against`, in that reversed order. **Never** `verdict`. |
| **Writes forward** | `swapped_verdict`. Persisted as `decide_swapped.md`. |
| **Validation** | The same verdict guardrail as S3. |
| **Termination** | 3 attempts, 60 s per call. Exhausted means "check not completed", not a failed run. |
| **Human interface** | None. |

**Run limits:** the model-call cap rises from 9 to **12** when the check is on
(4 stages, 3 attempts each). The 5-minute wall clock is unchanged. Attempts and
tokens are recorded under the `decide_swapped` stage, so the run report (FR-7)
and the batch budget (FR-8.4) include them with no new accounting code.

## Interface

```
debate "<motion>" --check-order
debate --batch motions.txt --check-order [--budget 20000]
```

The flag is optional in both modes. Without it, output and behavior are exactly
as today. The examples below are **mockups**; the numbers are made up.

**Single debate, order-stable:**

```
$ debate "Cats make better pets than dogs" --check-order
Winner: Against
Order check: stable (the same side won with the arguments in either order)
Run 20260930-101500-cats-make-better-pets-than-dogs:
  propose  1 attempt    498 tokens (200 prompt + 298 completion)  output/.../propose.md
  oppose   1 attempt    490 tokens (198 prompt + 292 completion)  output/.../oppose.md
  decide   1 attempt    1,010 tokens (822 prompt + 188 completion)  output/.../decide.md
  swapped  1 attempt    1,004 tokens (816 prompt + 188 completion)  output/.../decide_swapped.md
  total    4 attempts   3,002 tokens (2,036 prompt + 966 completion)
```

**Order-sensitive:**

```
Winner: Against
Order check: order-sensitive (swapped verdict: For; the judge favored the argument it read last)
```

**Check not completed** (the run still succeeds):

```
Winner: Against
Order check: not completed (the swapped verdict was rejected 3 times)
```

**Batch progress lines** gain a short tag when the check is on. The motion is
shortened further to keep each line within 80 columns:

```
[1/6] Cats make better pets than dogs ............ Against  2,980 tokens  stable
[2/6] Dogs make better pets than cats ............ Against  2,975 tokens  sensitive
[3/6] Remote work is better than office work ..... Against  3,010 tokens  no check
```

`stable`, `sensitive`, and `no check` (not completed).

**Batch summary** gains, only when the check was requested: an `Order check`
column in the table, an `Order check` section, and a different closing
paragraph.

```markdown
| # | Motion                          | Outcome | Winner  | Order check       | Attempts | Tokens | Run folder |
|---|---------------------------------|---------|---------|-------------------|----------|--------|------------|
| 1 | Cats make better pets than dogs | success | Against | stable            | 4        | 2,980  | …          |
| 2 | Dogs make better pets than cats | success | Against | sensitive (last)  | 4        | 2,975  | …          |

## Order check
Checked 2 of 2 completed debates. Order-stable: 1. Order-sensitive: 1 (favored the
first-read argument: 0; the last-read: 1). Not completed: 0.

## Read this carefully
In 1 of 2 checked debates the winner changed when the arguments were swapped.
That is the reading order or ordinary variation between judge calls; this check
cannot separate the two. In the rest, the same side won in both orders. The
for-win rate above uses the official verdict only. These are rates, not a
finding of bias.
```

- If no debate in the batch completed a check (flag off, or all checks not completed), the closing paragraph is the existing FR-8.6 sentence.
- The **for-win rate** and **pair consistency** use the official verdict only (FR-9.10).
- Exit codes are unchanged. A check that is not completed does not change the exit code, because the run succeeded.

## Amendment 1 (2026-09-30): the swapped winner in the summary

Serves FR-9.11. It changes only the batch summary, and only when the check was
requested. Everything else in this design is unchanged.

**Table.** A `Swapped` column goes between `Winner` and `Order check`:

```markdown
| # | Motion                          | Outcome | Winner  | Swapped | Order check       | Attempts | Tokens | Run folder |
|---|---------------------------------|---------|---------|---------|-------------------|----------|--------|------------|
| 1 | Cats make better pets than dogs | success | Against | Against | stable            | 4        | 3,035  | …          |
| 2 | Dogs make better pets than cats | success | Against | For     | sensitive (last)  | 4        | 3,000  | …          |
| 3 | Some motion                     | success | For     | -       | not completed     | 3        | 2,100  | …          |
```

- `Swapped` is the swapped verdict's winner (`For` or `Against`), or `-` when the check did not complete or the debate did not finish.
- It appears only when the check was requested. A batch without `--check-order` is unchanged, byte for byte (the golden test still applies).

**Where the verdicts are.** The `Order check` section gains one sentence:

```
Each debate's two verdicts are in its run folder: `decide.md` (official) and `decide_swapped.md` (swapped).
```

**Data.** Nothing new: `OrderCheck.swapped` already holds the swapped verdict.

**Not included** (open question 1 in the story): quoting each verdict's reasoning
in the summary. The summary stays compact; the reasoning is in the two files.

**Tests** (added to the test table): the column appears only with the flag, in
the right position, with `-` for a check that did not complete and for an
unfinished or pending debate; the swapped winner matches the debate's swapped
verdict; the pointer sentence is present; the golden summary without the flag is
unchanged.

## Alternatives considered

| Alternative | Why not |
|---|---|
| A second crew run after the first, given the finished outputs | Cleaner failure isolation, but it re-implements context passing, so the two prompts could differ in more than order. Reusing one crew keeps the prompts identical (verified below). |
| A separate `judge_swapped` agent or task text in the YAML | Two copies of the judge instructions can drift apart, which would silently break the comparison. |
| Label the arguments ("Argument A/B", or For/Against) | Would help the judge map arguments to sides, but it changes the first judge's prompt and so the behavior of existing debates. The story requires that they stay exactly as they are. Not in v1. |
| Randomize the order of the official judge call instead of adding a check | Changes what the official verdict means. Out of scope. |
| Run the check on every debate | Rejected by the user: it would add about 50% to every debate. |
| Fail the run when S4 fails | Rejected by the user: the check is extra information. |

## Impact on existing work

Applied at delivery, in the same PR as the code:

- **PRD:** O9, FR-9.1 to 9.10, a rewrite of FR-8.6 for when check data exists, and Q8 closed.
- **Design 01 (stages):** S4 added, with its dependency on S1 and S2 only.
- **Design 02 (configurations):** no new configuration. The Judge serves S3 and S4, with the argument order as a per-call parameter.
- **Design 03 (capabilities):** one more stage value (`decide_swapped`) for `write_artifact`. Nothing else in the contract changes.
- **Design 04 (control):** S4's memory allowlist, the 12-call cap, the rule that S4 never fails the run, and the outer-loop step that compares the two verdicts.
- **Design 05 (framework):** no change. S4 is one more CrewAI task.
- **Code:** `run.py` (S4, `OrderCheck`, the failure rule), `artifacts.py` (stage value), `summary.py` (column, section, closing paragraph), `cli.py` (flag, check line, progress tag, report label), `batch.py` (passes the flag through, which needs no change beyond the existing `**run_kwargs`).
- **README and CLAUDE.md:** the flag and its cost.

## Agent system design (steps 1 to 5)

| Step | Decision |
|---|---|
| 1. Stages | New S4 Decide (swapped). Responsibility: a verdict on the same arguments in swapped order. Inputs: motion, S1, S2. Output: swapped verdict. Capability: write artifact (by the loop). Shape: still linear when it runs. |
| 2. Configurations | Judge reused. Least capability holds: no tools. |
| 3. Capabilities | `write_artifact` gains the stage value `decide_swapped`. Same derived path, same atomic write. |
| 4. Control | Memory allowlist above. Same validation. Same limits. **Different failure rule:** S4 exhausted does not end the run. New outer-loop step: compare W1 and W2 and build `OrderCheck`. |
| 5. Framework | Fourth CrewAI task built from the `decide` config with reversed `context`. Failure handling in application code. |

## Evidence from pre-design experiments (fake model, CrewAI 1.15.23)

Run on 2026-09-30 with a fake model that records each prompt, before writing this design.

| # | Question | Result |
|---|---|---|
| E1 | Does a task's `context` order control the order of the arguments in the judge's prompt? | **Yes.** `context=[propose, oppose]` puts the proposition first, `[oppose, propose]` puts the opposition first. |
| E2 | Does either judge see the other's verdict? | **No.** The swapped prompt does not contain the first verdict, and the first does not contain the second. |
| E3 | If S4 always fails validation, what survives? | S4 makes exactly 3 attempts and raises. The official `decide` output is kept and readable. |
| E4 | Are the two judge prompts identical apart from the order? | **Yes**, after normalizing the two argument texts. |

The context is passed as raw, **unlabeled** texts separated by a line of dashes,
so the judge infers which side each argument is on from its content (each
argument says which side it takes). This is the same as today.

## Risks

| Risk | How it is checked |
|---|---|
| **A flip is not proof of an order effect.** The judge is a language model, so its answer can vary between two calls even with identical input. A "sensitive" result means "the reading order or ordinary variation", and this check cannot separate the two. A "stable" result is stronger evidence. | Stated in the summary text and the story's wording. Only a same-order repeat could measure the noise (see Open decisions). |
| CrewAI's context order or isolation changes in a later version | Regression tests for E1, E2, E4 that fail if it does. |
| S4 failing costs the user a good debate | Tests for each failure path in the table above. |
| The judge mislabels which side an argument is on, in both orders, so "stable" hides an error | Accepted: the arguments state their side. Arguments are unlabeled, as today. |
| Extra cost surprises the user | Opt-in only. About 1,000 tokens per debate (the judge call measured 1,010). A checked batch fits about 6 or 7 debates in the default 20,000 budget. Documented in the README. |
| The flag changes the output of existing debates | Existing tests must pass unchanged, and new tests assert that without the flag no `order_check`, no extra column and no extra line appear. |
| Longer runs | About 3 to 4 seconds more per debate (real debates took 8 to 9 seconds). Well inside the 5-minute limit. |

## Test approach

All with the fake model; no network, no API key.

| Case | Expected |
|---|---|
| Check off | No S4 call, no `order_check`, no `decide_swapped.md`, and output identical to today. |
| Check on, same winner both orders | 4 model stages, `stable`, both artifacts written, official verdict unchanged. |
| Check on, winner flips (for then against) | `sensitive`, favored `first`; official verdict is the first. |
| Check on, winner flips (against then for) | `sensitive`, favored `last`. |
| Swapped prompt vs official prompt | Same text except the order of the arguments (E4). |
| Swapped prompt content | Contains both arguments, reversed, and never the first verdict (E1, E2). |
| S4 rejected 3 times | Run succeeds, `not_completed`, official verdict and its artifact intact, 3 S4 attempts. |
| Time limit during S4 | Run succeeds, `not_completed`. |
| `decide_swapped.md` cannot be written | Run succeeds, `not_completed`. |
| S3 fails with the flag on | Run is exhausted as today and S4 never starts. |
| Stats | Attempts and tokens appear under `decide_swapped` and in the run total. Max 12 calls. |
| CLI single run | The `Order check:` line for all three results, and the `swapped` report line. |
| CLI batch | `--check-order` reaches every debate; progress tags; exit codes unchanged. |
| Summary | Column, section and closing paragraph appear only when the flag was used and at least one check completed; otherwise the existing FR-8.6 sentence. For-win rate and pair consistency use official verdicts. |
| Batch without the flag | Summary and progress lines are byte-for-byte as today. |
| Swapped winner column (Amendment 1) | Shown only with the flag; `-` when the check did not complete or the debate did not finish; matches the swapped verdict; the pointer sentence to `decide.md` and `decide_swapped.md` is present. |
| Budget | The extra tokens count toward the batch budget. |

## Open decisions for review

**Settled by the user's approval of the design on 2026-09-30, as the design has them:** (1) accept the single-swap limit and word the summary honestly, with the same-order repeat recorded as backlog item 003; (2) keep the progress tags and the first/last-read detail. The original text follows for the record.

1. **Noise control.** The risk above means "sensitive" cannot prove an order effect. The complete fix is a third call: the same order again, to measure how often the judge changes its answer for no reason. It would add about 1,000 more tokens per debate. It is **not in the approved story**, so this design does not include it. Options: (a) accept the limit and word the summary honestly, as designed; (b) plan the same-order repeat as a separate backlog item (003). _Recommendation: (a) now, and (b) recorded as a backlog item._
2. **Batch progress tag** (`stable`, `sensitive`, `no check`) and the `favored first/last` detail go slightly beyond the story's wording. They are cheap and make the result readable. Keep them?

## Review (2026-09-30)

Checked against the approved story and against the code it will change
(`run.py`, `artifacts.py`, `cli.py`, `summary.py`, `batch.py`).

**What holds up**
- Every acceptance criterion in the story maps to a design element and a test row. The two that carry the most risk (the second answer is made without seeing the first, and unflagged debates stay exactly as they are) have evidence (E2) and explicit tests.
- The official verdict is written by S3's callback before S4 starts, so no S4 failure can lose it.
- Token and attempt accounting needs no new code: the usage meter already attributes by stage name, and `RunResult.total` sums every stage.
- `batch.py` needs no change. `run_batch` already forwards extra keyword arguments to each debate.
- No new agent configuration and no new CrewAI behavior beyond E1 to E4.

**Findings, and what was done**

| # | Severity | Finding | Disposition |
|---|---|---|---|
| S1 | High | The story promises to tell whether a verdict reflects the arguments or only the reading order. A single swap cannot fully do that: a flip may be ordinary variation between two judge calls. "Stable" is strong evidence; "sensitive" is ambiguous. | **Stated in the design and in the summary text.** The complete fix (a same-order repeat as a noise control) is outside the approved story, so it is put to the user as Open decision 1, with a proposal to record it as backlog item 003. |
| S2 | Medium | The run's stage list is a fixed tuple, `STAGES`, used by `write_artifact`, by the failing-stage lookup (`_next_stage`), and by the report. If `decide_swapped` is simply added to it, a run *without* the check could be told its next stage is `decide_swapped`. | **Fixed in this design:** the artifact contract knows all four stages, but each run uses its own list, three stages by default and four with `--check-order`. The failing-stage lookup uses the run's list. |
| S3 | Medium | The report prints each stage's label in an 8-character column, and `decide_swapped` is 14. It would misalign the whole report. | **Fixed:** the report shows this stage as `swapped` (as in the mockups). |
| S4 | Medium | Existing CLI tests replace `run_debate` with a fake that takes only `(motion, output_dir)`. If the CLI always passed `check_order=False`, those fakes would break, and it would also mean the unflagged path is not literally unchanged. | **Fixed:** the CLI passes `check_order` **only when the flag is given**. Recorded as an implementation rule for the plan. |
| S5 | Medium | The rule "S4 never fails the run" has to hold on every ending path: an exception, the wall-clock timeout, and a failed write of the swapped artifact. The current code has separate branches for the first two, and write errors are handled after the crew stops. | **Recorded** in the failure table and test rows. The plan must implement it once, in a shared helper, not three times. |
| S6 | Low | The mockups use "first-read" and "last-read". The story only says "order-sensitive". | Kept as extra detail, raised as Open decision 2. |
| S7 | Low | With the flag on, the default 20,000-token batch budget covers about 6 or 7 debates, not 10, and the summary's "too few runs" line will nearly always appear. | **Documented** in Risks and to go in the README. No design change: a larger `--budget` is the answer. |

**Still true after the fixes:** no new reasoning-core configuration, no new tool
for the model, and no change to how S1 to S3 behave.

## Change log
- 2026-09-30: **reopened for Amendment 1** (the swapped winner in the summary). Status back to Draft; re-approval needed.
- 2026-09-30: approved by the user (gate 2). Both open decisions settled as designed. Backlog item 003 (same-order repeat as a noise control) recorded in the feature index.
- 2026-09-30: design review. Findings S1 to S7; S2, S3, S4 applied to the design, S1 and S6 put to the user as open decisions, S5 and S7 recorded. Still Draft, pending gate 2.
- 2026-09-30: drafted from the approved story, with pre-design experiments E1 to E4. Draft, pending review and gate 2.
