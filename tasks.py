"""Public task registry for external validators and benchmark tooling."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from .server.tasks import TASKS as _SERVER_TASKS
    from .server.tasks import TASK_BY_ID, get_task, get_task_by_id, task_catalog
except ImportError:
    from server.tasks import TASKS as _SERVER_TASKS
    from server.tasks import TASK_BY_ID, get_task, get_task_by_id, task_catalog


TASK_IDS: List[str] = [task.task_id for task in _SERVER_TASKS]

TASKS: List[Dict[str, Any]] = task_catalog()

__all__ = [
    "TASK_IDS",
    "TASKS",
    "TASK_BY_ID",
    "get_task",
    "get_task_by_id",
    "task_catalog",
]
