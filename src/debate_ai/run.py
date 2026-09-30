"""The outer control loop (design step 4, section 2, and step 5, section 5).

Owns what no stage owns: motion entry, run id, stage sequencing, artifact
writing, run-level limits, and the success / exhausted / failed report.
Stage-level retry and validation are delegated to CrewAI guardrails.
"""
import re
import threading
import yaml
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional

from crewai import LLM, Agent, Crew, Process, Task

from debate_ai.artifacts import (
    CHECK_STAGE,
    render_argument,
    render_swapped_verdict,
    render_verdict,
    run_stages,
    write_with_retry,
)
from debate_ai.order_check import OrderCheck, compare_verdicts, not_completed
from debate_ai.validation import Verdict, argument_guardrail, parse_verdict, verdict_guardrail

CONFIG_DIR = Path(__file__).resolve().parent / "config"  # inside the package, so it ships with it
MAX_ATTEMPTS = 3  # first call plus 2 retries, per stage; 3 stages => at most 9 calls (12 with the order check)
CALL_TIMEOUT_S = 60
RUN_TIME_LIMIT_S = 300
MAX_COMPLETION_TOKENS = 1000



class RunCancelled(RuntimeError):
    """Raised inside an abandoned run so its worker thread stops."""


Outcome = Literal["success", "exhausted", "failed"]


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


@dataclass
class RunResult:
    outcome: Outcome
    motion: str
    run_id: Optional[str] = None
    stage: Optional[str] = None  # the stage that ended the run, if not success
    reason: Optional[str] = None
    artifacts: dict = field(default_factory=dict)  # stage -> Path
    verdict: Optional[Verdict] = None
    stats: dict = field(default_factory=dict)  # stage -> StageStats
    order_check: Optional[OrderCheck] = None  # None unless --check-order was requested

    @property
    def total(self) -> StageStats:
        total = StageStats()
        for s in self.stats.values():
            total.attempts += s.attempts
            total.prompt_tokens += s.prompt_tokens
            total.completion_tokens += s.completion_tokens
            total.total_tokens += s.total_tokens
        return total


