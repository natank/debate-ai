"""Tests 2-5 (design step 5, section 6): CrewAI behavior the design relies on.

Each test records what CrewAI actually does. Where it differs from what the
design assumed, the test name and comments say so.
"""
import time
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError
from crewai import Crew, Process, Task

from tests.fakes import make_agent, make_llm


class Verdict(BaseModel):
    winner: Literal["for", "against"]
    reasoning: str


def verdict_guardrail(out):
    try:
        Verdict.model_validate_json(out.raw)
        return True, out.raw
    except ValidationError as e:
        return False, f"invalid verdict: {e.errors()[0]['msg']}"


def solo(llm, **task_kw):
    agent = make_agent(llm)
    task = Task(description="d", expected_output="e", agent=agent, **task_kw)
    return Crew(agents=[agent], tasks=[task], verbose=False), task


# ---- Test 2: shared agent state ------------------------------------------

def test_2_shared_agent_leaks_nothing_between_tasks_or_runs():
    llm = make_llm(route={"TASK-A": "reply SECRET-A", "TASK-B": "reply B"})
    agent = make_agent(llm, memory=False)
    a = Task(description="TASK-A first motion", expected_output="e", agent=agent, context=[])
    b = Task(description="TASK-B", expected_output="e", agent=agent, context=[])
    crew = Crew(agents=[agent], tasks=[a, b], process=Process.sequential, verbose=False)

    crew.kickoff()
    crew.kickoff()  # a second run on the same agent and crew

    b_prompts = [c for c in llm.calls if "TASK-B" in c]
    assert len(b_prompts) == 2
    assert all("SECRET-A" not in p for p in b_prompts)


# ---- Test 3: limits ---------------------------------------------------------

def test_3_guardrail_max_retries_2_gives_exactly_3_attempts():
    llm = make_llm(replies=["bad"])
    crew, _ = solo(llm, guardrail=lambda o: (False, "too short"), guardrail_max_retries=2)
    with pytest.raises(Exception, match="failed guardrail validation after 2 retries"):
        crew.kickoff()
    assert len(llm.calls) == 3


def test_3_max_execution_time_reports_late_it_does_not_interrupt():
    """Design assumed a 60 s cut-off. CrewAI raises TimeoutError only after
    the blocking call returns, so the timeout must also be set on the LLM
    client (or enforced by the application)."""
    llm = make_llm(delay=2.0)
    agent = make_agent(llm, max_execution_time=1)
    task = Task(description="d", expected_output="e", agent=agent)
    start = time.time()
    with pytest.raises(TimeoutError):
        Crew(agents=[agent], tasks=[task], verbose=False).kickoff()
    assert time.time() - start >= 2.0


# ---- Test 4: failure in one branch -----------------------------------------

def branch_crew(fail: str):
    llm = make_llm(route={"S1TASK": "reply-s1", "S2TASK": "reply-s2", "S3TASK": "reply-s3"})
    agent = make_agent(llm)
    bad = {"guardrail": lambda o: (False, "nope"), "guardrail_max_retries": 1}
    s1 = Task(description="S1TASK", expected_output="e", agent=agent, context=[],
              async_execution=True, **(bad if fail == "s1" else {}))
    s2 = Task(description="S2TASK", expected_output="e", agent=agent, context=[],
              **(bad if fail == "s2" else {}))
    s3 = Task(description="S3TASK", expected_output="e", agent=agent, context=[s1, s2])
    crew = Crew(agents=[agent], tasks=[s1, s2, s3], process=Process.sequential, verbose=False)
    return crew, llm, (s1, s2, s3)


def test_4_s1_failure_stops_the_run_and_s2_never_runs():
    """Design (step 4, 2.3) expected S2's valid output to be kept. In CrewAI
    the exception aborts kickoff before S2 starts."""
    crew, llm, (s1, s2, s3) = branch_crew("s1")
    with pytest.raises(Exception, match="failed guardrail validation"):
        crew.kickoff()
    assert llm.called("S2TASK") == 0 and llm.called("S3TASK") == 0
    assert s2.output is None and s3.output is None


def test_4_s2_failure_keeps_s1_output_and_skips_the_judge():
    crew, llm, (s1, s2, s3) = branch_crew("s2")
    with pytest.raises(Exception, match="failed guardrail validation"):
        crew.kickoff()
    assert s1.output is not None and s1.output.raw == "reply-s1"
    assert llm.called("S3TASK") == 0


# ---- Test 5: verdict shape --------------------------------------------------

def test_5_output_pydantic_alone_fails_hard_without_retry():
    """Design assumed a bad `winner` would be rejected and retried. It raises
    ValidationError on the first call."""
    llm = make_llm(replies=['{"winner":"tie","reasoning":"x"}', '{"winner":"for","reasoning":"y"}'])
    crew, _ = solo(llm, output_pydantic=Verdict)
    with pytest.raises(ValidationError):
        crew.kickoff()
    assert len(llm.calls) == 1


def test_5_guardrail_rejects_bad_winner_and_retries_with_the_reason():
    llm = make_llm(replies=['{"winner":"tie","reasoning":"x"}', '{"winner":"for","reasoning":"y"}'])
    crew, _ = solo(llm, output_pydantic=Verdict, guardrail=verdict_guardrail,
                   guardrail_max_retries=2)
    result = crew.kickoff()
    assert result.pydantic.winner == "for"
    assert len(llm.calls) == 2
    assert "invalid verdict" in llm.calls[1]  # the rejection reason reaches the retry
