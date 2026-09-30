"""Command line entry point: `debate "<motion>"`."""
import argparse
import sys

from dotenv import load_dotenv

from debate_ai.run import run_debate

EXIT = {"success": 0, "exhausted": 1, "failed": 2}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="debate", description="Run a debate on a motion.")
    parser.add_argument("motion", help="the motion to debate, in quotes")
    parser.add_argument("--output-dir", default="output", help="where run folders go")
    args = parser.parse_args(argv)

    load_dotenv()
    result = run_debate(args.motion, output_dir=args.output_dir)

    if result.outcome == "success":
        print(f"Winner: {result.verdict.winner.capitalize()}")
        print(f"Run {result.run_id}:")
    else:
        where = f" at stage '{result.stage}'" if result.stage else ""
        print(f"Run {result.outcome}{where}: {result.reason}", file=sys.stderr)
        if result.artifacts:
            print("Artifacts written before it stopped:", file=sys.stderr)
    for stage, path in result.artifacts.items():
        print(f"  {stage}: {path}", file=sys.stderr if result.outcome != "success" else sys.stdout)
    return EXIT[result.outcome]


if __name__ == "__main__":
    sys.exit(main())
