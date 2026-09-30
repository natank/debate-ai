"""Command line entry point: `debate "<motion>"`."""
import argparse
import sys

from dotenv import load_dotenv

from debate_ai.artifacts import STAGES
from debate_ai.run import RunResult, StageStats, run_debate

EXIT = {"success": 0, "exhausted": 1, "failed": 2}


def _line(label: str, s: StageStats, path=None) -> str:
    attempts = f"{s.attempts} attempt{'s' if s.attempts != 1 else ''}"
    tokens = (
        f"{s.total_tokens:,} tokens ({s.prompt_tokens:,} prompt + {s.completion_tokens:,} completion)"
    )
    return f"  {label:<8} {attempts:<12} {tokens}" + (f"  {path}" if path else "")


def format_report(result: RunResult) -> list[str]:
    """Per-stage attempts, tokens and artifact path, then a total."""
    lines = []
    for stage in STAGES:
        if stage in result.stats or stage in result.artifacts:
            lines.append(_line(stage, result.stats.get(stage, StageStats()), result.artifacts.get(stage)))
    if result.stats:
        lines.append(_line("total", result.total))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="debate", description="Run a debate on a motion.")
    parser.add_argument("motion", help="the motion to debate, in quotes")
    parser.add_argument("--output-dir", default="output", help="where run folders go")
    args = parser.parse_args(argv)

    load_dotenv()
    result = run_debate(args.motion, output_dir=args.output_dir)

    ok = result.outcome == "success"
    out = sys.stdout if ok else sys.stderr
    if ok:
        print(f"Winner: {result.verdict.winner.capitalize()}")
        print(f"Run {result.run_id}:")
    else:
        where = f" at stage '{result.stage}'" if result.stage else ""
        print(f"Run {result.outcome}{where}: {result.reason}", file=out)
    for line in format_report(result):
        print(line, file=out)
    return EXIT[result.outcome]


if __name__ == "__main__":
    sys.exit(main())
