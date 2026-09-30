"""Feature 006, subtask 3: the crew is a @CrewBase class, and it is wired as the design says."""
import inspect
import threading
from pathlib import Path

import pytest
import yaml

import debate_ai
from debate_ai.crew import DebateCrew
from debate_ai.run import run_debate
from tests.fakes import make_llm

PACKAGE = Path(debate_ai.__file__).resolve().parent
CONFIG = PACKAGE / "config"


def build(check_order=False, factory=None, **kw):
    return DebateCrew(
        motion="Cats are better",
        llm_factory=factory or (lambda _model: make_llm()),
        saver=lambda stage, render: (lambda out: None),
        cancelled=threading.Event(),
        stats={},
        check_order=check_order,
        **kw,
    )


# ---- structure ------------------------------------------------------------------------

def test_the_crew_is_a_crewbase_class():
    assert DebateCrew.is_crew_class is True


def test_every_agent_named_in_the_yaml_has_an_agent_method():
    """CrewBase fails at start-up if tasks.yaml names an agent with no @agent method."""
    tasks = yaml.safe_load((CONFIG / "tasks.yaml").read_text(encoding="utf-8"))
    agents = yaml.safe_load((CONFIG / "agents.yaml").read_text(encoding="utf-8"))
    assert {t["agent"] for t in tasks.values()} <= set(agents)
    for name in agents:
        assert getattr(getattr(DebateCrew, name), "is_agent", False), f"no @agent method for {name}"


def test_every_task_named_in_the_yaml_has_a_task_method():
    tasks = yaml.safe_load((CONFIG / "tasks.yaml").read_text(encoding="utf-8"))
    for name in tasks:
        assert getattr(getattr(DebateCrew, name), "is_task", False), f"no @task method for {name}"


@pytest.mark.parametrize("check_order,count", [(False, 3), (True, 4)])
def test_the_crew_has_three_tasks_or_four_with_the_order_check(check_order, count):
    dc = build(check_order)
    crew = dc.crew()
    assert len(crew.tasks) == count and len(crew.agents) == 2
    assert list(dc.stage_tasks()) == ["propose", "oppose", "decide", "decide_swapped"][:count]


# ---- the isolation wiring the design depends on -----------------------------------------

def test_the_debaters_are_blind_and_the_judges_read_the_arguments_in_opposite_orders():
    t = build(check_order=True).stage_tasks()
    ids = lambda task: [id(c) for c in task.context]  # noqa: E731
    assert t["propose"].context == [] and t["oppose"].context == []
    assert ids(t["decide"]) == [id(t["propose"]), id(t["oppose"])]
    assert ids(t["decide_swapped"]) == [id(t["oppose"]), id(t["propose"])]
    # Neither judge is given the other judge's output.
    assert id(t["decide"]) not in ids(t["decide_swapped"]) and id(t["decide_swapped"]) not in ids(t["decide"])


def test_propose_and_oppose_share_one_debater_and_the_judges_share_one_judge():
    t = build(check_order=True).stage_tasks()
    assert t["propose"].agent is t["oppose"].agent
    assert t["decide"].agent is t["decide_swapped"].agent
    assert t["propose"].agent is not t["decide"].agent


def test_each_stage_task_is_the_one_in_the_crew():
    dc = build(check_order=True)
    crew_tasks, named = dc.crew().tasks, dc.stage_tasks()
    assert [id(x) for x in crew_tasks] == [id(x) for x in named.values()]


def test_every_task_gets_three_attempts_and_a_guardrail():
    for task in build(check_order=True).stage_tasks().values():
        assert task.guardrail_max_retries == 2 and task.guardrail is not None


# ---- per-run state ----------------------------------------------------------------------

def test_two_crews_built_in_a_row_share_no_agents_tasks_or_config():
    a, b = build(True), build(True)
    assert a.debater() is not b.debater() and a.judge() is not b.judge()
    assert a.agents_config is not b.agents_config and a.tasks_config is not b.tasks_config
    assert a.crew() is not b.crew()


def test_the_model_comes_from_the_factory_and_the_yaml_llm_string_is_left_alone(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # no real client may be built
    made = []

    def factory(model):
        made.append(model)
        return make_llm()

    dc = build(factory=factory)
    assert dc.agents_config["debater"]["llm"] == "openai/gpt-5.4-mini"
    assert made and set(made) == {"openai/gpt-5.4-mini"}
    assert dc.debater().llm is dc._llms["debater"] and dc.judge().llm is dc._llms["judge"]


# ---- where the config is found ----------------------------------------------------------

def test_the_default_lookup_finds_the_package_config_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dc = build()
    assert Path(dc.base_directory).resolve() == PACKAGE
    assert set(dc.agents_config) == {"debater", "judge"}
    assert set(dc.tasks_config) == {"propose", "oppose", "decide"}


def test_a_config_folder_can_be_given_and_replaces_the_default(tmp_path):
    for name in ("agents.yaml", "tasks.yaml"):
        text = (CONFIG / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text.replace("A compelling debater", "OVERRIDE ROLE"), encoding="utf-8")
    assert "OVERRIDE ROLE" in build(config_dir=tmp_path).debater().role
    assert "OVERRIDE ROLE" not in build().debater().role


# ---- run_debate keeps its shape ----------------------------------------------------------

def test_run_debate_keeps_its_parameter_names_and_kinds():
    params = inspect.signature(run_debate).parameters
    assert list(params) == ["motion", "output_dir", "llm_factory", "config_dir", "time_limit",
                            "write_backoff", "now", "check_order"]
    assert params["motion"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(params[n].kind is inspect.Parameter.KEYWORD_ONLY for n in list(params)[1:])
    assert params["config_dir"].default is None and params["check_order"].default is False
    assert params["output_dir"].default == "output"
