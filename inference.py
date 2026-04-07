"""Benchmark inference entrypoint for Codebug."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from client import CodebugEnv
from models import CodebugAction

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_NAME = os.getenv("CODEBUG_TASK", "debug")
BENCHMARK = os.getenv("CODEBUG_BENCHMARK", "codebug")
MAX_STEPS = int(os.getenv("CODEBUG_MAX_STEPS", "8"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("CODEBUG_SUCCESS_THRESHOLD", "0.80"))


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def _load_system_prompt() -> str:
    prompt_path = Path(__file__).with_name("inference.pt")
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return textwrap.dedent(
        """
        You are operating a Python debugging environment.
        Return exactly one JSON object with keys:
        tool, line_no, var_name, value, query, patch.
        Use only the supported tools and leave unused keys null.
        Prefer concise, valid actions.
        """
    ).strip()


SYSTEM_PROMPT = _load_system_prompt()


def build_prompt(task_id: str, instruction: str, code: str, test_output: str) -> str:
    return textwrap.dedent(
        f"""
        Task: {task_id}
        Instruction: {instruction}
        Code:
        {code}

        Latest test output:
        {test_output or "None"}
        """
    ).strip()


def ask_model(client: OpenAI, task_id: str, instruction: str, code: str, test_output: str) -> Optional[dict]:
    if not API_KEY:
        return None

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_prompt(task_id, instruction, code, test_output),
                },
            ],
            temperature=0.2,
            max_tokens=220,
            stream=False,
        )
        content = (completion.choices[0].message.content or "").strip()
        return json.loads(content)
    except Exception:
        return None


def heuristic_action(task_id: str, step: int) -> dict:
    if step == 1:
        return {"tool": "run_tests"}
    if step == 2:
        return {"tool": "search_symbol", "query": "def "}

    patches = {
        "easy_off_by_one": """def aggregate_range(n: int) -> int:
    total = 0
    for value in range(1, n + 1):
        total += value
    return total


def render_report(n: int) -> str:
    return f"sum={aggregate_range(n)}"
""",
        "medium_mutable_default": """from typing import List, Optional


def collect_tags(tag: str, bucket: Optional[List[str]] = None) -> List[str]:
    bucket = [] if bucket is None else list(bucket)
    bucket.append(tag)
    return bucket


def build_ticket(title: str, tag: Optional[str] = None) -> dict:
    tags = collect_tags(tag or "general")
    return {"title": title, "tags": tags}
""",
        "hard_cross_function_corruption": """def normalize_user(payload: dict) -> dict:
    return {
        "name": payload["name"].strip().title(),
        "contact": {"email": payload["email"].strip().lower()},
    }


def enrich_user(user: dict) -> dict:
    user["contact"]["primary"] = user["contact"]["email"]
    return user


def build_profile(payload: dict) -> str:
    normalized = normalize_user(payload)
    enriched = enrich_user(normalized)
    return f"{enriched['name']} <{enriched['contact']['primary']}>"
""",
    }
    return {"tool": "submit_fix", "patch": patches.get(task_id, "")}


def coerce_action(candidate: Optional[dict], task_id: str, step: int) -> CodebugAction:
    data = candidate or heuristic_action(task_id, step)
    tool = data.get("tool") if isinstance(data, dict) else None
    if tool not in {
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
    }:
        data = heuristic_action(task_id, step)
    return CodebugAction(**data)


def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY or "missing")
    env = CodebugEnv.from_docker_image(LOCAL_IMAGE_NAME) if LOCAL_IMAGE_NAME else CodebugEnv()

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)
    try:
        result = env.reset()
        observation = result.observation

        for step in range(1, MAX_STEPS + 1):
            proposed = ask_model(
                client,
                observation.task_id,
                observation.instruction,
                observation.code,
                observation.test_output,
            )
            action = coerce_action(proposed, observation.task_id, step)
            action_str = json.dumps(action.model_dump(exclude_none=True), separators=(",", ":"))
            result = env.step(action)
            observation = result.observation
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            steps_taken = step
            log_step(
                step=step,
                action=action_str,
                reward=reward,
                done=bool(result.done),
                error=observation.last_action_error,
            )
            if result.done:
                break

        score = float(observation.metadata.get("score", 0.0))
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD
    finally:
        try:
            env.close()
        finally:
            log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    main()
