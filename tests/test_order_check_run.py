"""Feature 002, subtask 2: the fourth stage and its success paths (fake model)."""
import json

import pytest

from debate_ai.run import run_debate
from tests.fakes import make_stage_llm

P, O, D = "You are proposing", "You are in opposition", "Review the arguments"
FOR_TEXT = "ZX-FOR-MARKER " + "pro " * 200
AGAINST_TEXT = "QW-AGAINST-MARKER " + "con " * 200
REASON = "The two arguments were weighed on their specific points and one was clearly better. " * 4


def verdict(winner, marker="x"):
    return json.dumps({"winner": winner, "reasoning": f"{marker} {REASON}"})


def run(tmp_path, judge_replies, *, check_order=True, propose=None, oppose=None, **kw):
    llm = make_stage_llm({
        P: [propose or FOR_TEXT], O: [oppose or AGAINST_TEXT], D: judge_replies,
    })
    result = run_debate("Cats are better", output_dir=tmp_path, llm_factory=lambda _m: llm,
                        write_backoff=0, check_order=check_order, **kw)
    return result, llm


def judge_prompts(llm):
    return [c for c in llm.calls if D in c]


# ---- the check is off by default ------------------------------------------------

def test_without_the_flag_nothing_changes(tmp_path):
    result, llm = run(tmp_path, [verdict("for")], check_order=False)
    assert result.outcome == "success" and result.order_check is None
    assert llm.count(D) == 1
    assert sorted(p.name for p in (tmp_path / result.run_id).iterdir()) == [
        "decide.md", "oppose.md", "propose.md"]
    assert "decide_swapped" not in result.stats and "decide_swapped" not in result.artifacts


def test_the_flag_defaults_to_off(tmp_path):
    llm = make_stage_llm({P: [FOR_TEXT], O: [AGAINST_TEXT], D: [verdict("for")]})
    result = run_debate("Cats are better", output_dir=tmp_path, llm_factory=lambda _m: llm)
    assert result.order_check is None and llm.count(D) == 1


# ---- the check on: outcomes ---------------------------------------------------

def test_the_same_winner_in_both_orders_is_stable(tmp_path):
    result, llm = run(tmp_path, [verdict("against", "FIRST"), verdict("against", "SECOND")])
    assert result.outcome == "success" and llm.count(D) == 2
    assert result.order_check.status == "stable"
    assert result.verdict.winner == "against" and "FIRST" in result.verdict.reasoning
    assert "SECOND" in result.order_check.swapped.reasoning
    folder = tmp_path / result.run_id
    assert sorted(p.name for p in folder.iterdir()) == [
        "decide.md", "decide_swapped.md", "oppose.md", "propose.md"]


@pytest.mark.parametrize("first,second,favored", [("for", "against", "first"), ("against", "for", "last")])
def test_a_flip_is_sensitive_and_the_official_verdict_stays_the_first(tmp_path, first, second, favored):
    result, _ = run(tmp_path, [verdict(first), verdict(second)])
    assert result.outcome == "success"
    assert result.order_check.status == "sensitive" and result.order_check.favored == favored
    assert result.verdict.winner == first  # the official verdict is never changed
    assert f"**Winner:** {first.capitalize()}" in (tmp_path / result.run_id / "decide.md").read_text()
    assert f"**Winner:** {second.capitalize()}" in (tmp_path / result.run_id / "decide_swapped.md").read_text()


def test_the_swapped_artifact_says_what_it_is(tmp_path):
    result, _ = run(tmp_path, [verdict("for"), verdict("against")])
    text = (tmp_path / result.run_id / "decide_swapped.md").read_text()
    assert text.startswith("# Verdict (arguments in swapped order)")
    assert "**Motion:** Cats are better" in text and "`decide.md`" in text
    assert result.artifacts["decide_swapped"] == tmp_path / result.run_id / "decide_swapped.md"


# ---- the swapped call is the same question with the order reversed --------------

def test_the_swapped_prompt_reverses_the_arguments_and_nothing_else(tmp_path):
    _, llm = run(tmp_path, [verdict("for", "FIRST-VERDICT"), verdict("against", "SECOND-VERDICT")])
    first, second = judge_prompts(llm)
    assert first.index("ZX-FOR-MARKER") < first.index("QW-AGAINST-MARKER")
    assert second.index("QW-AGAINST-MARKER") < second.index("ZX-FOR-MARKER")
    normal = first.replace(FOR_TEXT.strip(), "<1>").replace(AGAINST_TEXT.strip(), "<2>")
    swapped = second.replace(AGAINST_TEXT.strip(), "<1>").replace(FOR_TEXT.strip(), "<2>")
    assert normal == swapped  # identical apart from the order of the two arguments


def test_neither_judge_sees_the_other_judges_verdict(tmp_path):
    _, llm = run(tmp_path, [verdict("for", "FIRST-VERDICT"), verdict("against", "SECOND-VERDICT")])
    first, second = judge_prompts(llm)
    assert "FIRST-VERDICT" not in second
    assert "SECOND-VERDICT" not in first


def test_the_debaters_still_never_see_each_other_or_a_verdict(tmp_path):
    _, llm = run(tmp_path, [verdict("for"), verdict("against")])
    opposition = next(c for c in llm.calls if O in c)
    assert "ZX-FOR-MARKER" not in opposition
    assert D not in opposition


# ---- accounting and limits ------------------------------------------------------

def test_the_swapped_stage_is_counted_in_the_stats_and_the_total(tmp_path):
    result, _ = run(tmp_path, [verdict("for"), verdict("for")])
    s = result.stats["decide_swapped"]
    assert (s.attempts, s.prompt_tokens, s.completion_tokens, s.total_tokens) == (1, 100, 40, 140)
    assert result.total.attempts == 4 and result.total.total_tokens == 560


def test_a_rejected_swapped_reply_is_retried_like_any_judge_reply(tmp_path):
    result, llm = run(tmp_path, [verdict("for"), "not json", verdict("against")])
    assert result.outcome == "success" and result.order_check.status == "sensitive"
    assert result.stats["decide_swapped"].attempts == 2
    assert result.stats["decide"].attempts == 1
    assert llm.count(D) == 3


def test_a_run_makes_at_most_twelve_model_calls_with_the_check(tmp_path):
    result, llm = run(tmp_path, [verdict("for"), verdict("tie")])
    assert len(llm.stages) <= 12


# ---- the first three stages behave as today --------------------------------------

def test_when_the_official_judge_fails_the_check_never_starts(tmp_path):
    result, llm = run(tmp_path, [verdict("tie")])
    assert result.outcome == "exhausted" and result.stage == "decide"
    assert llm.count(D) == 3  # the official judge's three attempts, and no more
    assert "decide_swapped" not in result.stats
    assert not (tmp_path / result.run_id / "decide_swapped.md").exists()
    assert result.order_check is None
