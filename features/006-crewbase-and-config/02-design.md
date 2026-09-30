# 006 — Adopt @CrewBase and Move the Config into the Source: Design

```
Status: Approved
Approved: natank (the user), 2026-09-30
Story: 01-story.md (Approved, gate 1 passed)
```

## Summary

The fallback in the story was **not needed**: a `@CrewBase` version of the crew
was built as a prototype and tested before this design was written. The whole
existing suite passes against it, and the prompts, artifacts, stats and results
it produces are identical to today's. This is a structural refactor with no
user-visible change.

## Approach

**1. Move the config.** `git mv _docs/config/agents.yaml _docs/config/tasks.yaml
src/debate_ai/config/`. Content unchanged.

**2. A new module `src/debate_ai/crew.py`** holds one `@CrewBase` class,
`DebateCrew`, in place of the `_build_crew` function in `run.py`:

```python
@CrewBase
class DebateCrew:
    def __init__(self, motion, config_dir, llm_factory, saver, cancelled, stats, check_order): ...
    @agent  def debater(self): ...        # one Agent, shared by propose and oppose, as today
    @agent  def judge(self): ...
    @task   def propose(self): ...        # context=[] : blind to the other side
    @task   def oppose(self): ...         # context=[] : blind to the other side
    @task   def decide(self): ...         # context=[propose, oppose]
    @task   def decide_swapped(self): ... # same YAML entry as decide, context=[oppose, propose]
    @crew   def crew(self): ...           # tasks listed explicitly: 3, or 4 with check_order
```

The class file's folder is `src/debate_ai/`, so `CrewBase`'s default of
`config/agents.yaml` and `config/tasks.yaml` finds the moved files. That is the
convention the framework expects.

**3. `run_debate` is unchanged in shape.** It builds the class, takes the crew,
the stage-to-task map and the usage meter from it, and carries on exactly as
now. `run_debate` keeps its signature and its result.

### How each thing that a plain class cannot hold is handled

| Need | How |
|---|---|
| Per-run values (motion, run id, cancel flag, artifact saver, stats) | Passed to `__init__`. `@CrewBase` creates the instance first and loads config and builds agents after it, so `__init__` values are visible to every agent and task method. |
| Swappable model for tests | `__init__` takes `llm_factory`. Each `@agent` builds `Agent(**{**yaml_config, "llm": factory(...)}, ...)`, exactly as `_build_crew` does. The YAML `llm:` string is never turned into a client, so tests need no API key. |
| Optional fourth task | `decide_swapped` is always defined; the `@crew` method adds it to the task list only when `check_order` is true. |
| Two tasks from one YAML entry | `decide` and `decide_swapped` both use `tasks_config["decide"]`. They are separate `Task` objects, as now. |
| Usage meter and cancel-aware guardrails | Same code as today, as methods on the class. The meter is created in `crew()` once both agents exist. |
| A different config folder (tests) | `config_dir=None` uses `CrewBase`'s default lookup beside the class. If a folder is given, it is set as absolute paths on the instance before initialization. |

### Where the shared helpers go

`run.py` will import `DebateCrew`, and `DebateCrew` needs a few things that live in
`run.py` today. To avoid a circular import, these small pieces move into `crew.py`
with **no change to their code**: `MAX_ATTEMPTS`, `RunCancelled`, `StageStats`, the
usage meter, and the two verdict renderers. `run.py` imports them, so
`from debate_ai.run import StageStats` and every other existing import still work.

## Evidence from the prototype (2026-09-30, CrewAI 1.15.23)

A `@CrewBase` class was written in a scratch folder and tested against the current code.

