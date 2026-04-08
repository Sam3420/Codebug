# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Codebug Environment.

This module creates an HTTP server that exposes the CodebugEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import CodebugAction, CodebugObservation
    from .codebug_environment import CodebugEnvironment
    from .tasks import TASKS, task_catalog
    from ..graders import GRADER_SPECS
except ImportError:
    from models import CodebugAction, CodebugObservation
    from server.codebug_environment import CodebugEnvironment
    from server.tasks import TASKS, task_catalog
    from graders import GRADER_SPECS


# Create the app with web interface and README integration
app = create_app(
    CodebugEnvironment,
    CodebugAction,
    CodebugObservation,
    env_name="codebug",
    max_concurrent_envs=1,
)

app.router.routes = [
    route for route in app.router.routes if getattr(route, "path", None) != "/metadata"
]


@app.get("/metadata", tags=["Environment Info"])
async def metadata() -> dict:
    return {
        "name": "codebug",
        "description": "High-fidelity Python debugging benchmark for OpenEnv.",
        "version": "1.0.0",
        "task_count": len(TASKS),
        "grader_count": len(GRADER_SPECS),
        "tasks": task_catalog(),
        "graders": GRADER_SPECS,
        "grader": {
            "type": "hidden_pytest",
            "scoring_range": [0.0, 1.0],
            "terminal_tool": "submit_fix",
            "enabled": True,
        },
    }


@app.get("/tasks", tags=["Environment Info"])
async def tasks() -> dict:
    return {
        "task_count": len(TASKS),
        "tasks": task_catalog(),
    }


@app.get("/graders", tags=["Environment Info"])
async def graders() -> dict:
    return {
        "grader_count": len(GRADER_SPECS),
        "graders": GRADER_SPECS,
    }


def main() -> None:
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m codebug.server.app

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn codebug.server.app:app --workers 4
    """
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
