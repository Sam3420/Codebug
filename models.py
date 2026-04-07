"""Data models for the production Codebug debugging environment."""

from typing import Any, Dict, List, Literal, Optional

try:
    from .compat import Action, Field, Observation
except ImportError:
    from compat import Action, Field, Observation


ToolName = Literal[
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


class CodebugAction(Action):
    """Generic debugger action envelope."""

    tool: ToolName = Field(..., description="Debugger tool to execute.")
    line_no: Optional[int] = Field(
        default=None,
        description="1-based source line number used by set_breakpoint.",
    )
    var_name: Optional[str] = Field(
        default=None,
        description="Variable name used by inspect_variable or set_variable.",
    )
    value: Optional[str] = Field(
        default=None,
        description="Stringified literal for set_variable, parsed with ast.literal_eval.",
    )
    query: Optional[str] = Field(
        default=None,
        description="Search string used by search_symbol.",
    )
    patch: Optional[str] = Field(
        default=None,
        description=(
            "Patch payload for submit_fix. Either full replacement source or a JSON "
            "array of {line_no, content} objects."
        ),
    )


class CodebugObservation(Observation):
    """Structured observation for RL-driven debugging."""

    task_id: str = Field(default="", description="Current benchmark task identifier.")
    difficulty: str = Field(default="", description="Task difficulty tier.")
    instruction: str = Field(default="", description="Task goal shown to the agent.")
    code: str = Field(default="", description="Current source code with pointer markers.")
    current_line: int = Field(default=0, description="Current highlighted source line.")
    locals: Dict[str, str] = Field(
        default_factory=dict,
        description="Locals visible at the current trace frame.",
    )
    stack: List[str] = Field(
        default_factory=list,
        description="Function stack at the current point of execution.",
    )
    breakpoints: List[int] = Field(
        default_factory=list,
        description="Sorted active breakpoints.",
    )
    test_output: str = Field(
        default="",
        description="Logs from the most recent validation run.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Current traceback or runtime error.",
    )
    last_action_error: Optional[str] = Field(
        default=None,
        description="Error from the most recent tool invocation, if any.",
    )
    available_actions: List[str] = Field(
        default_factory=list,
        description="Tools accepted by the environment.",
    )
    patch_budget_lines: int = Field(
        default=0,
        description="Maximum changed lines before penalties grow sharply.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra reproducibility metadata.",
    )
