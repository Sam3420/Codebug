"""OpenEnv environment implementation for Codebug."""

from __future__ import annotations

from itertools import count
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

try:
    from ..compat import Environment, State
    from ..models import CodebugAction, CodebugObservation
    from .engine import VirtualDebuggerEngine
    from .grader import grade_submission, run_hidden_tests
    from .tasks import DebugTask, get_task, get_task_by_id
except ImportError:
    from compat import Environment, State
    from models import CodebugAction, CodebugObservation
    from server.engine import VirtualDebuggerEngine
    from server.grader import grade_submission, run_hidden_tests
    from server.tasks import DebugTask, get_task, get_task_by_id


ALL_TOOLS: List[str] = [
    "set_breakpoint",
    "step_over",
    "step_into",
    "step_out",
    "inspect_variable",
    "set_variable",
    "get_stack_trace",
    "list_locals",
    "search_symbol",
    "run_tests",
    "submit_fix",
]


class CodebugEnvironment(Environment):
    """A deterministic Python debugging environment for reinforcement learning."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = False
    _task_counter = count()
    _task_counter_lock = Lock()

    def __init__(self) -> None:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task_index = -1
        self._task: Optional[DebugTask] = None
        self._engine = VirtualDebuggerEngine()
        self._current_source = ""
        self._last_test_output = ""
        self._last_action_error: Optional[str] = None
        self._last_reward = 0.0
        self._done = False
        self._episode_score = 0.0

    def reset(self, task_id: Optional[str] = None) -> CodebugObservation:
        if task_id:
            self._task = get_task_by_id(task_id)
        else:
            with self._task_counter_lock:
                self._task_index = next(self._task_counter)
            self._task = get_task(self._task_index)
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._current_source = self._task.source
        self._last_test_output = ""
        self._last_action_error = None
        self._last_reward = 0.0
        self._done = False
        self._episode_score = 0.0
        self._engine = VirtualDebuggerEngine()
        self._engine.load(self._task.source, self._task.entrypoint_call)
        return self._build_observation()

    def step(self, action: CodebugAction) -> CodebugObservation:  # type: ignore[override]
        self._state.step_count += 1
        self._last_action_error = None

        if self._done:
            self._last_action_error = "Episode already finished. Call reset() to start again."
            self._last_reward = -0.2
            return self._build_observation()

        reward = -0.02

        try:
            tool = action.tool
            if tool == "set_breakpoint":
                reward += self._handle_set_breakpoint(action)
            elif tool == "step_over":
                reward += self._handle_move(self._engine.step_over())
            elif tool == "step_into":
                reward += self._handle_move(self._engine.step_into())
            elif tool == "step_out":
                reward += self._handle_move(self._engine.step_out())
            elif tool == "inspect_variable":
                reward += self._handle_inspect_variable(action)
            elif tool == "set_variable":
                reward += self._handle_set_variable(action)
            elif tool == "get_stack_trace":
                reward += 0.02
            elif tool == "list_locals":
                reward += 0.02
            elif tool == "search_symbol":
                reward += self._handle_search_symbol(action)
            elif tool == "run_tests":
                reward += self._handle_run_tests()
            elif tool == "submit_fix":
                reward += self._handle_submit_fix(action)
            else:
                self._last_action_error = f"Unsupported tool: {tool}"
                reward -= 0.1
        except Exception as exc:  # pragma: no cover
            self._last_action_error = f"{type(exc).__name__}: {exc}"
            reward -= 0.15

        self._last_reward = reward
        observation = self._build_observation()
        observation.reward = reward
        observation.done = self._done
        return observation

    @property
    def state(self) -> State:
        return self._state

    def _handle_set_breakpoint(self, action: CodebugAction) -> float:
        if action.line_no is None:
            self._last_action_error = "set_breakpoint requires line_no."
            return -0.1
        matched = self._engine.set_breakpoint(action.line_no)
        if not matched:
            self._last_action_error = f"No executable trace event was found for line {action.line_no}."
            return -0.08
        assert self._task is not None
        near_bug = any(abs(action.line_no - bug_line) <= 2 for bug_line in self._task.expected_bug_lines)
        return 0.08 if near_bug else 0.03

    def _handle_move(self, moved: bool) -> float:
        if not moved:
            self._last_action_error = "No further execution steps are available."
            return -0.05
        return 0.01

    def _handle_inspect_variable(self, action: CodebugAction) -> float:
        if not action.var_name:
            self._last_action_error = "inspect_variable requires var_name."
            return -0.1
        value = self._engine.inspect_variable(action.var_name)
        if value is None:
            self._last_action_error = f"Variable '{action.var_name}' is not in scope."
            return -0.08
        current_event = self._engine.current_event
        interesting = action.var_name in current_event.locals_snapshot
        return 0.05 if interesting else 0.02

    def _handle_set_variable(self, action: CodebugAction) -> float:
        if not action.var_name or action.value is None:
            self._last_action_error = "set_variable requires var_name and value."
            return -0.1
        self._engine.set_variable(action.var_name, action.value)
        return 0.03

    def _handle_search_symbol(self, action: CodebugAction) -> float:
        if not action.query:
            self._last_action_error = "search_symbol requires query."
            return -0.1
        matches = self._engine.search_symbol(self._current_source, action.query)
        if not matches:
            self._last_action_error = f"No occurrences found for '{action.query}'."
            return -0.05
        return 0.03

    def _handle_run_tests(self) -> float:
        assert self._task is not None
        pass_rate, output = run_hidden_tests(self._task, self._current_source)
        self._last_test_output = output
        return (0.2 * pass_rate) - 0.02

    def _handle_submit_fix(self, action: CodebugAction) -> float:
        if not action.patch:
            self._last_action_error = "submit_fix requires patch."
            return -0.2

        assert self._task is not None
        grade = grade_submission(self._task, action.patch)
        self._current_source = grade.patched_source
        self._last_test_output = grade.output
        self._episode_score = grade.score
        self._done = True
        self._engine.load(self._current_source, self._task.entrypoint_call)
        if not grade.passed:
            self._last_action_error = "Submitted patch did not fully pass hidden tests."
        minimal_bonus = 0.15 if grade.changed_lines <= self._task.patch_budget_lines else 0.0
        return (0.8 * grade.score) + minimal_bonus

    def _build_observation(self) -> CodebugObservation:
        task = self._task
        if task is None:
            return CodebugObservation(
                instruction="Environment not initialized.",
                available_actions=ALL_TOOLS,
                done=self._done,
                reward=self._last_reward,
            )

        current_event = self._engine.current_event
        code = _render_code(self._current_source, current_event.line_no, self._engine.breakpoints)
        metadata: Dict[str, object] = {
            "episode_id": self._state.episode_id,
            "step_count": self._state.step_count,
            "current_function": current_event.function_name,
            "trace_length": len(self._engine.events),
            "score": round(self._episode_score, 4),
        }
        return CodebugObservation(
            task_id=task.task_id,
            difficulty=task.difficulty,
            instruction=task.instruction,
            code=code,
            current_line=current_event.line_no,
            locals=self._engine.list_locals(),
            stack=current_event.stack,
            breakpoints=sorted(self._engine.breakpoints),
            test_output=self._last_test_output,
            error=self._engine.error,
            last_action_error=self._last_action_error,
            available_actions=ALL_TOOLS,
            patch_budget_lines=task.patch_budget_lines,
            metadata=metadata,
            reward=self._last_reward,
            done=self._done,
        )


def _render_code(source: str, current_line: int, breakpoints: set[int]) -> str:
    rendered: List[str] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        marker = ">>" if line_no == current_line else "  "
        bp = "*" if line_no in breakpoints else " "
        rendered.append(f"{marker}{bp} {line_no:02d}: {line}")
    return "\n".join(rendered)
