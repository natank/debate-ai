"""Feature 002, subtask 0: the order-check stage in the stage list and the report."""
import json

import pytest

from debate_ai.artifacts import (
    ALL_STAGES,
    CHECK_STAGE,
    STAGES,
    InvalidArgument,
    run_stages,
    write_artifact,
)
from debate_ai.cli import format_report
from debate_ai.run import RunResult, StageStats, _next_stage, run_debate
from tests.fakes import make_stage_llm


def test_write_artifact_accepts_the_swapped_stage(tmp_path):
    art = write_artifact(tmp_path, "r1", "decide_swapped", "verdict text")
    assert art.path == tmp_path / "r1" / "decide_swapped.md"
    assert art.path.read_text() == "verdict text"


@pytest.mark.parametrize("stage", ["swapped", "decide_swapped2", "../decide", "decide_swapped/", "", "DECIDE"])
def test_write_artifact_still_rejects_unknown_stages(tmp_path, stage):
    with pytest.raises(InvalidArgument):
        write_artifact(tmp_path, "r1", stage, "text")
    assert list(tmp_path.iterdir()) == []


def test_a_run_has_three_stages_or_four_with_the_check():
    assert run_stages(False) == ("propose", "oppose", "decide") == STAGES
    assert run_stages(True) == ("propose", "oppose", "decide", "decide_swapped") == ALL_STAGES
    assert ALL_STAGES[-1] == CHECK_STAGE


def test_the_failing_stage_lookup_uses_the_runs_own_stage_list():
    done = ["propose", "oppose", "decide"]
    # A normal run that has finished everything has no next stage. It must never
    # be told its next stage is the order check it did not ask for.
    assert _next_stage(done, run_stages(False)) is None
    assert _next_stage(done, run_stages(True)) == "decide_swapped"
    assert _next_stage([], run_stages(False)) == "propose"
    assert _next_stage(["propose"], run_stages(True)) == "oppose"
    assert _next_stage(["propose", "oppose"], run_stages(False)) == "decide"


def test_a_normal_run_that_fails_never_reports_the_check_stage(tmp_path):
    llm = make_stage_llm({
        "You are proposing": ["pro " * 200],
        "You are in opposition": ["con " * 200],
        "Review the arguments": [json.dumps({"winner": "tie", "reasoning": "x"})],
    })
    result = run_debate("Cats are better", output_dir=tmp_path, llm_factory=lambda _m: llm,
                        write_backoff=0)
    assert result.outcome == "exhausted" and result.stage == "decide"
    assert "decide_swapped" not in result.stats


def test_the_report_shows_the_swapped_stage_as_swapped_and_stays_aligned():
    result = RunResult(
        "success", "m", run_id="r1",
        stats={s: StageStats(1, 100, 40, 140) for s in ALL_STAGES},
    )
    lines = format_report(result)
    assert [l.split()[0] for l in lines] == ["propose", "oppose", "decide", "swapped", "total"]
    assert not any("decide_swapped" in l for l in lines)
    # The attempts column starts at the same place on every line.
    assert {l.index("1 attempt") if "1 attempt" in l else l.index("4 attempts") for l in lines} == {11}
