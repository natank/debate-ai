"""End-to-end tests of the outer loop, with a fake LLM (no network, no API key)."""
import json
import os
import time
from datetime import datetime

import pytest

from debate_ai import artifacts
from debate_ai.artifacts import InvalidArgument, WriteFailed, write_artifact
from debate_ai.run import make_run_id, run_debate
from tests.fakes import make_stage_llm

MOTION = "Cats make better pets than dogs"
P, O, D = "You are proposing", "You are in opposition", "Review the arguments"
FOR_TEXT = "ZX-FOR-MARKER " + "pro " * 200
AGAINST_TEXT = "QW-AGAINST-MARKER " + "con " * 200
REASONING = "The proposition offered concrete points and the opposition answered them less well. " * 5


def verdict(winner="for", reasoning=REASONING):
    return json.dumps({"winner": winner, "reasoning": reasoning})


def good_scripts(**over):
    scripts = {P: [FOR_TEXT], O: [AGAINST_TEXT], D: [verdict()]}
    scripts.update(over)
    return scripts


def run(tmp_path, scripts, **kw):
    llm = make_stage_llm(scripts)
    result = run_debate(
        kw.pop("motion", MOTION),
        output_dir=tmp_path,
        llm_factory=lambda _model: llm,
        write_backoff=0,
        **kw,
    )
    return result, llm


# ---- happy path ---------------------------------------------------------------

def test_success_writes_three_artifacts_and_returns_the_verdict(tmp_path):
    result, llm = run(tmp_path, good_scripts())
    assert result.outcome == "success"
    assert result.verdict.winner == "for"
    assert set(result.artifacts) == {"propose", "oppose", "decide"}
    folder = tmp_path / result.run_id
    assert sorted(p.name for p in folder.iterdir()) == ["decide.md", "oppose.md", "propose.md"]
    assert "**Side:** For" in (folder / "propose.md").read_text()
    assert "**Side:** Against" in (folder / "oppose.md").read_text()
    assert "**Winner:** For" in (folder / "decide.md").read_text()
    assert llm.count(P) == llm.count(O) == llm.count(D) == 1


def test_opposition_never_receives_the_proposition(tmp_path):
    result, llm = run(tmp_path, good_scripts())
    oppose_prompt = next(c for c in llm.calls if O in c)
    assert "ZX-FOR-MARKER" not in oppose_prompt
    judge_prompt = next(c for c in llm.calls if D in c)
    assert "ZX-FOR-MARKER" in judge_prompt and "QW-AGAINST-MARKER" in judge_prompt


# ---- unique run folders -----------------------------------------------------

def test_two_identical_motions_in_the_same_second_get_separate_folders(tmp_path):
    same_second = datetime(2026, 9, 30, 12, 0, 0)
    first, _ = run(tmp_path, good_scripts(), now=same_second)
    second, _ = run(tmp_path, good_scripts(), now=same_second)
    third, _ = run(tmp_path, good_scripts(), now=same_second)
    assert [first.run_id, second.run_id, third.run_id] == [
        "20260930-120000-cats-make-better-pets-than-dogs",
        "20260930-120000-cats-make-better-pets-than-dogs-2",
        "20260930-120000-cats-make-better-pets-than-dogs-3",
    ]
    for r in (first, second, third):
        assert r.outcome == "success"
        assert sorted(p.name for p in (tmp_path / r.run_id).iterdir()) == [
            "decide.md", "oppose.md", "propose.md"
        ]


def test_motions_sharing_a_long_prefix_do_not_collide(tmp_path):
    same_second = datetime(2026, 9, 30, 12, 0, 0)
    prefix = "Social media does more harm than good for "
    a, _ = run(tmp_path, good_scripts(), motion=prefix + "teenagers", now=same_second)
    b, _ = run(tmp_path, good_scripts(), motion=prefix + "adults", now=same_second)
    assert a.run_id != b.run_id
    assert (tmp_path / a.run_id / "propose.md").exists() and (tmp_path / b.run_id / "propose.md").exists()


def test_a_folder_that_exists_only_by_name_is_not_reused(tmp_path):
    (tmp_path / "20260930-120000-cats-make-better-pets-than-dogs").mkdir()
    result, _ = run(tmp_path, good_scripts(), now=datetime(2026, 9, 30, 12, 0, 0))
    assert result.run_id.endswith("-dogs-2")


# ---- entry ----------------------------------------------------------------------

@pytest.mark.parametrize("motion", ["", "   ", "\n\t"])
def test_empty_motion_is_rejected_with_no_model_call_and_no_folder(tmp_path, motion):
    result, llm = run(tmp_path, good_scripts(), motion=motion)
    assert result.outcome == "failed" and "empty" in result.reason
    assert llm.calls == []
    assert list(tmp_path.iterdir()) == []


def test_run_id_is_a_safe_folder_name():
    rid = make_run_id("Is 5/3 > 1?? ../etc", datetime(2026, 9, 29, 12, 0, 0))
    assert rid == "20260929-120000-is-5-3-1-etc"
    assert make_run_id("???", datetime(2026, 9, 29, 12, 0, 0)).endswith("-debate")


# ---- retry and exhaustion -----------------------------------------------------

def test_short_argument_is_retried_with_the_reason_then_accepted(tmp_path):
    result, llm = run(tmp_path, good_scripts(**{P: ["too short", FOR_TEXT]}))
    assert result.outcome == "success"
    assert llm.count(P) == 2
    retry_prompt = [c for c in llm.calls if P in c][1]
    assert "words" in retry_prompt


