# Design Step 3 — Capability Contracts

_Status: Draft · 2026-09-29_
_Input: `_docs/design/01-stages-and-sequence.md`, `_docs/design/02-reasoning-core-configs.md`._
_Process: `_docs/agentic-systems-and-workflows.md`, Design process, Step 3. No framework is assumed._

## 1. Capability inventory

_Update (feature 001): a second capability, `write_summary`, was added for batch runs. It is defined in section 9. The reasoning core still requests neither._

Steps 1 and 2 leave exactly one capability beyond reasoning:

| Capability | Needed by | Caller |
|---|---|---|
| Write artifact | S1, S2, S3 | The control loop (step 2, section 3), not the reasoning core |

There are no other capabilities in v1. In particular:

- **No lookup or research tool.** The PRD puts web research and fact-checking
  out of scope, and neither configuration has an allowed tool.
- **Reading inputs is not a capability.** Assembling each stage's inputs is
  the memory relationship (step 4).
- **Calling the reasoning core is not a capability.** It is relationship 1.

Because the reasoning core never requests this capability, it is not exposed
as a tool. There is no tool schema and no model-visible name. The contract
below is for ordinary application code, owned and tested like any other.

## 2. Contract: Write artifact

**Purpose.** Persist one stage's validated output as a Markdown file in the
run's output folder.

| Field | Contract |
|---|---|
| **Name** | `write_artifact` |
| **Arguments** | `run_id`: string, identifies the debate run (one folder per run, PRD Q4). `stage`: enum `propose`, `oppose`, `decide`. `content`: string, the validated stage output, already rendered as Markdown. |
| **Result** | `path`: string, the file written (`output/<run_id>/<stage>.md`). `bytes`: integer written. |
| **Side effects** | Creates the run folder if missing. Creates or replaces one file. Touches nothing outside `output/<run_id>/`. |
| **Failure modes** | See section 3. |
| **Retry safety** | Safe to retry. See section 4. |
| **Approval needed** | No. See section 5. |

**Path is derived, never supplied.** The file name comes from `stage` (a fixed
enum) and the folder from `run_id`. Neither is taken from model output, so a
model cannot choose or influence where anything is written.

**Content is data.** `content` is written as-is. It is never executed,
interpreted as a path, or used to build a command.

## 3. Failure modes

Each failure is reported to the control loop as a typed error, not swallowed.

| Failure | Cause | Reported as | Control loop response (owned by step 4) |
|---|---|---|---|
| Invalid stage | `stage` is not one of the three values | `InvalidArgument` | Programming error. Stop the run as failed. |
| Invalid run id | `run_id` is empty or contains path separators or `..` | `InvalidArgument` | Programming error. Stop the run as failed. |
| Empty content | `content` is empty | `InvalidArgument` | Should be unreachable, because validation rejects empty output first. Stop as failed. |
| Cannot create folder or file | Permissions, missing parent, read-only disk | `WriteFailed` | Retry within limits, then stop as failed. |
| Disk full | No space | `WriteFailed` | Same as above. |
| Partial write | Process dies mid-write | Not reported to the caller (the process is gone) | Prevented by the write strategy in section 4. |

A `WriteFailed` after S1 or S2 has produced valid output must not lose that
output. It stays in memory, and the write is retried without re-calling the
reasoning core (no repeat model cost).

## 4. Retry safety

Idempotent. Calling it twice with the same arguments leaves one file with the
same content.

- **Atomic replace.** Write to a temporary file in the same folder, then
  rename over the target. A reader sees the old file or the new one, never a
  half-written one.
- **Overwrite is allowed within a run.** Re-writing `<stage>.md` for the same
  `run_id` replaces it. This is what makes retry safe.
- **No overwrite across runs.** Each debate has its own `run_id`, so one run
  never replaces another run's files (PRD Q4).

## 5. Approval

None. The capability writes only under `output/<run_id>/`, only files the
system itself named, and nothing it writes is executed or sent anywhere. The
`output/` folder is gitignored, so files are not published by accident.

## 6. Output of step 3

- One contract: `write_artifact` (section 2).
- Failure table (section 3) and retry rule (section 4).

## 7. Carried forward

| To step | Item |
|---|---|
| 4 | Response to each failure in section 3: retry limits for `WriteFailed`, and stop-as-failed behavior. |
| 4 | Whether the Markdown rendering (heading with the motion and side, then the body) is part of the stage output or done by the control loop before the write. |
| 4 | Who generates `run_id` and where it enters memory (outer loop, with the motion). |
| 5 | Filesystem write is application code in any framework. Note whether a framework's own output-file feature is used instead, and if so how it satisfies the atomic-replace and derived-path rules here. |

## 8. Checklist (step 3 items)

- [x] Every capability has a contract, including side effects, retry safety and approval.
- [x] No capability is exposed to a configuration that does not need it.

## 9. Contract: Write summary _(added by feature 001)_

`write_artifact` (section 2) takes a fixed stage name, and a batch summary is
not a stage. Rather than loosen that contract, a sibling capability was added
with the same rules. Like `write_artifact`, it is called by application code,
never by the reasoning core, and is not exposed as a tool.

| Field | Contract |
|---|---|
| **Name** | `write_summary` |
| **Purpose** | Persist a batch's `summary.md`. Rewritten after every debate, so an interrupted batch leaves a valid file. |
| **Arguments** | `output_dir`; `batch_id`: string, same safety rules as `run_id` (no separators, no `..`, at most 100 characters); `content`: non-empty Markdown. |
| **Result** | `path`: `<output_dir>/batch-<batch_id>/summary.md`; `bytes`. |
| **Side effects** | Creates the batch folder if missing, and creates or replaces `summary.md`. Touches nothing else. |
| **Failure modes** | `InvalidArgument` (unsafe `batch_id`, empty content) and `WriteFailed`, reported as in section 3. |
| **Retry safety** | Idempotent. The same atomic temporary-file-then-rename write as section 4, so a reader sees the old or the new file, never a partial one. Only `WriteFailed` is retried (3 attempts), never an invalid argument. |
| **Approval needed** | No. It writes one file under a folder the system named. |

The path is derived, never supplied by the model or the user. The atomic write
is shared code with `write_artifact`.

