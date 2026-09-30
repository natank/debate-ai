# Debate AI — Product Requirements Document

_Status: Draft v0.1 · 2026-09-29_

**Sources:**
- [1] `_docs/config/agents.yaml`: agent definitions (`debater`, `judge`)
- [2] `_docs/config/tasks.yaml`: task definitions (`propose`, `oppose`, `decide`)
- [3] `_docs/agentic-systems-and-workflows.md`: the development process (applied after this PRD)

---

## 1. Summary

Debate AI takes a **motion** (a debatable statement, e.g. "Social media does
more harm than good") and runs a short, structured debate between AI agents:

1. A debater argues **for** the motion.
2. A debater argues **against** the motion.
3. A judge reads both arguments and **decides which side is more
   convincing, and why**.

Each step writes its result to a Markdown file, so the whole debate can be
read afterwards.

## 2. Problem and purpose

When you are weighing a contested question, the strongest case for each side
is rarely written down next to the other one, and you seldom get an impartial
view of which case is stronger. Debate AI produces both:

- the best concise case **for** and **against** a motion, written independently, and
- a reasoned verdict based only on the arguments, not on the judge's own views [1: judge.backstory].

## 3. App objectives

Derived from [1] and [2].

| # | Objective | Source |
|---|---|---|
| O1 | Accept any motion in natural language and use it as the single input for the whole debate. | `{motion}` in every agent and task [1][2] |
| O2 | Produce a **clear, concise, convincing argument in favor of** the motion. | `propose` [2]; debater goal and backstory [1] |
| O3 | Produce a **clear, concise, convincing argument against** the motion. | `oppose` [2]; debater goal and backstory [1] |
| O4 | Produce an **impartial verdict**: which side is more convincing, and why, judged only on the arguments presented. | `decide` [2]; judge role, goal and backstory [1] |
| O5 | Keep every debate output as a readable artifact. | `output_file` on every task [2] |
| O6 | Run on a configurable LLM, `openai/gpt-5.4-mini` by default. | `llm` on both agents [1] |
| O7 | Report what each run cost: the attempts used and the tokens spent, per stage and in total. | Not in [1] or [2]. Added 2026-09-30 from NFR-4 and the step 4 retry limits. **Documented after it was first implemented**, which broke the process in [3]. |
| O8 | Measure whether the judge favors a side, by running many motions in one batch and summarizing the results. | Not in [1] or [2]. Serves the side-bias success metric and NFR-1. Delivered by feature 001 (`features/001-batch-and-bias/`). |
| O9 | Tell whether a verdict depends on the order in which the arguments are presented to the judge. | Not in [1] or [2]. Follows from Q8 and FR-8.6. Delivered by feature 002 (`features/002-swapped-order-judge/`). |

**Success criterion (from [1]):** a debater succeeds when the judge agrees
with its argument. The product succeeds when both sides get a fair,
strong case and the verdict is justified by those cases.

## 4. Users and use cases

| User | Use case |
|---|---|
| Student / debate practitioner | See strong opening cases for both sides of a motion before preparing their own. |
| Decision-maker | Stress-test a proposition by seeing its best counter-argument and an impartial assessment. |
| Curious reader | Explore a contested topic in a balanced, compact format. |

## 5. Scope

### In scope (v1)
- A single motion per run.
- One round: one proposition argument, one opposition argument, one verdict.
- Two agent roles (debater, judge) and three tasks (propose, oppose, decide), as defined in [1][2].
- Markdown output files per task.
- Configuration through YAML (agents and tasks) and environment variables (API key, model).

### Out of scope (v1)
- Multi-round debate (rebuttals, cross-examination).
- More than two sides, or teams of debaters.
- Web research or fact-checking tools. The agents reason from model knowledge only.
- Human participation as a debater.
- Scoring rubrics, multiple judges, or panels.
- Persisting debates across runs beyond the output files.

## 6. Functional requirements

### FR-1: Motion input
- FR-1.1 The user supplies a motion as free text.
- FR-1.2 The same motion is interpolated into every agent and task (`{motion}`).
- FR-1.3 An empty motion is rejected before any model call.

### FR-2: Proposition argument (`propose`)
- FR-2.1 Performed by the `debater` agent.
- FR-2.2 Output: a clear, concise argument **in favor of** the motion.
- FR-2.3 Written to `output/propose.md`.

### FR-3: Opposition argument (`oppose`)
- FR-3.1 Performed by the `debater` agent (same configuration as FR-2, opposite side).
- FR-3.2 Output: a clear, concise argument **against** the motion.
- FR-3.3 Written to `output/oppose.md`.

### FR-4: Verdict (`decide`)
- FR-4.1 Performed by the `judge` agent.
- FR-4.2 Inputs: the motion, the proposition argument, and the opposition argument.
- FR-4.3 Output: which side is more convincing, and why.
- FR-4.4 The verdict must be based on the arguments presented, not on the judge's own opinion of the motion.
- FR-4.5 Written to `output/decide.md`.

### FR-5: Sequence
- FR-5.1 `propose` and `oppose` both complete before `decide` starts.
- FR-5.2 The run finishes when `decide.md` is written. If any task fails, the run reports which task failed and does not produce a verdict.

### FR-6: Configuration
- FR-6.1 Agents and tasks load from `agents.yaml` and `tasks.yaml`, not hard-coded.
- FR-6.2 The LLM is set per agent (`llm`); the API key comes from the environment (`.env`), never from the repo.

### FR-7: Run report _(added 2026-09-30)_
- FR-7.1 Every run ends with a report, whatever the outcome, including a run that failed or was exhausted.
- FR-7.2 For each stage that started, the report gives the **attempts** used and the **tokens** spent (prompt, completion and total).
- FR-7.3 The report gives a total across stages.
- FR-7.4 An attempt is a reply that reached validation. A rejected reply that was retried counts as another attempt. A call that ended in an error before validation is not an attempt, but its tokens count toward its stage.
- FR-7.5 The report lists each artifact's path next to its stage.
- FR-7.6 A run rejected before any model call (an empty motion) has no stages, so it has no usage lines.
- FR-7.7 Cost is reported in tokens, not currency. Prices change, and a price table would have to be kept current.

### FR-8: Batch run and bias summary _(feature 001)_
- FR-8.1 The user can run a batch: a list of motions read from a text file, one debate per motion, run one after another.
- FR-8.2 A line may declare a **pair** of opposite motions (for example "Remote work is better than office work | Office work is better than remote work"). Pairs let the summary test consistency (FR-8.5).
- FR-8.3 Each debate in a batch is an ordinary run (FR-1 to FR-7): same limits, same artifacts, same report. A failed or exhausted run is recorded and the batch continues.
- FR-8.4 The batch stops early, and says so, once the tokens spent have reached a budget (default 20,000), before starting the next debate. Motions not started are listed as skipped. The budget is checked between debates, so a batch can pass it by at most one debate.
- FR-8.5 The batch writes a summary with:
  - one row per motion: outcome, winner (for or against), attempts, tokens, and the run folder;
  - the **for-win rate** over completed runs;
  - for each pair, whether the judge was **position-consistent** (it picked the same position both times, so the winner flipped from for to against or the reverse) or **not** (it picked the same side of the debate both times);
  - the totals from FR-7.
- FR-8.6 When no order check was run (FR-9), the summary states that a skew toward one side cannot be told apart from an ordering effect, so it reports a rate and does not assert bias. When the order check was run, the summary reports what it showed and what it cannot show (FR-9.6).
- FR-8.7 A batch with an empty file, or a file with no usable motions, is rejected before any model call.
- FR-8.8 While a batch runs, one progress line is printed as each debate finishes, showing its position in the batch, the motion, its winner or outcome, and its tokens. A final line gives the completed count, attempts, tokens and the summary path.

### FR-9: Order check _(feature 002)_
- FR-9.1 A debate can be run with an order check, requested with `--check-order` (for a single motion, or for every debate in a `--batch`). After the verdict, the judge is asked again about the same two arguments with their order swapped, without seeing the first verdict. Without the flag, no check is made.
- FR-9.2 The run records both verdicts and whether the winning side's **argument** was the same in both orders (**order-stable**) or not (**order-sensitive**). For a sensitive result it records whether the judge favored the argument it read first or last.
- FR-9.3 The swapped verdict is saved as an artifact (`decide_swapped.md`).
- FR-9.4 The extra call's attempts and tokens are included in the FR-7 report and the FR-8.4 budget.
- FR-9.5 The extra call has the same attempt limit and validation as the first judge call.
- FR-9.6 The batch summary reports the order-stable and order-sensitive counts, separately from the for-win rate. It says that a change of winner is the reading order or ordinary variation between judge calls, and that the check cannot separate the two.
- FR-9.7 Without the order check, behavior is unchanged.
- FR-9.8 The official verdict is always the first-order verdict (FR-4). If the two orders disagree, the run is flagged order-sensitive and the official verdict is not changed.
- FR-9.9 If the swapped judge call fails after its retries, the run does not fail: it keeps its official verdict and the order check is reported as **not completed**. The same holds if the time limit is reached during the check or the swapped artifact cannot be saved.
- FR-9.10 The FR-8.5 for-win rate is based on the official verdict only. Order sensitivity is reported separately (FR-9.6).

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Fairness | Both sides get the same agent configuration and the same instructions, apart from which side they take. |
| NFR-2 Impartiality | The judge is told not to use its own views. Its output must cite the arguments it is weighing. |
| NFR-3 Conciseness | Each argument is concise, per `expected_output` [2]. A target length will be set in design. |
| NFR-4 Cost | One run uses one model call per task at minimum (3 total), on a small model by default, and at most 9 (12 with the order check, FR-9). FR-7 makes the actual cost visible. The order check adds about 1,000 tokens per debate. |
| NFR-5 Reproducibility | Output files hold enough to audit a run: the motion, both arguments, and the verdict. |
| NFR-6 Secrets | The API key is loaded from `.env`, which is excluded from version control. |

## 8. Success metrics

| Metric | Target (v1) |
|---|---|
| Run completion rate (valid motion → three output files) | ≥ 95% |
| Verdict names exactly one winning side | 100% |
| Tokens per debate (from the FR-7 report) | Tracked over a sample of motions. No target set yet. |
| Verdict gives reasons that refer to the actual arguments | Checked by manual review on a sample set |
| Side bias: across a balanced motion set, proposition wins ≈ opposition wins | No strong skew toward either side. Measured with the FR-8 batch summary. |
| Order sensitivity (from the FR-9 summary, when `--check-order` is used) | Tracked over a sample of motions. No target set yet. |

## 9. Relation to the development process [3]

Development follows the five-step design process in [3]. This PRD is its
"Requirements" input. The expected mapping is:

| [3] step | Initial input from this PRD |
|---|---|
| 1. Stages and sequence | Stages = propose, oppose, decide (FR-2 to FR-4). Shape: **parallel, then join** (FR-5.1). |
| 2. Reasoning-core configurations | `debater` (serves propose and oppose) and `judge` (serves decide) [1]. |
| 3. Capability contracts | No external tools in v1. The only side effect is writing output files. |
| 4. Control relationships | Validation of each output (e.g. the verdict names a side), termination and retry limits, and where the motion enters memory (outer loop, FR-1). |
| 5. Framework mapping | The YAML shape of [1][2] matches **CrewAI** (agents and tasks with `role/goal/backstory`, `description/expected_output/output_file`). |

Note on objective 2 in [3]: the steps here are fixed in advance
(propose → oppose → decide), so v1 is closer to a structured multi-agent
workflow than an open-ended agentic system. That fits a debate, and it keeps
the design simple to validate. The [3] process still applies to the
per-stage design (validation, termination, human interface).

## 10. Open questions

| # | Question | Proposed default |
|---|---|---|
| Q1 | Does the opposition see the proposition's argument? (CrewAI's sequential process passes earlier task outputs forward by default, which gives the opposition an unfair advantage.) | No: both sides argue independently (parallel), per NFR-1. |
| Q2 | What is the user interface: CLI, web app, or both? | CLI first (`debate "<motion>"`). |
| Q3 | Should the verdict follow a fixed structure (e.g. `winner: for/against` plus reasoning) so it can be validated automatically? | Yes: a structured header plus free-text reasoning. |
| Q4 | Should output files be overwritten each run, or kept per debate? | Keep per debate: `output/<timestamp-or-slug>/…`. |
| Q5 | What is the target length for arguments? | ~200–300 words each. |
| Q6 | `.env.example` currently holds variables from another project (`PDPA_*`, `MODEL_NAME=gpt-4o-mini`). Which should replace them? | `OPENAI_API_KEY` plus an optional model override matching [1]. |
| Q7 | The README cites `_docs/agets.yaml`, but the files are at `_docs/config/agents.yaml` and `_docs/config/tasks.yaml`. | Update the README paths. |
| Q8 | The judge always receives the proposition argument first and the opposition second, so a for-win skew could come from the debaters or from that order. Should the judge also be run with the order swapped? | **Delivered by feature 002:** `--check-order` (FR-9), opt-in. A single swap cannot separate the reading order from ordinary variation between judge calls, so the summary says so. A same-order repeat to measure that variation is backlog item 003 in `features/README.md`. |
| Q9 | What should the default batch token budget be? | **Decided:** 20,000 tokens, about 10 debates at the roughly 2,000 measured per debate. Overridable with `--budget`. |
