"""Feature 002, subtask 4: the order check in the batch summary."""
import pytest

from debate_ai.batch import parse_motions
from debate_ai.order_check import compare_verdicts, not_completed
from debate_ai.summary import LIMIT_SENTENCE, build_summary
from debate_ai.validation import Verdict
from tests.test_summary import bad, ok

# The summary of this fixed batch as it was before feature 002, recorded verbatim.
GOLDEN = '# Batch summary\nBatch b1 · 4 motions · 2 completed · 5,395 tokens · 10 attempts\nStatus: complete\n\n| # | Motion | Outcome | Winner | Attempts | Tokens | Run folder |\n|---|---|---|---|---|---|---|\n| 1 | Cats | success | For | 3 | 2,010 | r1 |\n| 2 | Dogs | success | For | 3 | 1,985 | r2 |\n| 3 | Remote work | exhausted (oppose) | - | 4 | 1,400 | r3 |\n| 4 | Homework | skipped | - | - | - | - |\n\n## For-win rate\n2 of 2 completed runs (100%). Too few runs to conclude anything.\n\nNot counted in the rate: 1 exhausted, 1 skipped.\n\n## Pairs\n| Pair | Result on A | Result on B | Reading |\n|---|---|---|---|\n| Cats / Dogs | For | For | Not consistent: sided with the proposition both times |\n\nConsistent pairs: 0 of 1 analyzed.\nNot consistent: Cats / Dogs.\n\n## Totals\n10 attempts, 5,395 tokens (4,095 prompt + 1,300 completion).\n\n## Read this carefully\nA skew toward "for" cannot be told apart from an ordering effect: the judge always sees the proposition first. These are rates, not a finding of bias.\n'


def v(w):
    return Verdict(winner=w, reasoning="x")


def checked(winner, swapped_winner, *, tokens=3000, run_id="r"):
    """A completed debate that was order-checked."""
    r = ok(winner, tokens=tokens, attempts=4, run_id=run_id)
    r.order_check = compare_verdicts(v(winner), v(swapped_winner))
    return r


def unfinished_check(winner="for", run_id="r"):
    r = ok(winner, run_id=run_id)
    r.order_check = not_completed("the swapped verdict was rejected 3 times")
    return r


# ---- without the check: nothing changes -----------------------------------------------

def test_a_batch_without_the_check_is_byte_for_byte_what_it_was_before():
    e = parse_motions("Cats | Dogs\nRemote work\nHomework\n")
    r = [ok("for", tokens=2010, run_id="r1"), ok("for", tokens=1985, run_id="r2"), bad(run_id="r3"), None]
    assert build_summary("b1", e, r, complete=True) == GOLDEN


def test_no_order_check_column_section_or_paragraph_without_the_flag():
    out = build_summary("b1", parse_motions("A\nB\n"), [ok("for"), ok("against")], complete=True)
    assert "Order check" not in out and "order-sensitive" not in out.lower()
    assert out.rstrip().endswith(LIMIT_SENTENCE)
    assert "| Winner | Attempts |" in out


# ---- with the check ---------------------------------------------------------------------

def test_the_column_and_section_appear_with_the_right_counts():
    e = parse_motions("A\nB\nC\nD\n")
    r = [checked("for", "for"), checked("for", "against"), checked("against", "for"), unfinished_check()]
    out = build_summary("b1", e, r, complete=True)
    assert "| # | Motion | Outcome | Winner | Order check | Attempts | Tokens | Run folder |" in out
    assert "|---|---|---|---|---|---|---|---|" in out
    assert "| 1 | A | success | For | stable | 4 |" in out
    assert "| 2 | B | success | For | sensitive (first) | 4 |" in out
    assert "| 3 | C | success | Against | sensitive (last) | 4 |" in out
    assert "| 4 | D | success | For | not completed | 3 |" in out
    assert ("## Order check\nChecked 3 of 4 completed debates. Order-stable: 1. Order-sensitive: 2 "
            "(favored the first-read argument: 1; the last-read: 1). Not completed: 1.") in out


def test_the_closing_paragraph_says_what_the_data_shows():
    e = parse_motions("A\nB\n")
    out = build_summary("b1", e, [checked("for", "for"), checked("for", "against")], complete=True)
    tail = out.split("## Read this carefully\n")[1].strip()
    assert tail == (
        "In 1 of 2 checked debates the winner changed when the arguments were swapped. That is "
        "the reading order or ordinary variation between judge calls; this check cannot separate "
        "the two. In the rest, the same side won in both orders. The for-win rate above uses the "
        "official verdict only. These are rates, not a finding of bias."
    )
    assert LIMIT_SENTENCE not in out


@pytest.mark.parametrize("pairs,expected_start", [
    ([("for", "for"), ("against", "against")], "In none of the 2 checked debates did the winner change"),
    ([("for", "against"), ("against", "for")], "In all 2 checked debates the winner changed"),
    ([("for", "against")], "In the only checked debate the winner changed"),
    ([("for", "for")], "In none of the 1 checked debate did the winner change"),
])
def test_the_closing_paragraph_wording_for_each_mix(pairs, expected_start):
    e = parse_motions("\n".join(f"M{i}" for i in range(len(pairs))))
    out = build_summary("b1", e, [checked(a, b) for a, b in pairs], complete=True)
    assert out.split("## Read this carefully\n")[1].startswith(expected_start)


def test_when_every_check_failed_the_original_limit_sentence_stays():
    e = parse_motions("A\nB\n")
    out = build_summary("b1", e, [unfinished_check(), unfinished_check()], complete=True)
    assert "Order check" in out  # the column and section still show what happened
    assert "Not completed: 2." in out and "Checked 0 of 2 completed debates." in out
    assert out.rstrip().endswith(LIMIT_SENTENCE)


def test_a_debate_that_did_not_finish_shows_a_dash_in_the_check_column():
    e = parse_motions("A\nB\nC\n")
    out = build_summary("b1", e, [checked("for", "for"), bad(), None], complete=False)
    assert "| 2 | B | exhausted (oppose) | - | - | 4 |" in out
    assert "| 3 | C | pending | - | - | - | - | - |" in out
    assert "Checked 1 of 1 completed debates." in out


# ---- the numbers that must not move ---------------------------------------------------

def test_the_for_win_rate_and_pair_consistency_use_the_official_verdict_only():
    e = parse_motions("Cats | Dogs\n")
    with_check = build_summary("b1", e, [checked("for", "against"), checked("against", "for")], complete=True)
    without = build_summary(
        "b1", e, [ok("for", attempts=4, tokens=3000), ok("against", attempts=4, tokens=3000)], complete=True
    )
    for text in (with_check, without):
        assert "1 of 2 completed runs (50%)." in text
        assert "Consistent pairs: 1 of 1 analyzed." in text


def test_attempts_and_tokens_include_the_swapped_stage():
    e = parse_motions("A\n")
    out = build_summary("b1", e, [checked("for", "for", tokens=3002)], complete=True)
    assert "· 3,002 tokens · 4 attempts" in out
    assert "4 attempts, 3,002 tokens" in out
