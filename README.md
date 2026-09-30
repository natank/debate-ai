# Debate AI

An agentic debate app. Give it a motion; one debater argues for it, the same
debater argues against it, and a judge decides which side was more convincing.

## Usage

```
uv sync
cp .env.example .env        # then set OPENAI_API_KEY
uv run debate "Cats make better pets than dogs"
```

Each run writes `output/<run_id>/propose.md`, `oppose.md` and `decide.md`.
Exit code: 0 success, 1 exhausted (retry or time limit reached), 2 failed.

### Batch: many motions and a summary

Put motions in a text file, one per line. Write `A | B` on one line for a pair
of opposite motions. Blank lines and lines starting with `#` are ignored.

```
# Pets: a pair, so we can test consistency
Cats make better pets than dogs | Dogs make better pets than cats

# A single motion
Remote work is better than office work
```

```
uv run debate --batch motions.txt [--budget 20000] [--output-dir output]
```

A progress line is printed as each debate finishes. Everything goes in
`output/batch-<id>/`: one folder per debate, and a `summary.md` with a row per
motion, the for-win rate, whether the judge stayed consistent on each pair, and
total attempts and tokens. The summary is rewritten after every debate, so an
interrupted batch still leaves a valid one.

- **Budget:** the batch stops before starting a debate once the tokens spent
  reach the budget (default 20,000, about 10 debates). A failed run does not stop it.
- **Exit code:** 0 if every motion completed, 1 if any run was exhausted or
  failed or any motion was skipped, 2 if the file was invalid or the summary
  could not be written. An invalid file is rejected before any model call.
- **Read the rates carefully:** the judge always sees the proposition first, so
  a skew toward "for" cannot be told apart from an ordering effect. The summary
  reports rates, not a verdict of bias.

The run report lists, per stage, the attempts used (a rejected reply that was
retried counts as another attempt), the tokens spent, and the artifact path,
followed by a total. It is printed for failed runs too, so you can see what an
exhausted stage cost. Attempts count validated replies; a call that timed out
is not counted, though its tokens are added to the stage's usage.

```
uv run pytest               # no API key or network needed
```

## Documents

- `_docs/prd.md`: product requirements
- `_docs/config/agents.yaml`, `_docs/config/tasks.yaml`: agent and task definitions
- `_docs/agentic-systems-and-workflows.md`: the design process used here
- `_docs/design/01` to `05`: the design, one file per step of that process

## Layout

- `src/debate_ai/run.py`: outer control loop (motion entry, limits, outcomes)
- `src/debate_ai/validation.py`: stage output checks (guardrails)
- `src/debate_ai/artifacts.py`: the `write_artifact` and `write_summary` capabilities
- `src/debate_ai/batch.py`: batch input parsing and the driver; `summary.py`: the summary builder
- `features/`: one folder per feature (story, design, delivery plan); see `features/README.md`
- `tests/`: fake-LLM tests of the orchestrator and of the CrewAI behavior the design relies on
