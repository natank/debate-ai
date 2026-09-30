# 006 — Adopt @CrewBase and Move the Config into the Source: Delivery Plan

```
Status: Approved
Approved: natank (the user), 2026-09-30
Design: 02-design.md (Approved, gate 2 passed)
```

## TL;DR

**What:** a structural refactor with **no user-visible change**. The crew is
defined by a `@CrewBase` class (`DebateCrew`, in a new `src/debate_ai/crew.py`)
instead of a hand-built function, and the two YAML config files move from
`_docs/config/` into `src/debate_ai/config/`, so the config is code and ships with
the package.

**What must not change:** every prompt sent to the model, every artifact, the
stats, the results, the isolation rule (the opposition never sees the
proposition), the judge prompts differing only in order, the three attempts per
stage, the optional swapped-order task, and all 195 existing tests.

**How it is made safe:** first record a baseline of today's behavior (prompts,
artifacts, stats, results, with the order check off and on). Every later step must
still match it. The work is then split so each commit passes all tests: record the
baseline, move the config, move a few helpers, swap in the `@CrewBase` class, fix
the docs.

**What gets built:** six subtasks in one PR. One real debate at the end (about
3,000 tokens) needs your go-ahead.

**Touches:** `run.py`, a new `crew.py`, `tests/test_isolation.py`, the config files,
and the documents that name the old path. `batch.py`, `summary.py`, `cli.py`,
`artifacts.py`, `order_check.py` and `validation.py` are not changed.

## Subtasks

| # | Subtask | Acceptance check / test | Depends on | Done |
|---|---|---|---|---|
| 0 | **Record the baseline, before changing any code.** A parity test compares a stored recording of today's behavior (the prompts sent to the fake model, the artifact files, the per-stage stats, and the result), for the order check off and on. The recording is made now, from the current code. | The parity test passes against the **current** code. The recording holds fake data only. Every existing test still passes. | - | [x] |
| 1 | **Move the config; keep the hand-built crew.** `git mv` both YAML files to `src/debate_ai/config/`; point the code at the new folder; update `tests/test_isolation.py`. Add tests: both files exist there and parse with the expected top-level keys; nothing under `src/` mentions `_docs`. | The move is a 100% rename with identical content (`git diff -M --stat`, and matching hashes). All tests pass, including the parity test. A wheel built from the tree contains `debate_ai/config/agents.yaml` and `tasks.yaml` (recorded once). | 0 | [x] |
| 2 | **Move the shared helpers into `crew.py`.** `MAX_ATTEMPTS`, `RunCancelled`, `StageStats`, the usage meter and the two verdict renderers move with no change to their code. `run.py` imports them, so every existing import still works. | An import test: `debate_ai.run` and `debate_ai.crew` import in either order, and `from debate_ai.run import StageStats, RunResult, run_debate` still works. All tests pass, including the parity test. | 0 | [x] |
| 3 | **Replace `_build_crew` with the `@CrewBase` class.** `DebateCrew` with `@agent` `debater` and `judge`, `@task` `propose`, `oppose`, `decide` and `decide_swapped`, and a `@crew` method that lists 3 or 4 tasks. `run_debate` builds it. `config_dir` defaults to `None`, which uses the framework's lookup beside the class; a folder is an override. `_build_crew` and the old path constant are removed. | Tests: `DebateCrew` is a `@CrewBase` class; every agent named in `tasks.yaml` has an `@agent` method; the crew has 3 tasks without the check and 4 with it; `propose` and `oppose` have empty context, `decide` reads propose then oppose, `decide_swapped` reads oppose then propose; two crews built in a row share no agents or config; the default lookup works from another working directory; `run_debate` keeps its parameter names. **The parity test and all existing tests pass unchanged.** | 1, 2 | [ ] |
| 4 | **Correct the documents.** Design 05 records that the "build the crew by hand" decision is reversed, and why. Update the config path in README, CLAUDE.md, the PRD source references, design 02, and the feature 002 story; mention `crew.py` in the README layout and CLAUDE.md. | A repository search for `_docs/config` finds only sentences about history. | 3 | [ ] |
| 5 | **Real check.** One real debate with `--check-order`, about 3,000 tokens. Run only with the user's go-ahead. | Manual review: the same kind of output as before (three artifacts plus `decide_swapped.md`, an `Order check:` line, the run report), recorded in Deviations. | 3 | [ ] |

