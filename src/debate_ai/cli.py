"""Command line entry point.

    debate "<motion>"                 one debate
    debate --batch FILE [--budget N]  many debates and a summary (feature 001)
"""
import argparse
import sys

from dotenv import load_dotenv

from debate_ai.artifacts import STAGES, WriteFailed
from debate_ai.batch import DEFAULT_BUDGET, BatchInputError, BatchResult, read_motions_file, run_batch
from debate_ai.run import RunResult, StageStats, run_debate

EXIT = {"success": 0, "exhausted": 1, "failed": 2}
LINE_WIDTH = 80


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


def format_progress_line(i: int, n: int, motion: str, result: RunResult, width: int = LINE_WIDTH) -> str:
    """`[i/N] <motion> ..... <winner or outcome>  <tokens> tokens`, at most `width` wide.
    A long motion is shortened with `...`; the full motion is in the summary."""
    if result.outcome == "success":
        label = result.verdict.winner.capitalize()
    else:
        label = f"{result.outcome} ({result.stage})" if result.stage else result.outcome
    right = f"{label:<8} {result.total.total_tokens:,} tokens"
    left = f"[{i}/{n}] {' '.join(motion.split())}"
    room = width - len(right) - 5  # a space, at least three dots, a space
    if len(left) > room:
        left = left[: max(room - 3, 0)].rstrip() + "..."
    dots = "." * max(width - len(left) - len(right) - 2, 3)
    return f"{left} {dots} {right}"


def format_batch_summary_line(result: BatchResult) -> str:
    """`Batch <id>: 2 of 3 completed, 1 exhausted, 8 attempts, 5,470 tokens`."""
    ran = [r for r in result.results if r is not None]
    parts = [f"{result.completed} of {len(result.entries)} completed"]
    for outcome in ("exhausted", "failed"):
        count = sum(1 for r in ran if r.outcome == outcome)
        if count:
            parts.append(f"{count} {outcome}")
    if result.skipped:
        parts.append(f"{result.skipped} skipped")
    attempts = sum(r.total.attempts for r in ran)
    tokens = sum(r.total.total_tokens for r in ran)
    parts += [f"{attempts} attempts", f"{tokens:,} tokens"]
    return f"Batch {result.batch_id}: " + ", ".join(parts)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debate",
        description='Run a debate on a motion, or a batch of motions with --batch.',
        usage='debate "<motion>" [--output-dir DIR]\n'
        "       debate --batch FILE [--budget TOKENS] [--output-dir DIR]",
    )
    parser.add_argument("motion", nargs="?", help="the motion to debate, in quotes")
    parser.add_argument("--batch", metavar="FILE", help="run every motion in FILE and write a summary")
    parser.add_argument(
        "--budget", type=int, default=None, metavar="TOKENS",
        help=f"with --batch: stop once this many tokens are spent (default {DEFAULT_BUDGET:,})",
    )
    parser.add_argument("--output-dir", default="output", help="where run folders go")
    return parser


def _run_single(motion: str, output_dir: str) -> int:
    result = run_debate(motion, output_dir=output_dir)

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


def _run_batch(path: str, budget: int, output_dir: str) -> int:
    try:
        entries = read_motions_file(path)
    except BatchInputError as e:
        print(f"{e} No debates were run.", file=sys.stderr)
        return 2

    def progress(i, n, entry, result):
        print(format_progress_line(i, n, entry.motion, result), flush=True)

    try:
        result = run_batch(
            entries, output_dir=output_dir, budget=budget, run=run_debate, on_progress=progress
        )
    except WriteFailed as e:
        print(f"Could not write the batch summary: {e}", file=sys.stderr)
        return 2

    if result.stopped:
        print(f"Stopped: {result.stopped}", file=sys.stderr)
    print()
    print(format_batch_summary_line(result))
    print(f"Summary: {result.summary_path}")
    return result.exit_code


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.batch is not None and args.motion is not None:
        parser.error("give either a motion or --batch FILE, not both")
    if args.batch is None and args.motion is None:
        parser.error("give a motion, or --batch FILE")
    if args.batch is None and args.budget is not None:
        parser.error("--budget only applies with --batch")
    if args.budget is not None and args.budget < 1:
        parser.error("--budget must be at least 1")

    load_dotenv()
    if args.batch is not None:
        return _run_batch(args.batch, args.budget or DEFAULT_BUDGET, args.output_dir)
    return _run_single(args.motion, args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
