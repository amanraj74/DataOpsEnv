---
title: DataOps Benchmark
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
tags:
  - openenv
pinned: false
---
# DataOpsEnv

AI Data Engineering Agent Benchmark built on the OpenEnv framework.

## What It Does

DataOpsEnv evaluates AI agents on real-world data engineering tasks. Agents interact with datasets, SQL queries, and data pipelines through a standardized step/reset/state API. Each action receives immediate, graded feedback.

This environment simulates three core workflows that data engineers perform daily:

1. **Data Quality Audit** (Easy) - Inspect a 235-row employee dataset and identify quality issues such as null values, duplicate primary keys, invalid data types, outliers, and foreign key violations.

2. **SQL Bug Fix** (Medium) - Diagnose and repair 4 broken SQL queries against a relational database. Bugs include missing JOINs, incorrect filters, bad GROUP BY clauses, and cartesian products.

3. **Pipeline Debugging** (Hard) - Debug a 4-model SQL data pipeline by reading execution logs, identifying faulty models, patching their SQL, and verifying the corrected output.

## Motivation

Data quality issues, broken queries, and pipeline failures cost organizations millions annually. DataOpsEnv provides a controlled, deterministic testbed where AI agents can be trained and evaluated on these exact failure modes.

## Action Space

```python
class DataOpsAction(Action):
    action_type: str   # submit_report | submit_fix | patch_model | submit_final
    task_id: str       # Task identifier
    payload: dict      # Action-specific data
```

| Action | Task | Payload |
|--------|------|---------|
| submit_report | Audit | {issues: [{issue_type, column, row, description}]} |
| submit_fix | SQL Fix | {query_id: str, fixed_sql: str} |
| patch_model | Pipeline | {model_name: str, fixed_sql: str} |
| submit_final | Pipeline | {} |

## Observation Space

```python
class DataOpsObservation(Observation):
    task_type: str
    task_description: str
    data_preview: str | None
    sql_query: str | None
    pipeline_models: dict | None
    schema_info: dict
    logs: str | None
    dependency_graph: dict | None
    error_message: str | None
    steps_remaining: int
    current_score: float
    action_feedback: str | None
    done: bool
    reward: float
```

## Reward Function

The environment uses dense rewards with partial credit:

| Action | Reward |
|--------|--------|
| Correct issue detected | +0.1 per type match |
| Correct SQL fix | +0.15 to +0.4 (weighted by difficulty) |
| Correct pipeline patch | +0.05 per buggy model |
| Final correct output | Up to +0.5 |
| Hallucinated issue | -0.05 |
| Wrong fix / syntax error | -0.1 |
| Unnecessary patch | -0.03 |
| Invalid action | -0.05 |

All scores are clamped to the [0.0, 1.0] range.

## Setup

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)

### Local Development

```bash
cd dataops_env
pip install -e ".[dev]"
python tests/test_env.py
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t dataops-env .
docker run -p 7860:7860 dataops-env
```

### Inference

```bash
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

## Baseline Results

| Task | Score | Steps |
|------|-------|-------|
| Data Quality Audit | ~0.45 | 1-2 |
| SQL Bug Fix | ~0.60 | 4-6 |
| Pipeline Debug | ~0.70 | 4-5 |
| Average | ~0.58 | ~12 |

Baseline: Qwen2.5-72B-Instruct, temperature=0.3

## Project Structure

```
dataops_env/
  Dockerfile
  inference.py
  openenv.yaml
  models.py
  client.py
  pyproject.toml
  requirements.txt
  README.md
  server/
    app.py
    dataops_environment.py
    tasks/
      task_audit.py
      task_sql_fix.py
      task_pipeline.py
  tests/
    test_env.py
  outputs/
```

## Environment Design

- **reset()** returns a clean initial observation with task context
- **step(action)** returns observation, reward, done flag, and feedback
- **state** tracks episode_id and step_count
- **Deterministic**: same seed produces identical episodes
- **Episode boundaries**: episodes end on final submission or step limit

## License

BSD 3-Clause License
