"""
Tests for the DataOps Environment.

Tests all three tasks: data quality audit, SQL bug fix, and pipeline debug.
Verifies reset/step/state API, grading logic, and reward signals.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import DataOpsAction, DataOpsObservation
from server.dataops_environment import DataOpsEnvironment


def test_reset_default():
    """Test default reset initializes data_quality_audit task."""
    env = DataOpsEnvironment()
    obs = env.reset()
    assert obs.task_type == "data_quality_audit"
    assert obs.done is False
    assert obs.reward == 0.0
    assert obs.steps_remaining > 0
    assert obs.data_preview is not None
    assert obs.schema_info is not None
    print(" test_reset_default passed")


def test_reset_sql_fix():
    """Test reset with sql_bug_fix task."""
    env = DataOpsEnvironment()
    obs = env.reset(task_type="sql_bug_fix")
    assert obs.task_type == "sql_bug_fix"
    assert obs.sql_query is not None
    assert obs.done is False
    print(" test_reset_sql_fix passed")


def test_reset_pipeline():
    """Test reset with pipeline_debug task."""
    env = DataOpsEnvironment()
    obs = env.reset(task_type="pipeline_debug")
    assert obs.task_type == "pipeline_debug"
    assert obs.pipeline_models is not None
    assert obs.logs is not None
    assert obs.dependency_graph is not None
    assert obs.done is False
    print(" test_reset_pipeline passed")


def test_state_property():
    """Test state property returns valid State."""
    env = DataOpsEnvironment()
    env.reset()
    state = env.state
    assert state.episode_id is not None
    assert state.step_count == 0
    print(" test_state_property passed")


def test_state_increments():
    """Test step count increments on each step."""
    env = DataOpsEnvironment()
    env.reset(task_type="data_quality_audit")

    action = DataOpsAction(
        action_type="submit_report",
        payload={"issues": []},
    )
    env.step(action)
    assert env.state.step_count == 1
    print(" test_state_increments passed")


def test_audit_empty_report():
    """Test submitting empty audit report gives low score."""
    env = DataOpsEnvironment()
    env.reset(task_type="data_quality_audit")

    action = DataOpsAction(
        action_type="submit_report",
        payload={"issues": []},
    )
    obs = env.step(action)
    assert obs.done is True
    assert obs.current_score == 0.0
    print(" test_audit_empty_report passed")


def test_audit_partial_report():
    """Test submitting partial audit report gives partial score."""
    env = DataOpsEnvironment()
    env.reset(seed=42, task_type="data_quality_audit")

    # Submit some correct issues
    issues = [
        {"issue_type": "null_value", "column": "first_name", "description": "null in first_name"},
        {"issue_type": "null_value", "column": "salary", "description": "null in salary"},
        {"issue_type": "duplicate_primary_key", "column": "employee_id", "description": "dup pk"},
        {"issue_type": "foreign_key_violation", "column": "department_id", "description": "invalid fk"},
        {"issue_type": "outlier", "column": "salary", "description": "salary outlier"},
    ]

    action = DataOpsAction(
        action_type="submit_report",
        payload={"issues": issues},
    )
    obs = env.step(action)
    assert obs.done is True
    assert obs.current_score > 0.0  # Should get partial credit
    assert obs.current_score <= 1.0
    print(f" test_audit_partial_report passed (score={obs.current_score:.4f})")


def test_audit_invalid_action():
    """Test invalid action type gives penalty."""
    env = DataOpsEnvironment()
    env.reset(task_type="data_quality_audit")

    action = DataOpsAction(
        action_type="invalid_action",
        payload={},
    )
    obs = env.step(action)
    assert obs.done is False
    assert obs.reward < 0  # Should be a penalty
    print(" test_audit_invalid_action passed")


def test_sql_fix_correct_query():
    """Test fixing a SQL query correctly gives positive reward."""
    env = DataOpsEnvironment()
    env.reset(task_type="sql_bug_fix")

    # Submit correct fix for q1
    correct_sql = (
        "SELECT d.dept_name, AVG(e.salary) AS avg_salary, COUNT(*) AS emp_count\n"
        "FROM employees e\n"
        "JOIN departments d ON e.dept_id = d.dept_id\n"
        "WHERE e.is_active = 1\n"
        "GROUP BY d.dept_name\n"
        "ORDER BY avg_salary DESC;"
    )

    action = DataOpsAction(
        action_type="submit_fix",
        payload={"query_id": "q1", "fixed_sql": correct_sql},
    )
    obs = env.step(action)
    assert obs.reward > 0  # Should get positive reward
    assert obs.done is False  # More queries to fix
    print(f" test_sql_fix_correct_query passed (reward={obs.reward:.4f})")


def test_sql_fix_broken_query():
    """Test submitting a still-broken SQL gives low/no reward."""
    env = DataOpsEnvironment()
    env.reset(task_type="sql_bug_fix")

    # Submit the same broken query
    action = DataOpsAction(
        action_type="submit_fix",
        payload={
            "query_id": "q1",
            "fixed_sql": "SELECT * FROM nonexistent_table;",
        },
    )
    obs = env.step(action)
    assert obs.reward <= 0  # Should not get positive reward
    print(" test_sql_fix_broken_query passed")


def test_pipeline_patch_and_submit():
    """Test patching pipeline models and submitting."""
    env = DataOpsEnvironment()
    env.reset(task_type="pipeline_debug")

    # Patch the buggy stg_active_employees model
    action = DataOpsAction(
        action_type="patch_model",
        payload={
            "model_name": "stg_active_employees",
            "fixed_sql": (
                "CREATE TABLE stg_active_employees AS\n"
                "SELECT emp_id, first_name, last_name, dept_id,\n"
                "       salary, hire_date, performance_rating\n"
                "FROM raw_employees\n"
                "WHERE is_active = 1;"
            ),
        },
    )
    obs = env.step(action)
    assert obs.done is False
    assert obs.reward > 0
    print(f" pipeline patch stg_active_employees (reward={obs.reward:.4f})")

    # Patch int_dept_metrics
    action = DataOpsAction(
        action_type="patch_model",
        payload={
            "model_name": "int_dept_metrics",
            "fixed_sql": (
                "CREATE TABLE int_dept_metrics AS\n"
                "SELECT d.dept_id, d.dept_name, d.budget, d.target_revenue,\n"
                "       COUNT(e.emp_id) AS active_emp_count,\n"
                "       AVG(e.salary) AS avg_salary,\n"
                "       AVG(e.performance_rating) AS avg_performance,\n"
                "       SUM(e.salary) AS total_salary_cost\n"
                "FROM raw_departments d\n"
                "LEFT JOIN stg_active_employees e ON d.dept_id = e.dept_id\n"
                "GROUP BY d.dept_id, d.dept_name, d.budget, d.target_revenue;"
            ),
        },
    )
    obs = env.step(action)
    assert obs.done is False
    print(f" pipeline patch int_dept_metrics (reward={obs.reward:.4f})")

    # Patch fct_dept_performance
    action = DataOpsAction(
        action_type="patch_model",
        payload={
            "model_name": "fct_dept_performance",
            "fixed_sql": (
                "CREATE TABLE fct_dept_performance AS\n"
                "SELECT m.dept_id, m.dept_name, m.active_emp_count,\n"
                "       m.avg_salary, m.avg_performance, m.total_salary_cost,\n"
                "       m.budget, m.target_revenue,\n"
                "       COALESCE(s.total_revenue, 0) AS total_revenue,\n"
                "       COALESCE(s.total_sales, 0) AS total_sales,\n"
                "       ROUND(COALESCE(s.total_revenue, 0) * 100.0 / m.target_revenue, 2) AS revenue_pct,\n"
                "       ROUND(m.total_salary_cost * 100.0 / m.budget, 2) AS budget_utilization\n"
                "FROM int_dept_metrics m\n"
                "LEFT JOIN int_sales_summary s ON m.dept_id = s.dept_id;"
            ),
        },
    )
    obs = env.step(action)
    assert obs.done is False
    print(f" pipeline patch fct_dept_performance (reward={obs.reward:.4f})")

    # Submit final
    action = DataOpsAction(
        action_type="submit_final",
        payload={},
    )
    obs = env.step(action)
    assert obs.done is True
    assert obs.current_score > 0.5  # Should get a good score with all bugs fixed
    print(f" test_pipeline_patch_and_submit passed (score={obs.current_score:.4f})")


def test_reward_in_range():
    """Test that all task scores are in [0.0, 1.0] range."""
    for task_type in ["data_quality_audit", "sql_bug_fix", "pipeline_debug"]:
        env = DataOpsEnvironment()
        env.reset(task_type=task_type)

        # Submit minimal action
        if task_type == "data_quality_audit":
            action = DataOpsAction(
                action_type="submit_report",
                payload={"issues": []},
            )
        elif task_type == "sql_bug_fix":
            action = DataOpsAction(
                action_type="submit_fix",
                payload={"query_id": "q1", "fixed_sql": "SELECT 1;"},
            )
        else:
            action = DataOpsAction(
                action_type="submit_final",
                payload={},
            )

        obs = env.step(action)
        assert 0.0 <= obs.current_score <= 1.0, f"Score {obs.current_score} out of range for {task_type}"

    print(" test_reward_in_range passed")


def test_deterministic_reset():
    """Test that reset with same seed produces identical observations."""
    env1 = DataOpsEnvironment()
    obs1 = env1.reset(seed=42, task_type="data_quality_audit")

    env2 = DataOpsEnvironment()
    obs2 = env2.reset(seed=42, task_type="data_quality_audit")

    assert obs1.data_preview == obs2.data_preview
    assert obs1.schema_info == obs2.schema_info
    print(" test_deterministic_reset passed")


def test_episode_done_after_submit():
    """Test that episode is done after final submission."""
    env = DataOpsEnvironment()
    env.reset(task_type="data_quality_audit")

    action = DataOpsAction(
        action_type="submit_report",
        payload={"issues": []},
    )
    obs = env.step(action)
    assert obs.done is True

    # Stepping again should indicate already done
    obs2 = env.step(action)
    assert obs2.done is True
    assert obs2.error_message is not None
    print(" test_episode_done_after_submit passed")


if __name__ == "__main__":
    tests = [
        test_reset_default,
        test_reset_sql_fix,
        test_reset_pipeline,
        test_state_property,
        test_state_increments,
        test_audit_empty_report,
        test_audit_partial_report,
        test_audit_invalid_action,
        test_sql_fix_correct_query,
        test_sql_fix_broken_query,
        test_pipeline_patch_and_submit,
        test_reward_in_range,
        test_deterministic_reset,
        test_episode_done_after_submit,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f" {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")

    sys.exit(0 if failed == 0 else 1)
