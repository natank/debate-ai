import pytest

from debate_ai.batch import Entry, parse_motions
from debate_ai.run import RunResult, StageStats
from debate_ai.summary import LIMIT_SENTENCE, build_summary
from debate_ai.validation import Verdict


def ok(winner, *, tokens=2000, attempts=3, run_id="r"):
    return RunResult(
        "success", "m", run_id=run_id, verdict=Verdict(winner=winner, reasoning="x"),
        stats={"decide": StageStats(attempts, tokens - 500, 500, tokens)},
    )


def bad(outcome="exhausted", stage="oppose", tokens=1400, attempts=4, run_id="r"):
    return RunResult(outcome, "m", run_id=run_id, stage=stage, reason="why",
                     stats={stage: StageStats(attempts, tokens - 300, 300, tokens)})


def entries(text):
    return parse_motions(text)


# ---- rate ---------------------------------------------------------------------

def test_for_win_rate_excludes_exhausted_runs_and_counts_them_separately():
    e = entries("A\nB\nC\nD\n")
    out = build_summary("b1", e, [ok("for"), ok("against"), bad(), ok("for")], complete=True)
    assert "2 of 3 completed runs (67%)." in out
    assert "Not counted in the rate: 1 exhausted." in out
    assert "exhausted (oppose)" in out


def test_no_completed_runs_gives_no_rate():
    out = build_summary("b1", entries("A\n"), [bad("failed", "propose")], complete=True)
    assert "No completed runs." in out and "failed (propose)" in out


@pytest.mark.parametrize("n,warned", [(9, True), (10, False)])
def test_small_sample_line_appears_under_ten_completed_runs(n, warned):
    e = entries("\n".join(f"M{i}" for i in range(n)))
    out = build_summary("b1", e, [ok("for") for _ in range(n)], complete=True)
    assert ("Too few runs to conclude anything." in out) is warned


# ---- pairs --------------------------------------------------------------------

@pytest.mark.parametrize("a,b,consistent,phrase", [
    ("for", "against", True, 'sided with "Cats" both times'),
    ("against", "for", True, 'sided with "Dogs" both times'),
    ("for", "for", False, "sided with the proposition both times"),
    ("against", "against", False, "sided with the opposition both times"),
])
def test_pair_consistency_four_cases(a, b, consistent, phrase):
    out = build_summary("b1", entries("Cats | Dogs\n"), [ok(a), ok(b)], complete=True)
    assert phrase in out
    assert f"Consistent pairs: {int(consistent)} of 1 analyzed." in out
    assert ("Not consistent: Cats / Dogs." in out) is (not consistent)


def test_a_pair_with_an_unfinished_side_is_not_analyzed():
    out = build_summary("b1", entries("Cats | Dogs\n"), [ok("for"), bad()], complete=True)
    assert "Not analyzed" in out and "Consistent pairs: 0 of 0 analyzed." in out


def test_no_pairs_section_when_the_batch_has_no_pairs():
    out = build_summary("b1", entries("A\nB\n"), [ok("for"), ok("against")], complete=True)
    assert "## Pairs" not in out


# ---- limit sentence, skipped rows, header, totals ------------------------------

def test_the_limit_sentence_is_in_every_summary():
    for complete in (True, False):
        out = build_summary("b1", entries("A\n"), [None], complete=complete)
        assert LIMIT_SENTENCE in out


def test_skipped_and_pending_rows_and_both_header_states():
    e = entries("A\nB\nC\n")
    done = build_summary("b1", e, [ok("for"), None, None], complete=True)
    assert "Status: complete" in done and done.count("| skipped |") == 2
    assert "2 skipped" in done
    live = build_summary("b1", e, [ok("for"), None, None], complete=False)
    assert "Status: in progress (1 of 3 done)" in live and live.count("| pending |") == 2


def test_totals_and_per_motion_rows():
    e = entries("A\nB\n")
    out = build_summary("b1", e, [ok("for", tokens=2010, run_id="r1"), ok("against", tokens=1990, run_id="r2")], complete=True)
    assert "· 4,000 tokens · 6 attempts" in out
    assert "6 attempts, 4,000 tokens (3,000 prompt + 1,000 completion)." in out
    assert "| 1 | A | success | For | 3 | 2,010 | r1 |" in out
    assert "| 2 | B | success | Against | 3 | 1,990 | r2 |" in out


def test_building_a_summary_writes_no_files_and_calls_no_model(tmp_path, monkeypatch):
    import debate_ai.run as run

    monkeypatch.setattr(run, "run_debate", lambda *a, **k: pytest.fail("model run"))
    monkeypatch.chdir(tmp_path)
    build_summary("b1", entries("A | B\n"), [ok("for"), ok("against")], complete=True)
    assert list(tmp_path.iterdir()) == []
