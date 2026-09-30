# Debate AI

An agentic debate app: two debaters and a judge, built on CrewAI. See `README.md` for usage.

## How features are added: read this first

**Read `features/README.md` before starting, changing or continuing any feature.**
It defines the required workflow: a story, a design and a delivery plan, each
behind an explicit user approval gate, with the tier (simple or complex)
approved by the user by hand. Documentation (including `_docs/prd.md`) is part
of delivery and ships in the same PR as the code. Do not write feature code
before the gates in that file are passed.

To resume work, read `features/README.md` (section 8), then the feature's folder.

## Working rules

- Push, open a PR and merge only when the user asks. Work on a feature branch.
- Never commit `.env`. The repo is public.
- Run tests with `uv run pytest` (no API key or network needed). A real debate
  (`uv run debate "<motion>"`) calls the OpenAI API and costs money; run one only when asked.

## Where things are

- `_docs/prd.md`: requirements as delivered. `_docs/design/`: the original agent-system design.
- `src/debate_ai/`: `run.py` (outer loop), `validation.py`, `artifacts.py`, `cli.py`.
- `_docs/config/`: `agents.yaml` and `tasks.yaml`.
