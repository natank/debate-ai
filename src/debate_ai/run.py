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
    STAGES,
    render_argument,
    render_verdict,
    write_with_retry,
)
from debate_ai.validation import Verdict, argument_guardrail, parse_verdict, verdict_guardrail

CONFIG_DIR = Path(__file__).resolve().parents[2] / "_docs" / "config"
MAX_ATTEMPTS = 3  # first call plus 2 retries, per stage; 3 stages => at most 9 calls
CALL_TIMEOUT_S = 60
RUN_TIME_LIMIT_S = 300
MAX_COMPLETION_TOKENS = 1000



class RunCancelled(RuntimeError):
    """Raised inside an abandoned run so its worker thread stops."""


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


def make_run_id(motion: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    slug = re.sub(r"[^a-z0-9]+", "-", motion.lower()).strip("-")[:40].strip("-") or "debate"
    return f"{now:%Y%m%d-%H%M%S}-{slug}"


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
) -> RunResult:
    motion = (motion or "").strip()
    if not motion:  # FR-1.3: no model call, no folder
        return RunResult("failed", motion, reason="the motion is empty")

    run_id = make_run_id(motion, now)
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

    crew, tasks = _build_crew(motion, config_dir, llm_factory, saver, cancelled)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(crew.kickoff, inputs={"motion": motion})
    try:
        future.result(timeout=time_limit)
    except FutureTimeout:
        result.outcome = "exhausted"
        cancelled.set()
        result.reason = f"the run exceeded its {time_limit:g} s limit"
        result.stage = _next_stage(completed)
        executor.shutdown(wait=False, cancel_futures=True)
        return result
    except Exception as e:
        result.stage = _next_stage(completed)
        result.reason = str(e)
        exhausted = isinstance(e, TimeoutError) or "guardrail validation" in str(e)
        result.outcome = "exhausted" if exhausted else "failed"
        executor.shutdown(wait=False)
        return _with_write_errors(result, write_errors)
    executor.shutdown(wait=False)

    if write_errors:
        return _with_write_errors(result, write_errors)
    result.outcome = "success"
    result.verdict = parse_verdict(tasks["decide"].output.raw)
    return result


def _render_verdict(motion: str, raw: str) -> str:
    v = parse_verdict(raw)
    return render_verdict(motion, v.winner, v.reasoning)


def _next_stage(completed: list) -> Optional[str]:
    return next((s for s in STAGES if s not in completed), None)


def _with_write_errors(result: RunResult, write_errors: dict) -> RunResult:
    if write_errors:
        stage, message = next(iter(write_errors.items()))
        result.outcome = "failed"
        result.stage = stage
        result.reason = f"artifact write failed: {message}"
    return result


def _build_crew(motion, config_dir, llm_factory, saver, cancelled):
    agents_cfg = yaml.safe_load((config_dir / "agents.yaml").read_text())
    tasks_cfg = yaml.safe_load((config_dir / "tasks.yaml").read_text())

    agents = {
        name: Agent(
            **{**cfg, "llm": llm_factory(cfg["llm"])},
            allow_delegation=False,
            memory=False,
            verbose=False,
        )
        for name, cfg in agents_cfg.items()
    }

    def checked(guardrail):
        def wrapper(output):
            if cancelled.is_set():
                raise RunCancelled("the run was cancelled after its time limit")
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
        guardrail=checked(argument_guardrail),
        callback=saver("propose", lambda out: render_argument(motion, "for", out.raw)),
    )
    oppose = task(
        "oppose",
        context=[],
        guardrail=checked(argument_guardrail),
        callback=saver("oppose", lambda out: render_argument(motion, "against", out.raw)),
    )
    decide = task(
        "decide",
        context=[propose, oppose],
        # No output_pydantic: with it, only the first bad reply is retried and a
        # second one raises a raw ValidationError (test 5). The guardrail validates
        # the JSON and we parse it ourselves.
        guardrail=checked(verdict_guardrail),
        callback=saver(
            "decide",
            lambda out: _render_verdict(motion, out.raw),
        ),
    )
    crew = Crew(
        agents=list(agents.values()),
        tasks=[propose, oppose, decide],
        process=Process.sequential,
        verbose=False,
    )
    return crew, {"propose": propose, "oppose": oppose, "decide": decide}
