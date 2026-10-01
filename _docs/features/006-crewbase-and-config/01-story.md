# 006 — Adopt @CrewBase and Move the Config into the Source: Story

```
Status: Approved
Tier: complex       (tier approved by the user on 2026-09-30)
Approved: natank (the user), 2026-09-30
```

_History: this began as a simple feature (move `agents.yaml` and `tasks.yaml` out of
`_docs/` into the source). The user then asked for the crew itself to use CrewAI's
`@CrewBase` structure too, so it is now one complex feature. The earlier draft is in
commit `f114c32`._

**As a** maintainer, **I want** the debate crew defined with CrewAI's standard
`@CrewBase` structure, with its `agents.yaml` and `tasks.yaml` in the package
source, **so that** the project follows the framework's conventions, the
configuration is code (versioned, tested, and shipped with the package), and
agents, tasks and config are where CrewAI users expect to find them.

**Why.**
- The two YAML files sit in `_docs/config/`, and the code finds them by walking up from `run.py` to the repository root and into `_docs`. Documentation is not code, and that lookup breaks when the package is installed instead of run from the repository.
- The crew is currently assembled by hand in `_build_crew`. Design step 5 chose that on purpose (the reasons are in `_docs/design/05-framework-mapping.md`), but the user wants the framework's own structure instead. `@CrewBase` also expects its YAML in a `config/` folder next to the code, which is where the files are moving.

**This is a refactor. Nothing a user can see may change.** The debate must behave
exactly as it does today; only how it is assembled and where its config lives change.

## Tier
**Complex**, approved by the user on 2026-09-30. Reasons:
- It overturns a decision recorded in design step 5 (direct construction).
- It touches the run loop and most of the tests.
- It puts a core rule at risk if done wrong: the opposition must never see the proposition (NFR-1), and the two judge prompts must differ only in order.
- It has real design questions: how per-run state (run id, cancel flag, token meter, callbacks) and the swappable fake model reach a class-based crew, how the optional fourth task is included, and how `@CrewBase` treats the `llm:` value in the YAML.
- It needs feasibility experiments before a design can be trusted.


## Acceptance criteria
- [ ] The crew is defined by a `@CrewBase` class with `@agent`, `@task` and `@crew` methods. Its agents and tasks come from `agents.yaml` and `tasks.yaml`.
- [ ] Those two files are in `src/debate_ai/config/` and no longer in `_docs/config/`, moved with `git mv` so their history follows. Their content is unchanged, byte for byte.
- [ ] Nothing under `src/` refers to `_docs`, and a test enforces it.
- [ ] The app finds its config from its own package location, so it works from the repository and from an installed package. A wheel built from the project contains the two files.
- [ ] **Behavior is unchanged.** Every existing test passes without weakening any assertion, including: the opposition never sees the proposition; the two judge prompts differ only in argument order and neither judge sees the other's verdict; each stage gets three attempts; the fourth (swapped) task exists only with `--check-order`; per-run state and the fake model still reach the crew; artifacts, limits, outcomes and the run report are as before.
- [ ] `run_debate` keeps its signature and its result. The outer control loop stays in application code.
- [ ] One real debate with `--check-order` produces the same kind of output as before (a check for the user to run, or to approve).
- [ ] Documentation is corrected: design 05 records the decision to adopt `@CrewBase` and why it reverses the earlier choice, and every document that names the old config path is updated.

## Out of scope
- Any change to the YAML content, the prompts or the model.
- A command-line option to choose a config file.
- Other CrewAI features: flows, memory, tools, delegation, asynchronous tasks.
- Any change to the outer control loop, the batch, the summary or the order check.
- Any user-visible behavior change.

## Requirement changes
- none. The PRD's source references [1] and [2] get the new path, which is not a requirement.

## Open questions
All four were answered by the user on 2026-09-30, each as proposed:
1. **The fallback.** If the design phase finds that `@CrewBase` cannot keep one of the guarantees above (for example the isolation rule, or injecting the fake model), stop at the design gate and tell the user. The fallback is the smaller feature already drafted (`f114c32`): keep the hand-built crew and only move the config into the source. Resolved: yes.
2. **The real check.** One real debate with `--check-order` (about 3,000 tokens), run once at the end with the user's go-ahead. Resolved: yes.
3. **Folder name.** `006-crewbase-and-config`. Resolved: yes.
4. **Tier.** Complex. Resolved: yes.

Nothing is open. Story approved by the user on 2026-09-30 (gate 1 passed).

## Change log
- 2026-09-30: approved by the user (gate 1), all four questions answered as proposed. Design work may start.
- 2026-09-30: rewritten from the simple config-move draft (`f114c32`) after the user asked to also adopt `@CrewBase`. Draft, awaiting the tier decision, the answers above, and approval (gate 1).
