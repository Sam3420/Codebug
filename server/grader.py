"""Deterministic grader for Codebug tasks."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass

from .patch_engine import PatchError, apply_patch
from .tasks import DebugTask


@dataclass(frozen=True)
class GradeResult:
    """Outcome of grading a submitted patch."""

    patched_source: str
    changed_lines: int
    pass_rate: float
    score: float
    passed: bool
    output: str


def run_hidden_tests(task: DebugTask, source: str, timeout: int = 15) -> tuple[float, str]:
    """Execute the task's hidden tests against the supplied source."""

    if _has_pytest():
        return _run_pytest_hidden_tests(task, source, timeout)
    return _run_embedded_hidden_tests(task, source)


def _run_pytest_hidden_tests(task: DebugTask, source: str, timeout: int) -> tuple[float, str]:
    with tempfile.TemporaryDirectory(prefix=f"codebug_{task.task_id}_") as tmpdir:
        target_path = os.path.join(tmpdir, "target.py")
        test_path = os.path.join(tmpdir, "test_hidden.py")

        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write(source)
            if not source.endswith("\n"):
                handle.write("\n")

        with open(test_path, "w", encoding="utf-8") as handle:
            handle.write(task.hidden_test_source)
            if not task.hidden_test_source.endswith("\n"):
                handle.write("\n")

        cmd = [sys.executable, "-m", "pytest", "-q", test_path]
        proc = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        output = (proc.stdout + proc.stderr).strip()
        passed = 0
        failed = 0
        for line in output.splitlines():
            if " passed" in line:
                passed = _extract_count(line, " passed")
            if " failed" in line:
                failed = _extract_count(line, " failed")
        total = passed + failed
        pass_rate = 1.0 if proc.returncode == 0 and total == 0 else (
            passed / total if total else 0.0
        )
        return pass_rate, output


def _run_embedded_hidden_tests(task: DebugTask, source: str) -> tuple[float, str]:
    target_module = types.ModuleType("target")
    exec(compile(source, "target.py", "exec"), target_module.__dict__, target_module.__dict__)
    previous_target = sys.modules.get("target")
    sys.modules["target"] = target_module

    try:
        namespace: dict[str, object] = {}
        exec(compile(task.hidden_test_source, "test_hidden.py", "exec"), namespace, namespace)
        tests = [
            value
            for name, value in namespace.items()
            if name.startswith("test_") and callable(value)
        ]
        if not tests:
            return 0.0, "No hidden tests were discovered."

        passed = 0
        failures: list[str] = []
        for test in tests:
            try:
                test()
                passed += 1
            except Exception as exc:
                failures.append(f"{test.__name__}: {type(exc).__name__}: {exc}")
        total = len(tests)
        pass_rate = passed / total
        output = f"{passed} passed, {total - passed} failed"
        if failures:
            output = output + "\n" + "\n".join(failures)
        return pass_rate, output
    finally:
        if previous_target is None:
            sys.modules.pop("target", None)
        else:
            sys.modules["target"] = previous_target


def grade_submission(task: DebugTask, patch: str) -> GradeResult:
    """Apply a submitted patch and score it with hidden tests and patch penalties."""

    try:
        patched_source, changed_lines = apply_patch(task.source, patch)
    except PatchError as exc:
        return GradeResult(
            patched_source=task.source,
            changed_lines=0,
            pass_rate=0.0,
            score=0.0,
            passed=False,
            output=f"PatchError: {exc}",
        )

    pass_rate, output = run_hidden_tests(task, patched_source)
    efficiency_bonus = max(0.0, 1.0 - (changed_lines / max(task.patch_budget_lines, 1)))
    score = min(1.0, max(0.0, (0.85 * pass_rate) + (0.15 * efficiency_bonus)))
    if pass_rate >= 1.0 and changed_lines <= task.patch_budget_lines:
        score = 1.0
    return GradeResult(
        patched_source=patched_source,
        changed_lines=changed_lines,
        pass_rate=pass_rate,
        score=score,
        passed=pass_rate >= 1.0,
        output=output,
    )


def _extract_count(line: str, suffix: str) -> int:
    prefix = line.split(suffix)[0].strip().split()[-1]
    try:
        return int(prefix)
    except ValueError:
        return 0


def _has_pytest() -> bool:
    try:
        import pytest  # noqa: F401
    except Exception:
        return False
    return True