| # | Question | Result |
|---|---|---|
| E1 | Does the existing suite pass when the `@CrewBase` class builds every crew? | **Yes.** All 195 tests pass. 41 crews were built through the class during the run, and the tests ran with **no API key set**. |
| E2 | Are the outputs identical? | **Yes.** With the same fake model, with the order check off and on: the prompts sent to the model, the artifact files, the per-stage stats, and the result (outcome, verdict, order check) were identical to the current code's. |
| E3 | Can the class take constructor arguments? | Yes. The instance is created first; config loading and agent building happen after `__init__`. |
| E4 | Does the default config lookup work? | Yes. `config/agents.yaml` and `tasks.yaml` beside the class file load correctly from any working directory. An absolute path also works, as used by tests. |
| E5 | Is anything shared between two instances? | No. Each instance loads its own config dictionaries and builds its own agents. |
| E6 | Do propose and oppose share one debater agent, as today? | Yes, one `Agent` object. |
| E7 | What if `tasks.yaml` names an agent with no `@agent` method? | Instantiation fails with a `KeyError`. Every agent named in the YAML needs a method. A test will guard this. |
| E8 | Is the YAML `llm:` string touched? | No. It stays a plain string, and our factory supplies the model. |
| E9 | Does a built wheel contain the config? | Yes, as `debate_ai/config/agents.yaml` and `tasks.yaml`, with no `pyproject.toml` change. |

## What this costs and what it gains (stated plainly)

**Gains:** the framework's standard layout, so a CrewAI user finds agents, tasks
and config where they expect; the config becomes part of the packaged code (E9),
which fixes a real bug (the old lookup breaks when installed); one clear place
(`crew.py`) that says how the crew is assembled, apart from the outer loop.

**Costs:** a metaclass with hidden behavior (it loads config and builds agents
during instance creation); more indirection than a plain function; closer
coupling to CrewAI's decorator API; a small module reshuffle to avoid a circular
import. There is **no user-visible benefit**. That is why the parity evidence
above matters more than usual.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep the hand-built crew and only move the config (the earlier simple draft) | The fallback the user approved. Not needed, because nothing in the story failed. Still available if the implementation finds a problem. |
| Put the class inside `run.py` | No circular import and no helper move, but `run.py` (already the outer loop) would also hold the crew definition. Considered; see Open decision 1. |
| Use `@llm` factory methods and a name in the YAML | Would change the YAML content, which the story says must stay byte for byte. |
| Let `@crew` use `self.agents` and `self.tasks` | Would include `decide_swapped` even when the check is off. Explicit task lists keep the check strictly opt-in. |
| Pass `config=` to `Agent` and `Task` | The prototype passes the YAML fields as keyword arguments, exactly as the current code does, so behavior is identical by construction. |

## Impact on existing work

- **Code:** new `src/debate_ai/crew.py`; `run.py` loses `_build_crew` and the moved helpers and imports them; `tests/test_isolation.py` points at the new config folder.
- **Config:** two files move; content unchanged.
- **Tests:** all 195 must pass unchanged, apart from the config path in `test_isolation.py`.
- **Documents:** design 05 records the decision reversal; the path is updated in README, CLAUDE.md, the PRD's source references, design 02, and the feature 002 story. Requirements: none change.

## Agent system design (steps 1 to 5)

Steps 1 to 4 (stages, configurations, capabilities, control) are **unchanged**:
same stages, same isolation rule, same limits, same failure rules. Step 5
(framework mapping) changes in one row: the orchestration unit is now a
`@CrewBase` class instead of hand-built objects. The relationships the
application owns (memory scoping, validation, termination, artifacts, the run
report) are still application code.

## Risks

| Risk | How it is checked |
|---|---|
| A subtle behavior change | The whole existing suite, unchanged, plus a parity test comparing prompts, artifacts, stats and results against a recorded baseline. |
| The isolation rule breaks | Existing tests, and a test that the class builds `propose` and `oppose` with empty context and `decide_swapped` with the reversed one. |
| A future YAML edit names an agent with no `@agent` method | A guard test (E7). |
| The lookup depends on where the code runs | The default lookup is tested from a different working directory, and a wheel is built and inspected (E4, E9). |
| Code under `src/` reads from `_docs` again | A test that nothing under `src/` mentions `_docs`. |
| A CrewAI upgrade changes `@CrewBase` | The decorator API is public. The parity test would fail loudly. |
| Circular import | The helper move above; a test imports `debate_ai.run` and `debate_ai.crew` in both orders. |
| A stale document keeps the old path | A repository search for `_docs/config` after the change; only sentences about history may remain. |

