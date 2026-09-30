from pathlib import Path

from debate_ai import cli
from debate_ai.run import RunResult, StageStats
from debate_ai.validation import Verdict


def success_result():
    return RunResult(
        "success", "m", run_id="r1",
        artifacts={s: Path(f"output/r1/{s}.md") for s in ("propose", "oppose", "decide")},
        verdict=Verdict(winner="against", reasoning="x"),
        stats={
            "propose": StageStats(1, 900, 340, 1240),
            "oppose": StageStats(2, 1800, 700, 2500),
            "decide": StageStats(1, 1500, 200, 1700),
        },
    )


def test_report_lists_each_stage_with_attempts_tokens_path_and_a_total():
    lines = cli.format_report(success_result())
    assert len(lines) == 4
    assert "1 attempt " in lines[0] and "1,240 tokens (900 prompt + 340 completion)" in lines[0]
    assert "output/r1/propose.md" in lines[0]
    assert "2 attempts" in lines[1]
    assert lines[3].split()[0] == "total" and "4 attempts" in lines[3] and "5,440 tokens" in lines[3]


def test_success_prints_winner_and_report_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda *a, **k: success_result())
    assert cli.main(["some motion"]) == 0
    out = capsys.readouterr()
    assert "Winner: Against" in out.out and "total" in out.out and out.err == ""


def test_failure_prints_reason_and_partial_report_to_stderr(monkeypatch, capsys):
    failed = RunResult(
        "exhausted", "m", run_id="r1", stage="oppose", reason="3 attempts rejected",
        artifacts={"propose": Path("output/r1/propose.md")},
        stats={"propose": StageStats(1, 100, 40, 140), "oppose": StageStats(3, 300, 120, 420)},
    )
    monkeypatch.setattr(cli, "run_debate", lambda *a, **k: failed)
    assert cli.main(["some motion"]) == 1
    out = capsys.readouterr()
    assert "Run exhausted at stage 'oppose'" in out.err
    assert "3 attempts" in out.err and "560 tokens" in out.err and out.out == ""


def test_empty_motion_failure_has_no_report(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_debate", lambda *a, **k: RunResult("failed", "", reason="the motion is empty"))
    assert cli.main([" "]) == 2
    err = capsys.readouterr().err
    assert "motion is empty" in err and "total" not in err


# ---- batch mode (feature 001) ------------------------------------------------

import pytest  # noqa: E402

from debate_ai.cli import format_batch_summary_line, format_progress_line  # noqa: E402


def one(winner="for", tokens=2010):
    return RunResult("success", "m", run_id="r", verdict=Verdict(winner=winner, reasoning="x"),
                     stats={"decide": StageStats(3, tokens - 500, 500, tokens)})


def stuck(outcome="exhausted", stage="oppose", tokens=1420):
    return RunResult(outcome, "m", run_id="r", stage=stage, reason="why",
                     stats={stage: StageStats(3, tokens - 300, 300, tokens)})


def test_progress_line_matches_the_design_layout():
    line = format_progress_line(1, 3, "Cats make better pets than dogs", one("for", 2010))
    assert line.startswith("[1/3] Cats make better pets than dogs ")
    assert line.endswith(" For      2,010 tokens")
    assert len(line) == 80 and " ..." in line


def test_progress_line_shows_the_outcome_and_stage_for_an_unfinished_run():
    line = format_progress_line(2, 3, "Dogs make better pets than cats", stuck())
    assert line.endswith("exhausted (oppose) 1,420 tokens") and len(line) <= 80


def test_a_long_motion_is_shortened_to_fit_80_columns():
    long_motion = "Social media does more harm than good for teenagers in modern democratic societies today"
    line = format_progress_line(10, 12, long_motion, one("against", 12345))
    assert len(line) <= 80 and "..." in line and line.startswith("[10/12] Social media")
    assert line.endswith("Against  12,345 tokens")


def test_batch_summary_line_counts_completed_exhausted_skipped_and_totals():
    from debate_ai.batch import BatchResult, parse_motions

    entries = parse_motions("A\nB\nC\nD\n")
    result = BatchResult("b1", None, None, entries, [one(), stuck(), one(), None])
    assert format_batch_summary_line(result) == (
        "Batch b1: 2 of 4 completed, 1 exhausted, 1 skipped, 9 attempts, 5,440 tokens"
    )


def batch_file(tmp_path, text):
    f = tmp_path / "motions.txt"
    f.write_text(text, encoding="utf-8")
    return str(f)


def test_a_complete_batch_prints_progress_and_the_final_lines_to_stdout(monkeypatch, capsys, tmp_path):
    results = iter([one("for"), one("against"), one("for")])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    code = cli.main(["--batch", batch_file(tmp_path, "A | B\nC\n"), "--output-dir", str(tmp_path)])
    out = capsys.readouterr()
    assert code == 0 and out.err == ""
    lines = out.out.strip().splitlines()
    assert lines[0].startswith("[1/3] A ") and lines[1].startswith("[2/3] B ") and lines[2].startswith("[3/3] C ")
    assert any(l.startswith("Batch ") and "3 of 3 completed" in l for l in lines)
    assert any(l.startswith("Summary: ") and l.endswith("summary.md") for l in lines)
    assert list(tmp_path.glob("batch-*/summary.md"))


def test_an_exhausted_run_gives_exit_code_1_and_the_batch_continues(monkeypatch, capsys, tmp_path):
    results = iter([one(), stuck(), one()])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    code = cli.main(["--batch", batch_file(tmp_path, "A\nB\nC\n"), "--output-dir", str(tmp_path)])
    out = capsys.readouterr()
    assert code == 1
    assert "exhausted (oppose)" in out.out and "2 of 3 completed, 1 exhausted" in out.out


def test_a_budget_stop_reason_goes_to_stderr_and_the_exit_code_is_1(monkeypatch, capsys, tmp_path):
    results = iter([one(tokens=2010), one(tokens=1985), one()])
    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: next(results))
    code = cli.main(["--batch", batch_file(tmp_path, "A\nB\nC\n"), "--budget", "3000",
                     "--output-dir", str(tmp_path)])
    out = capsys.readouterr()
    assert code == 1
    assert "Stopped: 3,995 tokens used, over the 3,000 budget. Skipped 1 motion." in out.err
    assert "2 of 3 completed, 1 skipped" in out.out and "Stopped" not in out.out


