"""How the debate crew is put together (feature 006).

`DebateCrew` is the crew in CrewAI's standard @CrewBase shape: agents and tasks come
from `config/agents.yaml` and `config/tasks.yaml` beside this file, and the class
supplies what the YAML cannot (per-run state, the swappable model, the guardrails).
The pieces it needs are defined here too. This module does not import `run`, so
`run` can import it.
"""
from dataclasses import dataclass
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from debate_ai.artifacts import CHECK_STAGE, render_argument, render_swapped_verdict, render_verdict
from debate_ai.validation import argument_guardrail, parse_verdict, verdict_guardrail

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


@CrewBase
class DebateCrew:
    """One debate's crew. Build one per run: it holds that run's state.

    `@CrewBase` creates the instance first, then loads the YAML and builds the agents.
    So everything the agent and task methods need is set in `__init__`.
    """

    def __init__(self, motion, llm_factory, saver, cancelled, stats, check_order=False, config_dir=None):
        if config_dir is not None:
            # An absolute path replaces the default "config/..." beside this file (for tests).
            self.original_agents_config_path = str(Path(config_dir) / "agents.yaml")
            self.original_tasks_config_path = str(Path(config_dir) / "tasks.yaml")
        self.motion = motion
        self.llm_factory = llm_factory
        self.saver = saver
        self.cancelled = cancelled
        self.stats = stats
        self.check_order = check_order
        self._llms = {}
        self.meter = None  # created in crew(), once both agents exist

    def _llm(self, name):
        # The model comes from our factory, never from the YAML's `llm:` string, so tests
        # need no API key and the YAML is left exactly as written.
        if name not in self._llms:
            self._llms[name] = self.llm_factory(self.agents_config[name]["llm"])
        return self._llms[name]

    def _checked(self, stage, guardrail):
        def wrapper(output):
            if self.cancelled.is_set():
                raise RunCancelled("the run was cancelled after its time limit")
            self.meter.record(stage)
            return guardrail(output)

        return wrapper

    def _task(self, name, **extra):
        # `@CrewBase` already replaced tasks_config[name]["agent"] (a name) with that agent.
        return Task(**self.tasks_config[name], guardrail_max_retries=MAX_ATTEMPTS - 1, **extra)

    @agent
    def debater(self):
        return Agent(
            **{**self.agents_config["debater"], "llm": self._llm("debater")},
            allow_delegation=False,
            memory=False,
            verbose=False,
        )

    @agent
    def judge(self):
        return Agent(
            **{**self.agents_config["judge"], "llm": self._llm("judge")},
            allow_delegation=False,
            memory=False,
            verbose=False,
        )

    # context=[] keeps the opposition blind to the proposition (design step 4 scoping).
    @task
    def propose(self):
        return self._task(
            "propose",
            context=[],
            guardrail=self._checked("propose", argument_guardrail),
            callback=self.saver("propose", lambda out: render_argument(self.motion, "for", out.raw)),
        )

    @task
    def oppose(self):
        return self._task(
            "oppose",
            context=[],
            guardrail=self._checked("oppose", argument_guardrail),
            callback=self.saver("oppose", lambda out: render_argument(self.motion, "against", out.raw)),
        )

    @task
    def decide(self):
        return self._task(
            "decide",
            context=[self.propose(), self.oppose()],
            # No output_pydantic: with it, only the first bad reply is retried and a
            # second one raises a raw ValidationError. The guardrail validates the JSON
            # and we parse it ourselves.
            guardrail=self._checked("decide", verdict_guardrail),
            callback=self.saver("decide", lambda out: _render_verdict(self.motion, out.raw)),
        )

    @task
    def decide_swapped(self):
        # Feature 002: the same judge task text and guardrail, with the two arguments in
        # the opposite order. Its context excludes `decide`, so it never sees the first
        # verdict. Two tasks may share a YAML entry: CrewAI tells them apart by id.
        return self._task(
            "decide",
            context=[self.oppose(), self.propose()],
            guardrail=self._checked(CHECK_STAGE, verdict_guardrail),
            callback=self.saver(CHECK_STAGE, lambda out: _render_swapped(self.motion, out.raw)),
        )

    def stage_tasks(self):
        """Stage name -> its task, for the stages this run has."""
        named = {"propose": self.propose(), "oppose": self.oppose(), "decide": self.decide()}
        if self.check_order:
            named[CHECK_STAGE] = self.decide_swapped()
        return named

    @crew
    def crew(self):
        self.meter = _UsageMeter(self._llms.values(), self.stats)
        # Listed explicitly, so the swapped task joins the crew only when it was asked for.
        tasks = [self.propose(), self.oppose(), self.decide()]
        if self.check_order:
            tasks.append(self.decide_swapped())
        return Crew(
            agents=[self.debater(), self.judge()],
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
        )