## Test approach

All with the fake model; no network, no API key.

| Case | Expected |
|---|---|
| Existing suite | All 195 pass, unchanged (apart from one path). |
| Parity | For the order check off and on, prompts, artifacts, stats and result equal a recorded baseline of the current behavior. |
| Class structure | `DebateCrew` is a `@CrewBase` class; every agent named in `tasks.yaml` has an `@agent` method; the crew has 3 tasks without the check and 4 with it. |
| Isolation wiring | `propose` and `oppose` have empty context; `decide` reads propose then oppose; `decide_swapped` reads oppose then propose. |
| Config location | Both files exist in `src/debate_ai/config/` and parse with the expected top-level keys; nothing under `src/` mentions `_docs`; the default lookup works from another working directory. |
| Per-run state | Two crews built in a row share no agents or config. |
| Imports | `debate_ai.run` and `debate_ai.crew` import in either order; `from debate_ai.run import StageStats, RunResult, run_debate` still works. |
| Packaging (once, recorded) | A wheel built from the tree contains `debate_ai/config/agents.yaml` and `tasks.yaml`. |
| Real debate (once, with the user's go-ahead) | One `--check-order` debate produces the same kind of output as before. |

## Open decisions for review

**Settled by the user's approval of the design on 2026-09-30, both as recommended:** (1) a separate `crew.py` with the small helper move; (2) `config_dir=None` uses `@CrewBase`'s default lookup beside the class. The original text follows for the record.

1. **Module layout.** A separate `crew.py` with a small helper move (recommended: a clear boundary between how the crew is assembled and the outer loop), or the class inside `run.py` (nothing moves, but `run.py` grows).
2. **Config folder default.** `config_dir=None` uses `CrewBase`'s own default lookup beside the class (recommended: it exercises the framework convention, which is the point of the feature), or keep an explicit path constant and always pass it.

## Review (2026-09-30)

Checked against the approved story, the prototype, and the code that will change.

**What holds up:** every acceptance criterion maps to a design element and a test row; the fallback condition never triggered; the prototype's parity result covers the criterion that carries the most risk (behavior unchanged); `run_debate` keeps its signature; the outer loop is not touched.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| F1 | Medium | `run.py` will import the class and the class needs helpers defined in `run.py`, which is a circular import. The prototype hid this by importing `debate_ai.run` as a module. | **Fixed in the design:** a small helper move into `crew.py`, with re-exports from `run.py` so no existing import breaks. An import test guards it. |
| F2 | Medium | The prototype always set absolute config paths, so it never exercised the framework's default lookup. The feature's point is to use that convention. | **Fixed:** `config_dir=None` uses the default lookup; a folder is an override for tests. E4 covers both. |
| F3 | Low | An agent named in the YAML without an `@agent` method fails at instantiation (E7). It would surprise a future YAML edit. | **Fixed:** a guard test. |
| F4 | Low | `CrewBase` registers call hooks globally, but only for methods decorated as hooks. None exist here. | **Recorded.** Nothing to do now. |
| F5 | Low | The prototype was tested with the fake model only. A real model was not called. | **By design:** the story's one real debate covers it, and needs the user's go-ahead. |
| F6 | Low | The story says the YAML stays byte for byte. `git mv` guarantees that. | **Added:** a hash comparison in the plan's checks. |

## Change log
- 2026-09-30: approved by the user (gate 2). Both open decisions settled as recommended.
- 2026-09-30: drafted after the story was approved, with a working prototype and evidence E1 to E9. Draft, pending review and gate 2.
