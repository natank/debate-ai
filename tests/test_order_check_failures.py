"""Feature 002, subtask 3: the order check never fails the run (FR-9.9).

One test per way the swapped stage can end badly. In every case the run must
succeed with its official verdict, and the check is reported as not completed.
"""
import json
import time

import pytest

from debate_ai import artifacts
from debate_ai.run import run_debate
from tests.fakes import make_stage_llm

P, O, D = "You are proposing", "You are in opposition", "Review the arguments"
FOR_TEXT = "ZX-FOR-MARKER " + "pro " * 200
AGAINST_TEXT = "QW-AGAINST-MARKER " + "con " * 200
REASON = "The two arguments were weighed on their specific points and one was clearly better. " * 4


def verdict(winner, marker="OFFICIAL"):
    return json.dumps({"winner": winner, "reasoning": f"{marker} {REASON}"})


def run(tmp_path, judge_replies, *, llm_kwargs=None, **kw):
    llm = make_stage_llm({P: [FOR_TEXT], O: [AGAINST_TEXT], D: judge_replies}, **(llm_kwargs or {}))
    result = run_debate("Cats are better", output_dir=tmp_path, llm_factory=lambda _m: llm,
                        write_backoff=0, check_order=True, **kw)
    return result, llm


def assert_official_verdict_intact(tmp_path, result, winner="for"):
    assert result.outcome == "success"
    assert result.stage is None and result.reason is None
    assert result.verdict.winner == winner and "OFFICIAL" in result.verdict.reasoning
    text = (tmp_path / result.run_id / "decide.md").read_text()
    assert f"**Winner:** {winner.capitalize()}" in text
    assert result.order_check.status == "not_completed" and result.order_check.reason
    assert result.order_check.swapped is None


def test_a_swapped_verdict_rejected_three_times_leaves_a_successful_run(tmp_path):
    result, llm = run(tmp_path, [verdict("for"), "not json"])
    assert_official_verdict_intact(tmp_path, result)
    assert result.order_check.reason == "the swapped verdict was rejected 3 times"
    assert result.stats["decide_swapped"].attempts == 3  # exactly three, not four
    assert result.stats["decide"].attempts == 1
    assert llm.count(D) == 1 + 3
    assert not (tmp_path / result.run_id / "decide_swapped.md").exists()
    assert "decide_swapped" not in result.artifacts and "decide" in result.artifacts


def test_the_time_limit_reached_during_the_swapped_call_leaves_a_successful_run(tmp_path):
    # Calls 0-2 are the debaters and the official judge; call 3 is the swapped judge.
    result, llm = run(tmp_path, [verdict("against"), verdict("for")],
                      llm_kwargs={"delays": {3: 2.5}}, time_limit=1.0)
    assert_official_verdict_intact(tmp_path, result, winner="against")
    assert result.order_check.reason == "the run's time limit was reached"
    time.sleep(2.5)  # let the abandoned worker finish: it must write nothing further
    assert not (tmp_path / result.run_id / "decide_swapped.md").exists()
    assert len(llm.calls) == 4  # and make no further model calls


def test_a_failed_write_of_the_swapped_file_leaves_a_successful_run(tmp_path, monkeypatch):
    real_replace = artifacts.os.replace

    def replace(src, dst):
        if str(dst).endswith("decide_swapped.md"):
            raise OSError("disk full")
        return real_replace(src, dst)

    monkeypatch.setattr(artifacts.os, "replace", replace)
    result, llm = run(tmp_path, [verdict("for"), verdict("against", "SWAPPED")])
    assert_official_verdict_intact(tmp_path, result)
    assert result.order_check.reason == "the swapped verdict could not be saved"
    assert llm.count(D) == 2  # the model was not asked again: only the write was retried
    assert not (tmp_path / result.run_id / "decide_swapped.md").exists()
    assert sorted(p.name for p in (tmp_path / result.run_id).iterdir()) == [
        "decide.md", "oppose.md", "propose.md"]  # no temporary files left behind


def test_an_error_raised_by_the_swapped_call_leaves_a_successful_run(tmp_path):
    result, _ = run(tmp_path, [verdict("for"), verdict("against")], llm_kwargs={"fail_from": 3})
    assert_official_verdict_intact(tmp_path, result)
    assert result.order_check.reason.startswith("the swapped call failed: ")


def test_tokens_from_a_failed_swapped_call_are_still_counted(tmp_path):
    result, _ = run(tmp_path, [verdict("for"), "not json"])
    assert result.stats["decide_swapped"].total_tokens == 3 * 140
    # Three completed stages at 140 tokens each, plus the three rejected swapped attempts.
    assert result.total.total_tokens == (3 + 3) * 140


# ---- what must NOT be softened ---------------------------------------------------

def test_a_failed_write_of_the_official_verdict_still_fails_the_run(tmp_path, monkeypatch):
    real_replace = artifacts.os.replace

    def replace(src, dst):
        if str(dst).endswith("decide.md"):
            raise OSError("disk full")
        return real_replace(src, dst)

    monkeypatch.setattr(artifacts.os, "replace", replace)
    result, _ = run(tmp_path, [verdict("for"), verdict("against")])
    assert result.outcome == "failed" and result.stage == "decide"
    assert "write failed" in result.reason


def test_the_debaters_stages_still_end_the_run_when_they_fail(tmp_path):
    llm = make_stage_llm({P: ["too short"], O: [AGAINST_TEXT], D: [verdict("for")]})
    result = run_debate("Cats are better", output_dir=tmp_path, llm_factory=lambda _m: llm,
                        write_backoff=0, check_order=True)
    assert result.outcome == "exhausted" and result.stage == "propose"
    assert result.order_check is None
    assert llm.count(D) == 0