def test_bad_winner_is_retried_then_accepted(tmp_path):
    result, llm = run(tmp_path, good_scripts(**{D: [verdict("tie"), verdict("against")]}))
    assert result.outcome == "success" and result.verdict.winner == "against"
    assert llm.count(D) == 2


def test_s1_exhausted_ends_the_run_at_propose_after_three_attempts(tmp_path):
    result, llm = run(tmp_path, good_scripts(**{P: ["too short"]}))
    assert result.outcome == "exhausted" and result.stage == "propose"
    assert llm.count(P) == 3
    assert llm.count(O) == 0 and llm.count(D) == 0
    assert result.artifacts == {}


def test_s2_exhausted_keeps_the_proposition_and_skips_the_judge(tmp_path):
    result, llm = run(tmp_path, good_scripts(**{O: ["too short"]}))
    assert result.outcome == "exhausted" and result.stage == "oppose"
    assert set(result.artifacts) == {"propose"}
    assert (tmp_path / result.run_id / "propose.md").exists()
    assert llm.count(D) == 0


def test_a_run_never_exceeds_nine_model_calls(tmp_path):
    result, llm = run(tmp_path, good_scripts(**{D: [verdict("tie")]}))
    assert result.outcome == "exhausted" and result.stage == "decide"
    assert len(llm.stages) <= 9


def test_wall_clock_limit_reports_exhausted(tmp_path):
    import time

    from tests.fakes import StageLLM

    class Slow(StageLLM):
        def call(self, messages, *a, **k):
            time.sleep(1.5)
            return super().call(messages, *a, **k)

    llm = Slow(model="fake", scripts=good_scripts())
    llm.calls, llm.stages = [], []
    result = run_debate(MOTION, output_dir=tmp_path, llm_factory=lambda _m: llm, time_limit=0.5)
    assert result.outcome == "exhausted" and "limit" in result.reason
    assert result.stage == "propose"
    time.sleep(2)  # the in-flight call finishes, then the cancelled run must stop
    assert llm.count(P) == 1 and llm.count(O) == 0 and llm.count(D) == 0
    assert not (tmp_path / result.run_id).exists()  # nothing written after the report


# ---- artifact failures ----------------------------------------------------------

def test_write_failure_is_retried_without_recalling_the_model_then_fails_the_run(
    tmp_path, monkeypatch
):
    attempts = []

    def broken_replace(src, dst):
        attempts.append(dst)
        raise OSError("disk full")

    monkeypatch.setattr(artifacts.os, "replace", broken_replace)
    result, llm = run(tmp_path, good_scripts())
    assert result.outcome == "failed" and "write failed" in result.reason
    assert result.stage == "propose"
    assert llm.count(P) == 1  # the write was retried, the model was not
    assert len([a for a in attempts if str(a).endswith("propose.md")]) == 3


# ---- write_artifact contract ------------------------------------------------

@pytest.mark.parametrize("run_id", ["", "../x", "a/b", "..", "a..b", ".hidden", "x" * 101])
def test_write_artifact_rejects_unsafe_run_ids(tmp_path, run_id):
    with pytest.raises(InvalidArgument):
        write_artifact(tmp_path, run_id, "propose", "text")


def test_write_artifact_rejects_bad_stage_and_empty_content(tmp_path):
    with pytest.raises(InvalidArgument):
        write_artifact(tmp_path, "r1", "../../evil", "text")
    with pytest.raises(InvalidArgument):
        write_artifact(tmp_path, "r1", "propose", "  \n")
    assert list(tmp_path.iterdir()) == []


def test_write_artifact_is_idempotent_and_leaves_no_temp_files(tmp_path):
    a = write_artifact(tmp_path, "r1", "propose", "hello")
    b = write_artifact(tmp_path, "r1", "propose", "hello")
    assert a.path == b.path == tmp_path / "r1" / "propose.md"
    assert a.path.read_text() == "hello"
    assert [p.name for p in (tmp_path / "r1").iterdir()] == ["propose.md"]


def test_write_artifact_reports_write_failed_and_cleans_up(tmp_path):
    (tmp_path / "r1").mkdir()
    os.chmod(tmp_path / "r1", 0o500)
    try:
        with pytest.raises(WriteFailed):
            write_artifact(tmp_path, "r1", "propose", "hello")
    finally:
        os.chmod(tmp_path / "r1", 0o700)


# ---- attempts and token usage ----------------------------------------------

def test_stats_record_one_attempt_and_the_tokens_of_each_stage(tmp_path):
    result, llm = run(tmp_path, good_scripts())
    for stage in ("propose", "oppose", "decide"):
        s = result.stats[stage]
        assert (s.attempts, s.prompt_tokens, s.completion_tokens, s.total_tokens) == (1, 100, 40, 140)
    # One LLM object is shared by both agents here; it must not be counted twice.
    assert result.total.attempts == 3 and result.total.total_tokens == 420


def test_a_retry_shows_as_two_attempts_and_double_the_tokens(tmp_path):
    result, _ = run(tmp_path, good_scripts(**{P: ["too short", FOR_TEXT]}))
    assert result.stats["propose"].attempts == 2
    assert result.stats["propose"].total_tokens == 280
    assert result.stats["oppose"].attempts == 1


def test_an_exhausted_run_still_reports_the_attempts_it_used(tmp_path):
    result, _ = run(tmp_path, good_scripts(**{O: ["too short"]}))
    assert result.outcome == "exhausted"
    assert result.stats["propose"].attempts == 1
    assert result.stats["oppose"].attempts == 3
    assert result.stats["oppose"].total_tokens == 420
    assert "decide" not in result.stats
    assert result.total.attempts == 4
