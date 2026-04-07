"""Replayable debugger runtime for Codebug tasks."""

from __future__ import annotations

import ast
import linecache
import sys
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except Exception:
        return "<unrepresentable>"


@dataclass
class TraceEvent:
    """A single debugger-visible event produced by executing a task."""

    line_no: int
    function_name: str
    stack: List[str]
    locals_snapshot: Dict[str, str]
    depth: int


class VirtualDebuggerEngine:
    """Collect execution traces and expose debugger-like navigation."""

    def __init__(self) -> None:
        self.breakpoints: set[int] = set()
        self.events: List[TraceEvent] = []
        self.pointer: int = 0
        self.error: Optional[str] = None
        self.override_values: Dict[str, str] = {}
        self._filename = "<codebug-task>"

    def load(self, source: str, entrypoint_call: str) -> None:
        """Execute source once under tracing and store the resulting trace."""

        self.events = []
        self.pointer = 0
        self.error = None
        namespace: Dict[str, object] = {}

        linecache.cache[self._filename] = (
            len(source),
            None,
            [line + "\n" for line in source.splitlines()],
            self._filename,
        )

        def tracer(frame, event, arg):  # type: ignore[no-untyped-def]
            if frame.f_code.co_filename != self._filename:
                return tracer
            if event == "line":
                stack = self._stack_names(frame)
                locals_snapshot = {k: _safe_repr(v) for k, v in frame.f_locals.items()}
                self.events.append(
                    TraceEvent(
                        line_no=frame.f_lineno,
                        function_name=frame.f_code.co_name,
                        stack=stack,
                        locals_snapshot=locals_snapshot,
                        depth=max(len(stack) - 1, 0),
                    )
                )
            if event == "exception" and arg is not None:
                exc_type, exc_value, exc_tb = arg
                self.error = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            return tracer

        compiled = compile(source, self._filename, "exec")
        previous_trace = sys.gettrace()
        try:
            sys.settrace(tracer)
            exec(compiled, namespace, namespace)
            eval(entrypoint_call, namespace, namespace)
        except Exception:
            if self.error is None:
                self.error = traceback.format_exc()
        finally:
            sys.settrace(previous_trace)

        if not self.events:
            self.events.append(
                TraceEvent(
                    line_no=1,
                    function_name="<module>",
                    stack=["<module>"],
                    locals_snapshot={},
                    depth=0,
                )
            )

    def set_breakpoint(self, line_no: int) -> bool:
        self.breakpoints.add(line_no)
        for index, event in enumerate(self.events):
            if event.line_no == line_no:
                self.pointer = index
                return True
        return False

    def step_over(self) -> bool:
        if self.pointer + 1 >= len(self.events):
            return False
        self.pointer += 1
        return True

    def step_into(self) -> bool:
        current = self.current_event
        for index in range(self.pointer + 1, len(self.events)):
            if self.events[index].depth > current.depth:
                self.pointer = index
                return True
        return self.step_over()

    def step_out(self) -> bool:
        current = self.current_event
        for index in range(self.pointer + 1, len(self.events)):
            if self.events[index].depth < current.depth:
                self.pointer = index
                return True
        return False

    def list_locals(self) -> Dict[str, str]:
        data = dict(self.current_event.locals_snapshot)
        data.update(self.override_values)
        return data

    def inspect_variable(self, name: str) -> Optional[str]:
        locals_snapshot = self.list_locals()
        return locals_snapshot.get(name)

    def set_variable(self, name: str, value: str) -> str:
        try:
            parsed = ast.literal_eval(value)
            rendered = _safe_repr(parsed)
        except Exception:
            rendered = value
        self.override_values[name] = rendered
        return rendered

    def search_symbol(self, source: str, query: str) -> List[Dict[str, str | int]]:
        matches: List[Dict[str, str | int]] = []
        for line_no, line in enumerate(source.splitlines(), start=1):
            if query in line:
                matches.append({"line_no": line_no, "content": line.rstrip()})
        return matches

    @property
    def current_event(self) -> TraceEvent:
        index = min(max(self.pointer, 0), len(self.events) - 1)
        return self.events[index]

    @staticmethod
    def _stack_names(frame) -> List[str]:  # type: ignore[no-untyped-def]
        stack: List[str] = []
        cursor = frame
        while cursor is not None and cursor.f_code.co_filename == "<codebug-task>":
            stack.append(cursor.f_code.co_name)
            cursor = cursor.f_back
        if not stack:
            stack.append("<module>")
        return list(reversed(stack))
