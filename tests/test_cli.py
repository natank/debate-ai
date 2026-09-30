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
