"""Public grader registry for external validators and benchmark tooling."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

try:
    from .server.grader import grade_submission
    from .server.tasks import TASKS as _SERVER_TASKS
    from .server.tasks import get_task_by_id
except ImportError:
    from server.grader import grade_submission
    from server.tasks import TASKS as _SERVER_TASKS
    from server.tasks import get_task_by_id


def grade_task(task_id: str, patch: str) -> Dict[str, Any]:
    """Grade a patch submission for a specific task id."""

    result = grade_submission(get_task_by_id(task_id), patch)
    return {
        "task_id": task_id,
        "score": result.score,
        "pass_rate": result.pass_rate,
        "passed": result.passed,
        "changed_lines": result.changed_lines,
        "output": result.output,
    }


def _build_grader(task_id: str) -> Callable[[str], Dict[str, Any]]:
    def _grader(patch: str) -> Dict[str, Any]:
        return grade_task(task_id, patch)

    _grader.__name__ = get_task_by_id(task_id).grader_id
    return _grader


GRADERS: Dict[str, Callable[[str], Dict[str, Any]]] = {
    task.task_id: _build_grader(task.task_id) for task in _SERVER_TASKS
}

GRADER_SPECS: List[Dict[str, Any]] = [
    {
        "task_id": task.task_id,
        "grader_id": task.grader_id,
        "type": "hidden_pytest",
        "scoring_range": [0.0, 1.0],
        "enabled": True,
        "pass_metric": "pass_rate",
        "terminal_tool": "submit_fix",
    }
    for task in _SERVER_TASKS
]

__all__ = [
    "GRADERS",
    "GRADER_SPECS",
    "grade_task",
]
