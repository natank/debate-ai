"""Feature 006: the agent and task config lives in the package source, not in the docs."""
from pathlib import Path

import yaml

import debate_ai

PACKAGE = Path(debate_ai.__file__).resolve().parent
CONFIG = PACKAGE / "config"
REPO = PACKAGE.parent.parent


def test_both_config_files_are_inside_the_package():
    assert (CONFIG / "agents.yaml").is_file() and (CONFIG / "tasks.yaml").is_file()


def test_the_config_parses_with_the_expected_top_level_keys():
    agents = yaml.safe_load((CONFIG / "agents.yaml").read_text(encoding="utf-8"))
    tasks = yaml.safe_load((CONFIG / "tasks.yaml").read_text(encoding="utf-8"))
    assert set(agents) == {"debater", "judge"}
    assert set(tasks) == {"propose", "oppose", "decide"}
    assert all(t["agent"] in agents for t in tasks.values())


def test_the_config_is_no_longer_in_the_docs():
    assert not (REPO / "_docs" / "config").exists()


def test_nothing_under_src_refers_to_the_docs_folder():
    offenders = [
        str(p.relative_to(REPO))
        for p in (REPO / "src").rglob("*")
        if p.is_file() and p.suffix in {".py", ".yaml", ".yml", ".toml", ".md"}
        and "_docs" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


def test_the_crew_class_looks_for_its_config_in_the_package_folder():
    from debate_ai.crew import DebateCrew

    assert (Path(DebateCrew.base_directory) / "config").resolve() == CONFIG
