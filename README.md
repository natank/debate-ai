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
- `src/debate_ai/artifacts.py`: the `write_artifact` capability
- `tests/`: fake-LLM tests of the orchestrator and of the CrewAI behavior the design relies on