**Order of work.** Subtask 0 first: it must be recorded from the unchanged code, or
it proves nothing. Then 1 and 2 (independent of each other), then 3, then 4. Subtask
5 last, with your go-ahead. Subtasks 0 to 4 use the fake model only: no network and
no API key.

**Every commit passes every test.** That is why the config move (1) and the helper
move (2) come before the class swap (3): each is small and can be checked on its
own against the baseline.

## Traceability

| Story acceptance criterion | Subtask(s) |
|---|---|
| The crew is a `@CrewBase` class with `@agent`, `@task`, `@crew` methods reading the YAML | 3 |
| The config is in `src/debate_ai/config/`, moved with `git mv`, content unchanged byte for byte | 1 |
| Nothing under `src/` refers to `_docs`, enforced by a test | 1, 3 |
| The app finds its config from its own package location; a wheel contains it | 1, 3 |
| Behavior unchanged: every existing test passes; isolation, judge prompts, three attempts, the optional fourth task, per-run state and the fake model all intact | 0, 2, 3 |
| `run_debate` keeps its signature and result; the outer loop stays in application code | 3 |
| One real debate with `--check-order` gives the same kind of output | 5 |
| Documentation corrected, including design 05 and the old paths | 4 |

## Branch and PR plan
`feature/006-crewbase-and-config`. **One PR** for the whole feature. The documents
(story, design, plan) are the first commits, then one commit per subtask.

## Documentation to update (part of delivery)
- [ ] `_docs/design/05-framework-mapping.md`: the decision to adopt `@CrewBase`, why it reverses the earlier choice, and the path.
- [ ] `_docs/prd.md`: the config path in the source references [1] and [2]. No requirement changes.
- [ ] `README.md` and `CLAUDE.md`: the config path, and `crew.py` in the layout.
- [ ] `_docs/design/02-reasoning-core-configs.md`: the config path.
- [ ] `features/002-swapped-order-judge/01-story.md`: the reference to the config folder.
- [ ] `features/README.md`: set this feature's state in the index.

## Definition of Done
See `features/README.md`, section 6. Every item applies.

## Review (2026-09-30)

Checked against the approved story and design and against the code.

**What holds up:** every acceptance criterion is covered (see Traceability); each
subtask has its own checks; the design's tests are all placed; it is one PR; and
subtasks 0 to 4 need no network or API key.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| P1 | High | A parity check is only worth something if the baseline is recorded from the code **before** it changes. If it were recorded after the swap it would compare the new code with itself. | **Fixed:** subtask 0 comes first and its check is that it passes against the current code. |
| P2 | Medium | Doing the config move, the helper move and the class swap together would give one large, hard-to-review commit with no way to tell which step caused a difference. | **Fixed:** three separate subtasks (1, 2, 3), each passing every test on its own, in an order where 1 and 2 do not depend on each other. |
| P3 | Medium | Removing the old path constant and changing `config_dir` to default to `None` is a signature-level change. Nothing else in `src/` or `tests/` uses the constant (checked), but the story says `run_debate` keeps its signature. | **Fixed:** subtask 3 includes a test that the parameter names are unchanged; only the default value of one parameter changes, which no caller can notice. |
| P4 | Low | The wheel check needs a build, so it should not be a permanent test that slows every run. | **Fixed:** recorded once in subtask 1 and noted in the plan. |
| P5 | Low | The recorded baseline holds full prompts. | **Fixed:** it is generated with the fake model and fake text only, so it holds no real data or secrets. |
| P6 | Low | The design's remark that the `@crew` decorator may build unused tasks was not tested. | **Noted, not relied on:** the crew lists its tasks explicitly, and the parity check would catch any effect. |

## Deviations
- 2026-09-30, subtask 1 evidence (recorded once, as planned): both YAML files hash identically before and after the move (sha256, byte for byte) and git records the change as a 100% rename. `uv build --wheel` on the real tree produced `debate_ai-0.1.0-py3-none-any.whl` containing `debate_ai/config/agents.yaml` and `debate_ai/config/tasks.yaml`, and nothing from `_docs`. After the move the suite was 210 passing, with the parity test unchanged. In this step the hand-built crew still reads the config; only its folder changed.

## Change log
- 2026-09-30: approved by the user (gate 3 passed). All three gates passed; delivery starts.
- 2026-09-30: written after the design was approved. Draft, pending gate 3.
