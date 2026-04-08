---
title: Codebug DebugEnv
tags:
  - openenv
  - reinforcement-learning
  - debugging
---

# Codebug DebugEnv

Codebug is a production-oriented OpenEnv environment for reinforcement learning on
Python debugging tasks. Agents interact through debugger-style tools, inspect
runtime state, run hidden tests, and submit minimal code fixes that are graded
deterministically.

## What the Environment Exposes

- A single OpenEnv action envelope with 11 tools:
  `set_breakpoint`, `step_over`, `step_into`, `step_out`,
  `inspect_variable`, `set_variable`, `get_stack_trace`, `list_locals`,
  `search_symbol`, `run_tests`, `submit_fix`
- Structured observations containing:
  highlighted source code, current line, locals, stack, breakpoints,
  test logs, runtime error, and patch budget
- A deterministic task curriculum:
  easy off-by-one, medium mutable-default state leak, hard cross-function
  corruption
- Hidden-test grading with patch-size awareness for anti-shotgun-debugging reward

## Local Development

```bash
uv sync
uv run --project . pytest
uv run --project . python -m codebug.server.app --port 8000
```

## Docker Build

```bash
docker build -t codebug-env:latest -f server/Dockerfile .
```

## Hugging Face Spaces Deployment

This repository is designed to be pushed as a Docker Space.

```bash
openenv push
```

The deployment expects:

- `openenv.yaml` at the repository root of the environment
- the FastAPI app served from `server.app:app`
- the root-level `inference.py` script for benchmark evaluation

## Required Environment Variables for Inference

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`
- `LOCAL_IMAGE_NAME`

## Inference Contract

`inference.py` uses the OpenAI client and prints exactly:

- one `[START]` line at episode start
- one `[STEP]` line after each environment step
- one `[END]` line after `env.close()` even if an exception occurs

## Project Layout

```text
codebug/
|-- client.py
|-- models.py
|-- openenv.yaml
|-- pyproject.toml
|-- server/
|   |-- app.py
|   |-- codebug_environment.py
|   |-- engine.py
|   |-- grader.py
|   |-- patch_engine.py
|   `-- tasks.py
`-- inference.py
```
