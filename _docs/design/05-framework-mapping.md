# Design Step 5 — Framework Mapping

_Status: Draft · 2026-09-29_
_Input: design steps 1–4 (`_docs/design/`), `_docs/config/agents.yaml`, `_docs/config/tasks.yaml`._
_Process: `_docs/agentic-systems-and-workflows.md`, Design process, Step 5._

## 1. Candidates and evidence

| Candidate | Why it is a candidate | Evidence in this document |
|---|---|---|
| **CrewAI** | The existing YAML files are already in its shape (`role/goal/backstory`, `description/expected_output/agent/output_file`). | Checked against docs.crewai.com (Tasks, Agents pages) on 2026-09-29. Facts marked **[docs]**. |
| **LangGraph** | An explicit graph with shared state fits fork and join. | From general knowledge, **not checked in this session**. Marked **[unverified]**. |
| **Hand-rolled** | The design is three model calls and a join. | No framework claims. |

CrewAI facts used below, from the docs:

- Sequential process: *"the output of one task is automatically relayed into the next one"*, and `context` (a list of tasks) sets which outputs a task uses.
- `async_execution` (default `False`): the crew does not wait for that task before continuing.
- `guardrail` / `guardrails`: validated before the next task. On failure the error goes back to the agent and the task is retried up to `guardrail_max_retries` (default 3).
- `output_pydantic`: output conforms to a Pydantic model, accessed as `result.pydantic`.
- `output_file` (with `create_directory`, default `True`): stores task output at a path. The docs say nothing about overwrite behavior.
- Agent: `max_iter` (default 20), `max_execution_time` (optional), `max_retry_limit` (default 2, retries on error), `allow_delegation` (default `False`), `tools` (default empty). The docs summary did not state a default for `memory`.

## 2. The mapping table

Who owns each relationship. **F** = framework handles, **A** = application code.

| Relationship | CrewAI | LangGraph [unverified] | Hand-rolled |
|---|---|---|---|
| 1. Reasoning core call | **F.** Agent plus Task build and send the call. `llm` per agent. | **F/A.** Nodes call a model client the application chooses. | **A.** Direct SDK call. |
| 2. Capability dispatch | Not needed. No tools (step 2). | Not needed. | Not needed. |
| 3. Memory (scoped) | **F by default, wrong default.** Earlier output flows forward unless `context` says otherwise. **A** must set scoping. | **F.** State object plus per-node reads and writes. Scoping is explicit by design. | **A.** A plain dict with per-stage allowlists. |
| 4. Validation | **F** for the retry mechanism (`guardrail`, `output_pydantic`). **A** writes the check functions. | **A.** Checks and retry edges are written as graph logic. | **A.** |
| 5. Termination | **F** partly: `guardrail_max_retries`, `max_execution_time`. **A** for run-level limits (9 calls, 5 minutes) and the three outcomes. | **F** for a recursion limit [unverified]. **A** for the rest. | **A.** |
| 6. Human interface | Not needed in v1 apart from error reporting. **A.** | Not needed in v1. **A.** | **A.** |

Fork and join is not a numbered relationship, but it is the shape from
step 1. CrewAI offers `async_execution` and `context` for it. LangGraph
models it directly as parallel edges into a join node [unverified].
Hand-rolled uses two concurrent calls and a wait.

## 3. Choice: CrewAI, conditional on one test

**Choice.** CrewAI, because the YAML already exists in its shape, the design
needs only its simplest features (agents, tasks, a guardrail, a structured
output), and it absorbs the model calls, prompt assembly and retry-on-reject.

**Condition.** The design's one non-negotiable rule is that S2 never sees
S1's output (NFR-1, step 4 scoping). CrewAI's default sends earlier output
forward, so this must be **proven by a test before anything else is built**
(section 6, test 1). If it cannot be guaranteed, use hand-rolled: the design
is small enough that a plain Python orchestrator costs little, and it makes
the scoping rule true by construction.

**Why not LangGraph.** It would fit the shape, but it replaces the existing
YAML with graph code and adds a dependency for three model calls. Not ruled
out; revisit if the design grows loops (rebuttal rounds, human review).

## 4. Mapping the design onto CrewAI

| Design element | CrewAI element | Notes |
|---|---|---|
| Configuration: Debater | `debater` agent in `agents.yaml` | One agent serves S1 and S2. `allow_delegation=False`, no tools. |
| Configuration: Judge | `judge` agent | Same. |
| S1 Propose | `propose` task | `context=[]` intended, to be proven by test 1. Runs async. |
| S2 Oppose | `oppose` task | `context=[]` intended. Runs async. |
| S3 Decide | `decide` task | `context=[propose, oppose]`. |
| Side parameter | `{side}` input, alongside `{motion}` | Replaces the free text in the task description (step 2, section 4). |
| Verdict shape | `output_pydantic` on `decide` | `winner` restricted to `for` or `against`, plus `reasoning`. |
| Shape validation (step 4) | `guardrail` functions | Word count for S1 and S2. Reasoning length for S3. |
| Attempts (step 4: 3) | `guardrail_max_retries = 2` | The framework default of 3 would give 4 attempts. |
| Per-call timeout (60 s) | `max_execution_time` | To be confirmed in test 3. |
| No tool loop | `max_iter` set low | Default is 20, which is pointless with no tools. |
| Artifact writing (step 3) | **Application `write_artifact`, not `output_file`** | See below. |

