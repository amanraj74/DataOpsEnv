---
title: DataOpsenv Benchmark
emoji: 🏆
colorFrom: blue
colorTo: indigo
sdk: docker
tags:
  - openenv
pinned: false
---
# 🏆 DataOpsEnv — AI Data Engineering Agent Benchmark

> A production-grade OpenEnv benchmark that evaluates AI agents on real-world data engineering tasks with deterministic grading and dense reward signals.

## 📋 Overview

DataOpsEnv is an OpenEnv-compatible environment that simulates real-world data engineering workflows. It enables AI agents to:

- **Audit data quality** in datasets (detect nulls, duplicates, type errors, outliers, FK violations)
- **Repair broken SQL queries** (fix joins, filters, aggregations, cartesian products)
- **Debug data pipelines** (identify faulty steps, fix SQL models, resolve dependencies)

The environment provides **deterministic grading**, **dense reward signals**, and **multi-step reasoning tasks** — making it ideal for evaluating and training autonomous data engineering agents.

## 🎯 Motivation

Modern organizations lose millions due to poor data quality, broken pipelines, and incorrect analytics queries. Data engineers spend hours debugging CSV issues, SQL bugs, and pipeline failures. DataOpsEnv simulates these **exact workflows** as a benchmark for AI agents.

## 🧩 Tasks

### Task 1 — Data Quality Audit (Easy)
| Property | Details |
|----------|---------|
| **Goal** | Detect all quality issues in a 235-row employee dataset |
| **Input** | CSV data + schema definition with constraints |
| **Agent Finds** | Null values, duplicate PKs, invalid types, outliers, FK violations |
| **Action** | `submit_report(issues=[...])` |
| **Grading** | F1 score (precision + recall) with partial credit |
| **Score Range** | 0.0 — 1.0 |

### Task 2 — SQL Bug Fix (Medium)
| Property | Details |
|----------|---------|
| **Goal** | Fix 4 broken SQL queries against a real database |
| **Input** | Broken SQL + schema + business requirements |
| **Agent Fixes** | Missing JOINs, wrong filters, bad GROUP BY, cartesian products |
| **Action** | `submit_fix(query_id, fixed_sql)` |
| **Grading** | Row-level output match against expected results |
| **Score Range** | 0.0 — 1.0 |

### Task 3 — Pipeline Debugging (Hard)
| Property | Details |
|----------|---------|
| **Goal** | Fix a broken 4-model SQL data pipeline |
| **Input** | SQL models + error logs + dependency graph |
| **Agent Must** | Identify faulty models, fix SQL, ensure correct output |
| **Actions** | `patch_model(name, sql)` then `submit_final()` |
| **Grading** | Pipeline success + output match + bug identification |
| **Score Range** | 0.0 — 1.0 |

## 🔧 Action Space

```python
class DataOpsAction(Action):
    action_type: str   # submit_report | submit_fix | patch_model | submit_final
    task_id: str       # Task identifier
    payload: dict      # Action-specific data
```

### Action Types

| Action | Task | Payload |
|--------|------|---------|
| `submit_report` | Audit | `{issues: [{issue_type, column, row, description}]}` |
| `submit_fix` | SQL Fix | `{query_id: str, fixed_sql: str}` |
| `patch_model` | Pipeline | `{model_name: str, fixed_sql: str}` |
| `submit_final` | Pipeline | `{}` |

## 👁️ Observation Space

```python
class DataOpsObservation(Observation):
    task_type: str              # Current task identifier
    task_description: str       # Human-readable objective
    data_preview: str | None    # CSV data or query results
    sql_query: str | None       # SQL to fix
    pipeline_models: dict | None  # Pipeline SQL models
    schema_info: dict           # Database schema
    logs: str | None            # Pipeline execution logs
    dependency_graph: dict | None  # Model dependencies
    error_message: str | None   # Last error
    steps_remaining: int        # Steps left
    current_score: float        # Running score [0.0-1.0]
    action_feedback: str | None # Grading feedback
    done: bool                  # Episode complete?
    reward: float               # Step reward
```

## 💰 Reward Function

Dense reward system with step-by-step signals:

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

**Key features:**
- ✅ Step-by-step rewards (not sparse)
- ✅ Partial credit for partial solutions
- ✅ Penalties for bad behavior
- ✅ Score always in [0.0, 1.0]

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+
- Docker (for containerized deployment)

### Local Development

```bash
# Clone and install
cd dataops_env
pip install -e ".[dev]"

# Run tests
python tests/test_env.py

# Start server locally
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build
docker build -f server/Dockerfile -t dataops-env .

# Run
docker run -p 8000:8000 dataops-env
```

### Run Inference

```bash
# Set environment variables
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

# Run
python inference.py
```

## 📊 Baseline Results

| Task | Score | Steps |
|------|-------|-------|
| Data Quality Audit | ~0.45 | 1-2 |
| SQL Bug Fix | ~0.60 | 4-6 |
| Pipeline Debug | ~0.70 | 4-5 |
| **Average** | **~0.58** | **~12** |

*Baseline with Qwen2.5-72B-Instruct at temperature=0.3*

## 🏗️ Project Structure

```
dataops_env/
├── inference.py              # Baseline inference script (root)
├── openenv.yaml              # OpenEnv manifest
├── models.py                 # Pydantic Action/Observation models
├── pyproject.toml            # Dependencies
├── README.md                 # This file
├── server/
│   ├── app.py                # FastAPI server
│   ├── Dockerfile            # Container image
│   ├── requirements.txt      # Server dependencies
│   ├── dataops_environment.py  # Main environment class
│   └── tasks/
│       ├── task_audit.py     # Data quality audit task
│       ├── task_sql_fix.py   # SQL bug fix task
│       └── task_pipeline.py  # Pipeline debug task
└── tests/
    └── test_env.py           # Test suite
```

## ⚙️ Environment Design

- **reset()** → Clean state initialization with task selection
- **step(action)** → Dense reward per action with immediate feedback
- **state** → Episode tracking with step count and ID
- **Deterministic** → Same seed = same dataset/queries/pipeline
- **Episode Boundaries** → Clear done signal on final submission or step limit

## 📄 License

BSD 3-Clause License
