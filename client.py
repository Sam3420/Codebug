"""Client for the Codebug debugging environment."""

from typing import Any, Dict

try:
    from .compat import EnvClient, State, StepResult
    from .models import CodebugAction, CodebugObservation
except ImportError:
    from compat import EnvClient, State, StepResult
    from models import CodebugAction, CodebugObservation


class CodebugEnv(EnvClient[CodebugAction, CodebugObservation, State]):
    """Persistent client for the Codebug OpenEnv server."""

    def _step_payload(self, action: CodebugAction) -> Dict[str, Any]:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[CodebugObservation]:
        obs_data = payload.get("observation", {})
        observation = CodebugObservation(
            task_id=obs_data.get("task_id", ""),
            difficulty=obs_data.get("difficulty", ""),
            instruction=obs_data.get("instruction", ""),
            code=obs_data.get("code", ""),
            current_line=obs_data.get("current_line", 0),
            locals=obs_data.get("locals", {}),
            stack=obs_data.get("stack", []),
            breakpoints=obs_data.get("breakpoints", []),
            test_output=obs_data.get("test_output", ""),
            error=obs_data.get("error"),
            last_action_error=obs_data.get("last_action_error"),
            available_actions=obs_data.get("available_actions", []),
            patch_budget_lines=obs_data.get("patch_budget_lines", 0),
            metadata=obs_data.get("metadata", {}),
            done=payload.get("done", False),
            reward=payload.get("reward"),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
