# 006 — Move the agent and task config into the source

```
Status: Draft
Tier: simple        (proposed by the agent; tier approval pending)
Approved: pending
```

_Simple feature: one document, one approval gate for all three sections._

**Proposed tier: simple.** Reasons: a file move, one changed path in the code,
and documentation corrections. No requirement changes, no change to the agent
system, no new behavior, and it fits in one PR. The user decides the tier.

## 1. Story

**As a** maintainer, **I want** `agents.yaml` and `tasks.yaml` to live in the
package source, **so that** the configuration the app reads at run time is part
of the code (versioned, tested, and packaged with it) and not stored under the
documentation folder.

**Why.** The two files were moved into `_docs/config/` when the project started,
and the code finds them by walking up from `run.py` to the repository root and
into `_docs`. That has two problems: documentation is not code, and the lookup
breaks as soon as the package is installed rather than run from the repository
(the walk up from `site-packages` finds no `_docs`).

**Acceptance criteria**
- [ ] `agents.yaml` and `tasks.yaml` are in `src/debate_ai/config/` and no longer in `_docs/config/`. They are moved with `git mv`, so their history follows them.
- [ ] The app finds them from its own package location, so it works from the repository and from an installed package. A wheel built from the project contains `debate_ai/config/agents.yaml` and `tasks.yaml`.
- [ ] Nothing under `src/` refers to `_docs`. A test enforces it.
- [ ] The YAML content is unchanged, byte for byte, and debates behave exactly as before.
- [ ] All existing tests pass. The tests that read the config use the new location.
- [ ] Every document that names the old path is corrected: `README.md`, `CLAUDE.md`, the PRD's source references, design 02 and design 05, and the feature 002 story's reference.

**Out of scope**
- Changing the YAML content or the model.
- A command-line option to choose a config file. `run_debate` already takes a `config_dir` for tests; exposing it is a separate feature.
- Any change to how the config is used (the code still parses it with a plain YAML loader).

**Requirement changes**
- none. The PRD's source references [1] and [2] get the new path, which is not a requirement.

**Open questions**
1. Folder name: `src/debate_ai/config/`. _Proposal: yes._
2. Old design and feature records mention `_docs/config` where they describe history. _Proposal: correct the path only where a document states where the config lives now, and add one line to design 05 saying it moved (feature 006). Leave sentences that describe the past._

## 2. Design

**Approach.** Move the two files with `git mv` to `src/debate_ai/config/`. Change
one line in `run.py`:

```python
CONFIG_DIR = Path(__file__).resolve().parent / "config"   # was parents[2] / "_docs" / "config"
```

The path is now relative to the module, so it is correct in the repository, in an
editable install, and in a built wheel. `run_debate(..., config_dir=...)` and
`_build_crew` are unchanged.

**Evidence** (checked 2026-09-30, before writing this). With the two files in
`src/debate_ai/config/`, `uv build --wheel` produced a wheel containing
`debate_ai/config/agents.yaml` and `debate_ai/config/tasks.yaml`. The build
needs no `pyproject.toml` change: the build backend includes every file inside a
listed package directory.

**Alternatives considered**

| Alternative | Why not |
|---|---|
| Keep `_docs/config/` | Documentation is not code, and the lookup breaks when installed. This is the problem. |
| A top-level `config/` folder | Outside the package, so a built wheel would not contain it and an installed app would not find it, unless the build is configured to ship it as extra data. More machinery for the same result. |
| `importlib.resources` to locate the files | The standard tool, and it also handles zipped installs. Unneeded here: `debate_ai` is a normal package, and a module-relative path is simpler and just as correct. Easy to switch later. |
| Also add a `--config` option | A separate feature (see out of scope). |

**Impact on existing work**
- **Code:** `src/debate_ai/run.py` (one line) and `tests/test_isolation.py` (its path to the config).
- **Documents:** the eight files that name the old path (README, CLAUDE.md, PRD, design 02, design 05, the feature 002 story, plus the two code files above).
- **Requirements and agent design:** no change.

**Risks and how each is checked**

| Risk | How it is checked |
|---|---|
| The move changes the YAML | A byte-for-byte comparison of both files before and after the move. |
| The code still reads from `_docs` somewhere | A test that no file under `src/` contains `_docs`. |
| A document is left with the old path | A search of the repository for `_docs/config` after the change; anything left must be a sentence about history. |
| The package would not ship the files | The wheel check above, repeated after the move. |

**Test approach** (fake model, no network)
- New tests: both files exist in the package's `config/` folder and parse as YAML with the expected top-level keys (`debater`, `judge`; `propose`, `oppose`, `decide`); the default config directory is inside the package; no file under `src/` mentions `_docs`.
- Existing tests run unchanged apart from `test_isolation.py`'s path. Every fake-model debate already loads the default config, so they cover loading from the new location.

## 3. Delivery plan

| # | Subtask | Acceptance check / test | Done |
|---|---|---|---|
| 1 | **Move the config and point the code at it.** `git mv` both files to `src/debate_ai/config/`; change `CONFIG_DIR`; update `tests/test_isolation.py`; add the new tests. | Hashes of both files equal before and after; `git log --follow` shows their history; the new tests and every existing test pass; a wheel built from the tree contains the two files. | [ ] |
| 2 | **Correct the documents.** Update the path in README, CLAUDE.md, the PRD sources, design 02, design 05 and the feature 002 story; add a one-line note to design 05 that the files moved (feature 006). | A repository search for `_docs/config` finds only sentences about history. | [ ] |

**Branch and PR**: `feature/006-config-in-src`, one PR. The document first, then one commit per subtask.

**Documentation to update** (part of delivery)
- [ ] `_docs/prd.md`: the path in the source references [1] and [2]. No requirement changes.
- [ ] `README.md`, `CLAUDE.md`, `_docs/design/02-reasoning-core-configs.md`, `_docs/design/05-framework-mapping.md`, and the reference in `features/002-swapped-order-judge/01-story.md`.
- [ ] `features/README.md`: set this feature's state in the index.

## Change log
- 2026-09-30: drafted after the user pointed out that the runtime config should live in the source, not in the documentation folder. Draft, pending tier approval and the gate.
