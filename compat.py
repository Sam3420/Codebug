"""Compatibility helpers for local development without OpenEnv installed."""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    class BaseModel:
        def __init__(self, **kwargs: Any):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self, exclude_none: bool = False) -> dict[str, Any]:
            data = dict(self.__dict__)
            if exclude_none:
                data = {key: value for key, value in data.items() if value is not None}
            return data

    def Field(default: Any = None, **_: Any) -> Any:
        return default

try:
    from openenv.core import EnvClient as OpenEnvClient
    from openenv.core.client_types import StepResult as OpenEnvStepResult
    from openenv.core.env_server.interfaces import Environment as OpenEnvEnvironment
    from openenv.core.env_server.types import (  # type: ignore[attr-defined]
        Action as OpenEnvAction,
        Observation as OpenEnvObservation,
        State as OpenEnvState,
    )

    Action = OpenEnvAction
    Observation = OpenEnvObservation
    State = OpenEnvState
    Environment = OpenEnvEnvironment
    EnvClient = OpenEnvClient
    StepResult = OpenEnvStepResult
except Exception:  # pragma: no cover
    Action = BaseModel

    class Observation(BaseModel):
        done: bool = False
        reward: Optional[float] = None
        metadata: dict[str, Any] = Field(default_factory=dict)

    class State(BaseModel):
        episode_id: Optional[str] = None
        step_count: int = 0

    class Environment:
        SUPPORTS_CONCURRENT_SESSIONS: bool = False

        def reset(self) -> Observation:  # pragma: no cover
            raise NotImplementedError

        def step(self, action: Action) -> Observation:  # pragma: no cover
            raise NotImplementedError

        @property
        def state(self) -> State:  # pragma: no cover
            raise NotImplementedError

    ActionT = TypeVar("ActionT", bound=Action)
    ObservationT = TypeVar("ObservationT", bound=Observation)
    StateT = TypeVar("StateT", bound=State)

    class StepResult(Generic[ObservationT], BaseModel):
        observation: ObservationT
        reward: Optional[float] = None
        done: bool = False

    class EnvClient(Generic[ActionT, ObservationT, StateT]):  # pragma: no cover
        def __init__(self, base_url: Optional[str] = None):
            self.base_url = base_url

        @classmethod
        def from_docker_image(cls, image_name: Optional[str]):
            if image_name is None:
                raise RuntimeError("LOCAL_IMAGE_NAME is required when OpenEnv is unavailable.")
            raise RuntimeError("OpenEnv is not installed in this environment.")

        def close(self) -> None:
            return None
