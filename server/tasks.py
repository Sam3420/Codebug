"""Task catalog for the Codebug debugging benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DebugTask:
    """Immutable task bundle used by the environment and grader."""

    task_id: str
    difficulty: str
    instruction: str
    source: str
    entrypoint_call: str
    hidden_test_source: str
    expected_bug_lines: List[int]
    patch_budget_lines: int


TASKS: List[DebugTask] = [
    DebugTask(
        task_id="easy_off_by_one",
        difficulty="easy",
        instruction=(
            "Fix the logic bug so aggregate_range returns the inclusive sum from 1 to n."
        ),
        source="""def aggregate_range(n: int) -> int:
    total = 0
    for value in range(1, n):
        total += value
    return total


def render_report(n: int) -> str:
    return f"sum={aggregate_range(n)}"
""",
        entrypoint_call="render_report(5)",
        hidden_test_source="""from target import aggregate_range, render_report


def test_aggregate_range_small():
    assert aggregate_range(1) == 1
    assert aggregate_range(5) == 15


def test_render_report():
    assert render_report(4) == "sum=10"
""",
        expected_bug_lines=[3],
        patch_budget_lines=2,
    ),
    DebugTask(
        task_id="medium_mutable_default",
        difficulty="medium",
        instruction=(
            "Fix the state-leak bug so collect_tags does not reuse data across calls."
        ),
        source="""from typing import List, Optional


def collect_tags(tag: str, bucket: List[str] = []) -> List[str]:
    bucket.append(tag)
    return bucket


def build_ticket(title: str, tag: Optional[str] = None) -> dict:
    tags = collect_tags(tag or "general")
    return {"title": title, "tags": tags}
""",
        entrypoint_call="(build_ticket('first', 'bug'), build_ticket('second', 'ops'))",
        hidden_test_source="""from target import build_ticket, collect_tags


def test_collect_tags_isolated():
    assert collect_tags("bug") == ["bug"]
    assert collect_tags("ops") == ["ops"]


def test_build_ticket_isolated():
    first = build_ticket("first", "bug")
    second = build_ticket("second", "ops")
    assert first["tags"] == ["bug"]
    assert second["tags"] == ["ops"]
""",
        expected_bug_lines=[4],
        patch_budget_lines=4,
    ),
    DebugTask(
        task_id="hard_cross_function_corruption",
        difficulty="hard",
        instruction=(
            "Fix the source of the corrupted user record so build_profile returns the "
            "primary email address without crashing."
        ),
        source="""def normalize_user(payload: dict) -> dict:
    return {
        "name": payload["name"].strip().title(),
        "contact": {"mail": payload["email"].strip().lower()},
    }


def enrich_user(user: dict) -> dict:
    user["contact"]["primary"] = user["contact"]["email"]
    return user


def build_profile(payload: dict) -> str:
    normalized = normalize_user(payload)
    enriched = enrich_user(normalized)
    return f"{enriched['name']} <{enriched['contact']['primary']}>"
""",
        entrypoint_call="build_profile({'name': '  ada lovelace ', 'email': ' ADA@EXAMPLE.COM '})",
        hidden_test_source="""from target import build_profile, enrich_user, normalize_user


def test_normalize_user_schema():
    user = normalize_user({"name": " Ada ", "email": " ADA@EXAMPLE.COM "})
    assert user["contact"]["email"] == "ada@example.com"


def test_build_profile():
    profile = build_profile({"name": " Ada ", "email": " ADA@EXAMPLE.COM "})
    assert profile == "Ada <ada@example.com>"


def test_enrich_user():
    user = {"name": "Ada", "contact": {"email": "ada@example.com"}}
    enriched = enrich_user(user)
    assert enriched["contact"]["primary"] == "ada@example.com"
""",
        expected_bug_lines=[4, 9],
        patch_budget_lines=4,
    ),
]


def get_task(index: int) -> DebugTask:
    """Return a task using deterministic round-robin selection."""

    return TASKS[index % len(TASKS)]
