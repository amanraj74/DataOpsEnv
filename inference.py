"""
Inference Script for DataOpsEnv
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after episode ends, always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw error string, or null if none.
    - Each task should return score in [0, 1]
"""

import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

from openai import OpenAI

# ─── Import the environment directly (no Docker needed for local testing) ───
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import DataOpsAction, DataOpsObservation
from server.dataops_environment import DataOpsEnvironment

# ─── Configuration ───
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "dataops_env"
MAX_STEPS = 8
TEMPERATURE = 0.3


def obs_to_text(obs: DataOpsObservation) -> str:
    """Convert an observation to a text prompt for the LLM."""
    parts = []
    if obs.task_description:
        parts.append(f"## Task\n{obs.task_description}")
    if obs.data_preview:
        # Limit preview to avoid token overflow
        preview = obs.data_preview
        if len(preview) > 8000:
            lines = preview.split("\n")
            preview = "\n".join(lines[:50]) + f"\n... ({len(lines) - 50} more rows)"
        parts.append(f"## Data Preview\n```csv\n{preview}\n```")
    if obs.sql_query:
        parts.append(f"## Broken SQL Query\n```sql\n{obs.sql_query}\n```")
    if obs.pipeline_models:
        models_text = ""
        for name, sql in obs.pipeline_models.items():
            models_text += f"\n### {name}\n```sql\n{sql}\n```\n"
        parts.append(f"## Pipeline Models{models_text}")
    if obs.logs:
        parts.append(f"## Pipeline Logs\n```\n{obs.logs}\n```")
    if obs.dependency_graph:
        parts.append(f"## Dependency Graph\n{json.dumps(obs.dependency_graph, indent=2)}")
    if obs.schema_info:
        parts.append(f"## Schema\n```json\n{json.dumps(obs.schema_info, indent=2)}\n```")
    if obs.action_feedback:
        parts.append(f"## Feedback from Last Action\n{obs.action_feedback}")
    if obs.error_message:
        parts.append(f"## Error\n{obs.error_message}")
    parts.append(f"Steps remaining: {obs.steps_remaining} | Current score: {obs.current_score:.2f}")
    return "\n\n".join(parts)


def get_system_prompt(task_type: str) -> str:
    """Get the system prompt for the LLM based on task type."""
    base = (
        "You are an expert data engineer AI agent. "
        "You must respond with ONLY a valid JSON object (no markdown, no explanation). "
        "The JSON must have keys: action_type (string), payload (object).\n\n"
    )

    if task_type == "data_quality_audit":
        return base + (
            "You are auditing a dataset for quality issues.\n"
            "When ready, respond with:\n"
            '{"action_type": "submit_report", "payload": {"issues": [...]}}\n'
            "Each issue should have: issue_type, column, row (optional), description.\n"
            "Valid issue_types: null_value, duplicate_primary_key, invalid_data_type, outlier, foreign_key_violation."
        )
    elif task_type == "sql_bug_fix":
        return base + (
            "You are fixing broken SQL queries.\n"
            "Respond with:\n"
            '{"action_type": "submit_fix", "payload": {"query_id": "q1", "fixed_sql": "SELECT ..."}}\n'
            "Fix the SQL based on the business requirement and known bugs."
        )
    elif task_type == "pipeline_debug":
        return base + (
            "You are debugging a broken data pipeline.\n"
            "First patch buggy models:\n"
            '{"action_type": "patch_model", "payload": {"model_name": "...", "fixed_sql": "CREATE TABLE ... AS ..."}}\n'
            "Then submit:\n"
            '{"action_type": "submit_final", "payload": {}}\n'
            "Only patch models that have bugs. Do NOT patch correct models."
        )
    return base


def parse_llm_action(response_text: str) -> Dict[str, Any]:
    """Parse the LLM response into an action dict."""
    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to extract JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    # Fallback
    return {"action_type": "submit_report", "payload": {"issues": []}}


def run_task(task_type: str, client: OpenAI) -> float:
    """Run a single task and return the score."""
    env = DataOpsEnvironment()
    obs = env.reset(seed=42, task_type=task_type)

    rewards: List[float] = []
    steps = 0
    success = False
    final_score = 0.0

    # Emit [START]
    print(f"[START] task={task_type} env={BENCHMARK} model={MODEL_NAME}")

    try:
        system_prompt = get_system_prompt(task_type)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": obs_to_text(obs)},
        ]

        for step_num in range(1, MAX_STEPS + 1):
            if obs.done:
                break

            # Call LLM
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=4096,
                )
                llm_output = response.choices[0].message.content or ""
            except Exception as e:
                llm_output = json.dumps({
                    "action_type": "submit_report" if task_type == "data_quality_audit" else "submit_final",
                    "payload": {"issues": []} if task_type == "data_quality_audit" else {},
                })

            # Parse action
            action_dict = parse_llm_action(llm_output)
            action = DataOpsAction(
                action_type=action_dict.get("action_type", ""),
                payload=action_dict.get("payload", {}),
            )

            # Step
            obs = env.step(action)
            steps += 1
            reward = float(obs.reward) if obs.reward is not None else 0.0
            rewards.append(reward)

            error_str = obs.error_message or "null"
            done_str = "true" if obs.done else "false"
            action_str = action_dict.get("action_type", "unknown")

            # Emit [STEP]
            print(
                f"[STEP] step={step_num} action={action_str} "
                f"reward={reward:.2f} done={done_str} error={error_str}"
            )

            if obs.done:
                final_score = obs.current_score
                success = final_score > 0
                break

            # Add to conversation
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": obs_to_text(obs)})

    except Exception as e:
        error_msg = str(e)
        print(f"[STEP] step={steps + 1} action=error reward=0.00 done=true error={error_msg}")
        rewards.append(0.0)
        steps += 1

    # Emit [END]
    rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
    success_str = "true" if success else "false"
    print(
        f"[END] success={success_str} steps={steps} "
        f"score={final_score:.2f} rewards={rewards_str}"
    )

    return final_score


def main():
    """Run inference on all 3 tasks."""
    if not API_KEY:
        print("WARNING: No API key found. Set HF_TOKEN, API_KEY, or OPENAI_API_KEY.", file=sys.stderr)

    client = OpenAI(
        api_key=API_KEY or "dummy-key",
        base_url=API_BASE_URL,
    )

    tasks = ["data_quality_audit", "sql_bug_fix", "pipeline_debug"]
    scores = {}

    for task_type in tasks:
        try:
            score = run_task(task_type, client)
            scores[task_type] = score
        except Exception as e:
            print(f"[START] task={task_type} env={BENCHMARK} model={MODEL_NAME}")
            print(f"[STEP] step=1 action=error reward=0.00 done=true error={str(e)}")
            print(f"[END] success=false steps=1 score=0.00 rewards=0.00")
            scores[task_type] = 0.0

    # Summary
    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    print(f"\n# Summary: avg_score={avg_score:.2f}", file=sys.stderr)
    for task, score in scores.items():
        print(f"#   {task}: {score:.2f}", file=sys.stderr)


if __name__ == "__main__":
    main()
