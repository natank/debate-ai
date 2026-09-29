"""The write_artifact capability (design step 3), called by the control loop.

The path is derived from a fixed stage name and a validated run id, never
from model output. Files are replaced atomically so a retry is safe.
"""
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

STAGES = ("propose", "oppose", "decide")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class InvalidArgument(ValueError):
    """A programming error: bad stage, run id or content."""


class WriteFailed(OSError):
    """The file could not be written."""


@dataclass(frozen=True)
class Artifact:
    path: Path
    bytes: int


def write_artifact(output_dir, run_id: str, stage: str, content: str) -> Artifact:
    if stage not in STAGES:
        raise InvalidArgument(f"unknown stage: {stage!r}")
    if not _RUN_ID.match(run_id or "") or ".." in run_id:
        raise InvalidArgument(f"invalid run id: {run_id!r}")
    if not content or not content.strip():
        raise InvalidArgument("empty content")

    folder = Path(output_dir) / run_id
    target = folder / f"{stage}.md"
    data = content.encode("utf-8")
    tmp_name = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=folder, prefix=f".{stage}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, target)
    except OSError as e:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise WriteFailed(f"could not write {target}: {e}") from e
    return Artifact(path=target, bytes=len(data))


def write_with_retry(*args, attempts: int = 3, backoff: float = 0.2, **kwargs) -> Artifact:
    """Retry WriteFailed only. Never re-calls the model: the content is already valid."""
    for attempt in range(1, attempts + 1):
        try:
            return write_artifact(*args, **kwargs)
        except WriteFailed:
            if attempt == attempts:
                raise
            time.sleep(backoff * attempt)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def render_argument(motion: str, side: str, body: str) -> str:
    title = "Argument in favor" if side == "for" else "Argument against"
    return f"# {title}\n\n**Motion:** {_one_line(motion)}\n**Side:** {side.capitalize()}\n\n{body.strip()}\n"


def render_verdict(motion: str, winner: str, reasoning: str) -> str:
    return (
        f"# Verdict\n\n**Motion:** {_one_line(motion)}\n\n"
        f"**Winner:** {winner.capitalize()}\n\n{reasoning.strip()}\n"
    )
