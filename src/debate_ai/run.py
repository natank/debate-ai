"""The outer control loop (design step 4, section 2, and step 5, section 5).

Owns what no stage owns: motion entry, run id, stage sequencing, artifact
writing, run-level limits, and the success / exhausted / failed report.
Stage-level retry and validation are delegated to CrewAI guardrails.
"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional

from crewai import LLM

from debate_ai.artifacts import CHECK_STAGE, run_stages, write_with_retry
from debate_ai.crew import MAX_ATTEMPTS, DebateCrew, StageStats
from debate_ai.order_check import OrderCheck, compare_verdicts, not_completed
from debate_ai.validation import Verdict, parse_verdict

CALL_TIMEOUT_S = 60
RUN_TIME_LIMIT_S = 300
MAX_COMPLETION_TOKENS = 1000


Outcome = Literal["success", "exhausted", "failed"]


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
    config_dir: Optional[Path] = None,  # None: the config beside crew.py
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

    crew_builder = DebateCrew(
        motion=motion,
        llm_factory=llm_factory,
        saver=saver,
        cancelled=cancelled,
        stats=result.stats,
        check_order=check_order,
        config_dir=config_dir,
    )
    crew = crew_builder.crew()
    tasks = crew_builder.stage_tasks()
    meter = crew_builder.meter

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
