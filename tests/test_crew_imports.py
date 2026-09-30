"""Feature 006, subtask 2: the helpers moved to crew.py, and nothing that imported them broke."""
import subprocess
import sys
from pathlib import Path

import pytest

import debate_ai.crew as crew
import debate_ai.run as run


@pytest.mark.parametrize("code", [
    "import debate_ai.crew; import debate_ai.run",
    "import debate_ai.run; import debate_ai.crew",
    "from debate_ai.crew import StageStats",
    "from debate_ai.run import StageStats, RunResult, run_debate",
    "import debate_ai",
])
def test_imports_work_in_any_order_in_a_fresh_interpreter(code):
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_moved_names_are_the_same_objects_from_either_module():
    for name in ("StageStats", "RunCancelled", "MAX_ATTEMPTS", "_UsageMeter", "_render_verdict", "_render_swapped"):
        assert getattr(run, name) is getattr(crew, name), name


def test_crew_py_does_not_import_run():
    """run imports crew, so crew must never import run back (that would be a cycle)."""
    source = (Path(crew.__file__)).read_text(encoding="utf-8")
    assert "debate_ai.run" not in source and "from debate_ai import run" not in source


def test_the_moved_helpers_still_behave_the_same():
    stats = {}

    class FakeLLM:
        def __init__(self):
            self.total = 0

        def get_token_usage_summary(self):
            class S:
                prompt_tokens, completion_tokens = self.total, 0
                total_tokens = self.total

            return S()

    llm = FakeLLM()
    meter = crew._UsageMeter([llm, llm], stats)  # a shared instance is counted once
    llm.total = 140
    meter.record("propose")
    assert stats["propose"].attempts == 1 and stats["propose"].total_tokens == 140
    llm.total = 200
    meter.record("propose", attempt=False)
    assert stats["propose"].attempts == 1 and stats["propose"].total_tokens == 200
    assert crew.MAX_ATTEMPTS == 3
