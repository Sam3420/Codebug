from models import CodebugAction
from server.codebug_environment import CodebugEnvironment


def test_reset_returns_debug_observation():
    env = CodebugEnvironment()
    obs = env.reset()
    assert obs.task_id
    assert obs.available_actions
    assert "01:" in obs.code


def test_submit_fix_finishes_episode():
    env = CodebugEnvironment()
    obs = env.reset()
    assert obs.task_id == "easy_off_by_one"

    patch = """def aggregate_range(n: int) -> int:
    total = 0
    for value in range(1, n + 1):
        total += value
    return total


def render_report(n: int) -> str:
    return f"sum={aggregate_range(n)}"
"""
    result = env.step(CodebugAction(tool="submit_fix", patch=patch))
    assert result.done is True
    assert result.metadata["score"] >= 0.99