def test_a_bad_file_is_rejected_before_any_debate_with_exit_code_2(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "run_debate", lambda *a, **k: pytest.fail("ran a debate"))
    code = cli.main(["--batch", batch_file(tmp_path, "A\nfine\nB | C | D\n")])
    out = capsys.readouterr()
    assert code == 2 and out.out == ""
    assert out.err.strip() == 'Line 3: a pair uses one "|" (found 2). No debates were run.'


def test_a_missing_or_empty_batch_file_exits_2(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "run_debate", lambda *a, **k: pytest.fail("ran a debate"))
    assert cli.main(["--batch", str(tmp_path / "nope.txt")]) == 2
    assert "Cannot read" in capsys.readouterr().err
    assert cli.main(["--batch", batch_file(tmp_path, "# only a comment\n")]) == 2
    assert "no motions" in capsys.readouterr().err


def test_an_unwritable_summary_exits_2(monkeypatch, capsys, tmp_path):
    from debate_ai import batch as batch_module
    from debate_ai.artifacts import WriteFailed

    def broken(*a, **k):
        raise WriteFailed("disk full")

    monkeypatch.setattr(cli, "run_debate", lambda motion, **k: one())
    monkeypatch.setattr(batch_module, "write_summary_with_retry", broken)
    code = cli.main(["--batch", batch_file(tmp_path, "A\n"), "--output-dir", str(tmp_path)])
    assert code == 2 and "Could not write the batch summary" in capsys.readouterr().err


# ---- argument parsing --------------------------------------------------------

@pytest.mark.parametrize("argv", [
    [],
    ["a motion", "--batch", "f.txt"],
    ["a motion", "--budget", "5000"],
    ["--batch", "f.txt", "--budget", "0"],
    ["--batch", "f.txt", "--budget", "many"],
    ["--budget", "5000"],
])
def test_invalid_argument_combinations_exit_2_with_usage(argv, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2 and "usage:" in capsys.readouterr().err


def test_the_one_word_motion_batch_is_an_ordinary_motion(monkeypatch):
    seen = []

    def fake(motion, **k):
        seen.append(motion)
        return success_result()

    monkeypatch.setattr(cli, "run_debate", fake)
    assert cli.main(["batch"]) == 0
    assert seen == ["batch"]


def test_single_motion_mode_is_unchanged(monkeypatch, capsys):
    seen = {}

    def fake(motion, output_dir):
        seen.update(motion=motion, output_dir=output_dir)
        return success_result()

    monkeypatch.setattr(cli, "run_debate", fake)
    assert cli.main(["Cats are better", "--output-dir", "elsewhere"]) == 0
    out = capsys.readouterr()
    assert seen == {"motion": "Cats are better", "output_dir": "elsewhere"}
    assert "Winner: Against" in out.out and "Batch" not in out.out