**Why not `output_file`.** Step 3 requires a derived path per run
(`output/<run_id>/<stage>.md`), an atomic replace, and Markdown rendering
by the control loop. The YAML uses fixed paths (`output/propose.md`), and the
docs do not describe overwrite behavior. The application writes the files
from the task results, and `output_file` is removed from `tasks.yaml`.

## 5. What the application must implement itself

This is the starting list for detailed design.

1. **Outer loop entry.** Validate the motion (non-empty), generate `run_id`,
   place `motion` and `run_id` in memory before any task starts (step 4, 2.1).
2. **Scoped memory enforcement** for S1 and S2 (test 1 decides how).
3. **Guardrail functions:** word-count check for arguments, `winner` and
   reasoning-length check for the verdict (step 4, section 1).
4. **`write_artifact`:** derived path, temporary-file-then-rename, Markdown
   rendering, retry on `WriteFailed` up to 3 times without re-calling the
   model (steps 3 and 4).
5. **Run-level termination:** cap of 9 model calls, 5-minute wall clock,
   and the success, exhausted and failed outcomes with a report naming the
   failing stage (step 4, section 3).
6. **Branch-failure handling:** if one of S1 and S2 is exhausted, do not run
   S3, and keep the other branch's valid artifact (step 4, 2.3). Crew-level
   failure behavior must be confirmed in test 4.
7. **Error reporting** to the user: stage, reason, and which artifacts exist.
8. **`agents.yaml` and `tasks.yaml` edits** listed in step 2, section 4
   (side parameter, typo, verdict shape) and the removal of `output_file`.
9. **Model and token cap** per configuration. The YAML currently sets
   `openai/gpt-5.4-mini` for both. Confirm that name is valid and set the
   token cap for the length target.

## 6. Tests to run before building on this mapping

These are unverified assumptions. Each one can change the choice above.

| # | Test | Passing result | If it fails |
|---|---|---|---|
| 1 | **Isolation.** Run S1 and S2 with distinctive markers in S1's output. Inspect the exact prompt S2 sent to the model. | S2's prompt contains neither S1's text nor its marker, in async and non-async modes. | Use hand-rolled orchestration. |
| 2 | **Shared agent state.** The `debater` agent serves both tasks. Check that the second task does not receive the first task's content through agent memory. | No leakage. `memory` explicitly off. | Use two agent instances, or hand-rolled. |
| 3 | **Limits.** Confirm `max_execution_time` interrupts a slow call, and that `guardrail_max_retries = 2` gives exactly 3 attempts. | Both hold. | Enforce timeout and attempts in application code. |
| 4 | **Failure in one async branch.** Make S1 always fail its guardrail. Observe what happens to S2's result and to `decide`. | The failure is reported, S3 does not run, and S2's output is retrievable. | Wrap each task in application code. |
| 5 | **`output_pydantic` on the judge.** A reply outside the `for` or `against` values is rejected and retried, not passed through. | Rejected and retried within the attempt limit. | Validate `winner` in the guardrail instead. |

### Result: test 1 (isolation) — passed

Run with a recording fake LLM that captures the exact messages of every call,
so no API key or network is needed.

- With `context=[]` on `propose` and `oppose`, S2's prompt never contains
  S1's marker, and S1's never contains S2's. This holds with `propose` run
  synchronously and with `async_execution=True`.
- Control: `decide` receives both markers, so outputs do propagate.
- Control: without `context=[]`, S1's output does appear in S2's prompt.
  This confirms the CrewAI default and shows the test can fail.
- Test 2 (shared agent state) is partly covered: one `debater` agent served
  both tasks and no leakage appeared. It was run with CrewAI's default agent
  memory settings and no explicit `memory` setting, so it is not closed.
- CrewAI is therefore kept as the choice, with `context=[]` required on S1
  and S2.

## 7. Output of step 5

- Mapping table for three candidates (section 2).
- Choice and its condition (section 3).
- Design-to-CrewAI mapping (section 4).
- Application-owned list (section 5) and pre-build tests (section 6).

## 8. Checklist

- [x] The framework mapping names every relationship the application must implement itself (section 5).
- [ ] Tests 1–5 have been run. Until then this mapping is provisional.
      Test 1: **passed** (2026-09-29, `tests/test_isolation.py`, CrewAI 1.15.23). Tests 2–5 pending.

## 9. Design status

Steps 1–5 are done. Steps 1–4 are consistent with the PRD, and this step leaves
their content unchanged. The next phase is detailed design and implementation.
Test 1 should be the first thing built.
