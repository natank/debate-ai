"""How the debate crew is put together (feature 006).

Holds the small pieces the crew needs. From the next step it also holds the
@CrewBase class itself. This module does not import `run`, so `run` can import it.
"""
from dataclasses import dataclass

from debate_ai.artifacts import render_swapped_verdict, render_verdict
from debate_ai.validation import parse_verdict

MAX_ATTEMPTS = 3  # first call plus 2 retries, per stage; 3 stages => at most 9 calls (12 with the order check)


class RunCancelled(RuntimeError):
    """Raised inside an abandoned run so its worker thread stops."""


@dataclass
class StageStats:
    """Model calls and tokens for one stage. `attempts` counts validated attempts
    (one guardrail check each); a call that timed out is not counted."""

    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class _UsageMeter:
    """Attributes token usage to stages. CrewAI keeps usage per LLM instance, not per
    task, so we snapshot the running total at every guardrail check. Stages run one
    after another, so what accrued since the last check belongs to the current stage."""

    def __init__(self, llms, stats):
        self._llms = list({id(l): l for l in llms}.values())
        self._stats = stats
        self._last = self._totals()

    def _totals(self):
        fields = ("prompt_tokens", "completion_tokens", "total_tokens")
        totals = dict.fromkeys(fields, 0)
        for llm in self._llms:
            summary = llm.get_token_usage_summary()
            for f in fields:
                totals[f] += getattr(summary, f, 0) or 0
        return totals

    def record(self, stage: str, *, attempt: bool = True) -> None:
        now = self._totals()
        stats = self._stats.setdefault(stage, StageStats())
        if attempt:
            stats.attempts += 1
        for f, value in now.items():
            setattr(stats, f, getattr(stats, f) + value - self._last[f])
        self._last = now


def _render_verdict(motion: str, raw: str) -> str:
    v = parse_verdict(raw)
    return render_verdict(motion, v.winner, v.reasoning)


def _render_swapped(motion: str, raw: str) -> str:
    v = parse_verdict(raw)
    return render_swapped_verdict(motion, v.winner, v.reasoning)