def make_run_id(motion: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    slug = re.sub(r"[^a-z0-9]+", "-", motion.lower()).strip("-")[:40].strip("-") or "debate"
    return f"{now:%Y%m%d-%H%M%S}-{slug}"


def unique_run_id(output_dir, run_id: str) -> str:
    """Return run_id, or run_id-2, run_id-3, ... if that folder already exists, so a
    run never writes into (and overwrites) another run's folder."""
    candidate, n = run_id, 1
    while (Path(output_dir) / candidate).exists():
        n += 1
        candidate = f"{run_id}-{n}"
    return candidate


def default_llm_factory(model: str):
    return LLM(model=model, timeout=CALL_TIMEOUT_S, max_completion_tokens=MAX_COMPLETION_TOKENS)


def run_debate(
    motion: str,
    *,
    output_dir="output",
    llm_factory: Callable[[str], object] = default_llm_factory,
    config_dir: Path = CONFIG_DIR,
    time_limit: float = RUN_TIME_LIMIT_S,
    write_backoff: float = 0.2,
    now: Optional[datetime] = None,
    check_order: bool = False,
) -> RunResult:
    """Run one debate. With `check_order`, the judge is asked a second time about the same
    two arguments in swapped order (feature 002); the official verdict is still the first."""
    motion = (motion or "").strip()
    if not motion:  # FR-1.3: no model call, no folder
        return RunResult("failed", motion, reason="the motion is empty")

    stages = run_stages(check_order)
    run_id = unique_run_id(output_dir, make_run_id(motion, now))
    result = RunResult("failed", motion, run_id=run_id)
    write_errors: dict[str, str] = {}
    completed: list[str] = []
    # A worker thread cannot be killed. On timeout we set this flag; the guardrails
    # and the artifact callback check it, so the abandoned run stops after its
    # in-flight call and writes nothing further.
    cancelled = threading.Event()

    def saver(stage: str, render: Callable[[object], str]):
        def callback(task_output):
            # Written right after the stage passes validation, so a later
            # failure does not lose earlier results.
            if cancelled.is_set():
                return
            try:
                art = write_with_retry(
                    output_dir, run_id, stage, render(task_output), backoff=write_backoff
                )
                result.artifacts[stage] = art.path
            except Exception as e:  # recorded, reported after the crew stops
                write_errors[stage] = str(e)
            completed.append(stage)

        return callback

    crew, tasks, meter = _build_crew(
        motion, config_dir, llm_factory, saver, cancelled, result.stats, check_order
    )

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(crew.kickoff, inputs={"motion": motion})
    try:
        future.result(timeout=time_limit)
    except FutureTimeout:
        cancelled.set()
        executor.shutdown(wait=False, cancel_futures=True)
        if _only_check_missing(check_order, completed, write_errors):
            return _settle_without_check(result, tasks, "the run's time limit was reached")
        result.outcome = "exhausted"
        result.reason = f"the run exceeded its {time_limit:g} s limit"
        result.stage = _next_stage(completed, stages)
        return result  # usage is left as recorded: the abandoned call is still in flight
    except Exception as e:
        result.stage = _next_stage(completed, stages)
        if result.stage:  # tokens from a call that ended in an error, not a check
            meter.record(result.stage, attempt=False)
        if _only_check_missing(check_order, completed, write_errors):
            executor.shutdown(wait=False)
            return _settle_without_check(result, tasks, _check_failure_reason(e))
        result.reason = str(e)
        exhausted = isinstance(e, TimeoutError) or "guardrail validation" in str(e)
        result.outcome = "exhausted" if exhausted else "failed"
        executor.shutdown(wait=False)
        return _with_write_errors(result, write_errors)
    executor.shutdown(wait=False)

    if write_errors:
        if check_order and set(write_errors) == {CHECK_STAGE}:
            return _settle_without_check(result, tasks, "the swapped verdict could not be saved")
        return _with_write_errors(result, write_errors)
    result.outcome = "success"
    result.verdict = parse_verdict(tasks["decide"].output.raw)
    if check_order:
        swapped = parse_verdict(tasks[CHECK_STAGE].output.raw)
        result.order_check = compare_verdicts(result.verdict, swapped)
    return result


def _render_verdict(motion: str, raw: str) -> str:
    v = parse_verdict(raw)
    return render_verdict(motion, v.winner, v.reasoning)


def _only_check_missing(check_order: bool, completed: list, write_errors: dict) -> bool:
    """True when the official verdict is done and safely saved, and only the order check
    is missing. The check is extra information, so this must never cost the user a
    good debate (feature 002, FR-9.9): every path that ends a run asks this first."""
    return (
        check_order
        and "decide" in completed
        and CHECK_STAGE not in completed
        and set(write_errors) <= {CHECK_STAGE}
    )


def _check_failure_reason(e: Exception) -> str:
    if "guardrail validation" in str(e):
        return f"the swapped verdict was rejected {MAX_ATTEMPTS} times"
    if isinstance(e, TimeoutError):
        return "the swapped call timed out"
    return f"the swapped call failed: {str(e)[:150]}"


def _settle_without_check(result: RunResult, tasks: dict, reason: str) -> RunResult:
    """End the run as a success with its official verdict and a check that did not complete."""
    result.outcome = "success"
    result.stage = None
    result.reason = None
    result.verdict = parse_verdict(tasks["decide"].output.raw)
    result.order_check = not_completed(reason)
    return result


def _render_swapped(motion: str, raw: str) -> str:
    v = parse_verdict(raw)
    return render_swapped_verdict(motion, v.winner, v.reasoning)


def _next_stage(completed: list, stages: tuple) -> Optional[str]:
    """The first of this run's stages that has not completed. A run uses its own
    stage list, so a normal run can never name the order-check stage."""
    return next((s for s in stages if s not in completed), None)


def _with_write_errors(result: RunResult, write_errors: dict) -> RunResult:
    if write_errors:
        stage, message = next(iter(write_errors.items()))
        result.outcome = "failed"
        result.stage = stage
        result.reason = f"artifact write failed: {message}"
    return result


def _build_crew(motion, config_dir, llm_factory, saver, cancelled, stats, check_order=False):
    agents_cfg = yaml.safe_load((config_dir / "agents.yaml").read_text())
    tasks_cfg = yaml.safe_load((config_dir / "tasks.yaml").read_text())

    llms = {name: llm_factory(cfg["llm"]) for name, cfg in agents_cfg.items()}
    agents = {
        name: Agent(
            **{**cfg, "llm": llms[name]},
            allow_delegation=False,
            memory=False,
            verbose=False,
        )
        for name, cfg in agents_cfg.items()
    }
    meter = _UsageMeter(llms.values(), stats)

    def checked(stage, guardrail):
        def wrapper(output):
            if cancelled.is_set():
                raise RunCancelled("the run was cancelled after its time limit")
            meter.record(stage)
            return guardrail(output)

        return wrapper

    def task(name, **extra):
        cfg = {k: v for k, v in tasks_cfg[name].items() if k != "agent"}
        return Task(
            **cfg,
            agent=agents[tasks_cfg[name]["agent"]],
            guardrail_max_retries=MAX_ATTEMPTS - 1,
            **extra,
        )

    # context=[] keeps S2 blind to S1 (design step 4 scoping, test 1).
    propose = task(
        "propose",
        context=[],
        guardrail=checked("propose", argument_guardrail),
        callback=saver("propose", lambda out: render_argument(motion, "for", out.raw)),
    )
    oppose = task(
        "oppose",
        context=[],
        guardrail=checked("oppose", argument_guardrail),
        callback=saver("oppose", lambda out: render_argument(motion, "against", out.raw)),
    )
    decide = task(
        "decide",
        context=[propose, oppose],
        # No output_pydantic: with it, only the first bad reply is retried and a
        # second one raises a raw ValidationError (test 5). The guardrail validates
        # the JSON and we parse it ourselves.
        guardrail=checked("decide", verdict_guardrail),
        callback=saver(
            "decide",
            lambda out: _render_verdict(motion, out.raw),
        ),
    )
    all_tasks = [propose, oppose, decide]
    named = {"propose": propose, "oppose": oppose, "decide": decide}
    if check_order:
        # Feature 002: the same judge task text and guardrail, with the two arguments
        # in the opposite order. Its context excludes `decide`, so it never sees the
        # first verdict. Two tasks may share a description: CrewAI tells them apart by id.
        swapped = task(
            "decide",
            context=[oppose, propose],
            guardrail=checked(CHECK_STAGE, verdict_guardrail),
            callback=saver(CHECK_STAGE, lambda out: _render_swapped(motion, out.raw)),
        )
        all_tasks.append(swapped)
        named[CHECK_STAGE] = swapped
    crew = Crew(
        agents=list(agents.values()),
        tasks=all_tasks,
        process=Process.sequential,
        verbose=False,
    )
    return crew, named, meter
