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
  (`uv run debate "<motion>"`, or `--batch`) calls the OpenAI API and costs money, and `--check-order` adds about 1,000 tokens per debate; run one only when asked.
- When trying the CLI's error paths by hand, set `OPENAI_API_KEY` to a dummy value first and
  write each command out in full. In zsh an unquoted variable is not split into arguments, so a
  test of `--batch FILE` can turn into a real one-motion debate.

## Where things are

- `_docs/prd.md`: requirements as delivered. `_docs/design/`: the original agent-system design.
- `src/debate_ai/`: `run.py` (outer loop), `crew.py` (the `@CrewBase` crew), `validation.py`, `artifacts.py`, `cli.py`, `batch.py` and `summary.py` (batch runs), and `order_check.py` (the order check).
- `src/debate_ai/config/`: `agents.yaml` and `tasks.yaml`, which the crew loads. They are code, not documentation.
