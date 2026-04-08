"""
Task 3: Pipeline Debugging (Hard)

The agent receives a broken multi-step SQL data pipeline with dependency graph,
execution logs, and must identify the faulty step, fix the SQL models, and
ensure the final output is correct.

Graded by pipeline execution success + final output match.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Pipeline definition
# ──────────────────────────────────────────────────────────────────────

# The pipeline computes a department performance dashboard:
# raw_employees → stg_active_employees → int_dept_metrics → fct_dept_performance

PIPELINE_SETUP_SQL = """
CREATE TABLE IF NOT EXISTS raw_departments (
    dept_id INTEGER PRIMARY KEY,
    dept_name TEXT NOT NULL,
    budget REAL NOT NULL,
    target_revenue REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_employees (
    emp_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dept_id INTEGER NOT NULL,
    salary REAL NOT NULL,
    hire_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    performance_rating REAL,
    FOREIGN KEY (dept_id) REFERENCES raw_departments(dept_id)
);

CREATE TABLE IF NOT EXISTS raw_sales (
    sale_id INTEGER PRIMARY KEY,
    emp_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    sale_date TEXT NOT NULL,
    quarter TEXT NOT NULL,
    FOREIGN KEY (emp_id) REFERENCES raw_employees(emp_id)
);

-- Seed data
INSERT INTO raw_departments VALUES (1, 'Engineering', 5000000, 8000000);
INSERT INTO raw_departments VALUES (2, 'Sales', 3000000, 12000000);
INSERT INTO raw_departments VALUES (3, 'Marketing', 2000000, 5000000);
INSERT INTO raw_departments VALUES (4, 'Support', 1500000, 3000000);

INSERT INTO raw_employees VALUES (1, 'Alice', 'Smith', 1, 150000, '2019-03-15', 1, 4.5);
INSERT INTO raw_employees VALUES (2, 'Bob', 'Johnson', 1, 130000, '2020-06-01', 1, 3.8);
INSERT INTO raw_employees VALUES (3, 'Charlie', 'W', 2, 95000, '2021-01-10', 1, 4.2);
INSERT INTO raw_employees VALUES (4, 'Diana', 'Brown', 2, 88000, '2021-07-22', 1, 3.5);
INSERT INTO raw_employees VALUES (5, 'Eve', 'Garcia', 2, 110000, '2018-11-03', 1, 4.8);
INSERT INTO raw_employees VALUES (6, 'Frank', 'Miller', 3, 95000, '2020-04-15', 1, 3.9);
INSERT INTO raw_employees VALUES (7, 'Grace', 'Davis', 3, 85000, '2022-02-28', 0, 2.5);
INSERT INTO raw_employees VALUES (8, 'Henry', 'Rod', 4, 70000, '2023-01-10', 1, 3.2);
INSERT INTO raw_employees VALUES (9, 'Ivy', 'Mart', 4, 65000, '2023-06-01', 1, 4.0);
INSERT INTO raw_employees VALUES (10, 'Jack', 'Lopez', 1, 140000, '2019-08-10', 0, 3.0);

INSERT INTO raw_sales VALUES (1, 3, 50000, '2024-01-15', 'Q1');
INSERT INTO raw_sales VALUES (2, 3, 75000, '2024-02-20', 'Q1');
INSERT INTO raw_sales VALUES (3, 4, 30000, '2024-01-25', 'Q1');
INSERT INTO raw_sales VALUES (4, 5, 120000, '2024-03-10', 'Q1');
INSERT INTO raw_sales VALUES (5, 5, 95000, '2024-02-15', 'Q1');
INSERT INTO raw_sales VALUES (6, 3, 60000, '2024-04-10', 'Q2');
INSERT INTO raw_sales VALUES (7, 4, 45000, '2024-04-20', 'Q2');
INSERT INTO raw_sales VALUES (8, 5, 110000, '2024-05-15', 'Q2');
INSERT INTO raw_sales VALUES (9, 6, 20000, '2024-01-10', 'Q1');
INSERT INTO raw_sales VALUES (10, 6, 15000, '2024-04-05', 'Q2');
"""

# The broken pipeline models
BROKEN_MODELS = {
    "stg_active_employees": {
        "sql": (
            "CREATE TABLE stg_active_employees AS\n"
            "SELECT emp_id, first_name, last_name, dept_id,\n"
            "       salary, hire_date, performance_rating\n"
            "FROM raw_employees\n"
            "WHERE is_active = 0;"  # BUG: Should be = 1
        ),
        "bug_description": "Filter is inverted: selects INACTIVE employees instead of active ones",
        "depends_on": [],
    },
    "int_dept_metrics": {
        "sql": (
            "CREATE TABLE int_dept_metrics AS\n"
            "SELECT d.dept_id, d.dept_name, d.budget, d.target_revenue,\n"
            "       COUNT(e.emp_id) AS active_emp_count,\n"
            "       AVG(e.salary) AS avg_salary,\n"
            "       AVG(e.performance_rating) AS avg_performance,\n"
            "       SUM(e.salary) AS total_salary_cost\n"
            "FROM raw_departments d\n"
            "LEFT JOIN stg_active_employees e ON d.dept_id = e.dept_id\n"
            "GROUP BY d.dept_id;"  # BUG: GROUP BY missing non-agg columns
        ),
        "bug_description": "GROUP BY clause incomplete - should include all non-aggregated columns",
        "depends_on": ["stg_active_employees"],
    },
    "int_sales_summary": {
        "sql": (
            "CREATE TABLE int_sales_summary AS\n"
            "SELECT e.dept_id,\n"
            "       SUM(s.amount) AS total_revenue,\n"
            "       COUNT(s.sale_id) AS total_sales\n"
            "FROM raw_sales s\n"
            "JOIN raw_employees e ON s.emp_id = e.emp_id\n"
            "GROUP BY e.dept_id;"  # This one is correct
        ),
        "bug_description": None,  # No bug
        "depends_on": [],
    },
    "fct_dept_performance": {
        "sql": (
            "CREATE TABLE fct_dept_performance AS\n"
            "SELECT m.dept_id, m.dept_name, m.active_emp_count,\n"
            "       m.avg_salary, m.avg_performance, m.total_salary_cost,\n"
            "       m.budget, m.target_revenue,\n"
            "       COALESCE(s.total_revenue, 0) AS total_revenue,\n"
            "       COALESCE(s.total_sales, 0) AS total_sales,\n"
            "       ROUND(COALESCE(s.total_revenue, 0) * 100.0 / m.target_revenue, 2) AS revenue_pct,\n"
            "       ROUND(m.total_salary_cost * 100.0 / m.budget, 2) AS budget_utilization\n"
            "FROM int_dept_metrics m\n"
            "JOIN int_sales_summary s ON m.dept_id = s.dept_id;"  # BUG: Should be LEFT JOIN
        ),
        "bug_description": "Should be LEFT JOIN to include departments without sales",
        "depends_on": ["int_dept_metrics", "int_sales_summary"],
    },
}

# Correct models
CORRECT_MODELS = {
    "stg_active_employees": (
        "CREATE TABLE stg_active_employees AS\n"
        "SELECT emp_id, first_name, last_name, dept_id,\n"
        "       salary, hire_date, performance_rating\n"
        "FROM raw_employees\n"
        "WHERE is_active = 1;"
    ),
    "int_dept_metrics": (
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
    "int_sales_summary": (
        "CREATE TABLE int_sales_summary AS\n"
        "SELECT e.dept_id,\n"
        "       SUM(s.amount) AS total_revenue,\n"
        "       COUNT(s.sale_id) AS total_sales\n"
        "FROM raw_sales s\n"
        "JOIN raw_employees e ON s.emp_id = e.emp_id\n"
        "GROUP BY e.dept_id;"
    ),
    "fct_dept_performance": (
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
}

EXECUTION_ORDER = ["stg_active_employees", "int_sales_summary", "int_dept_metrics", "fct_dept_performance"]

DEPENDENCY_GRAPH = {
    "stg_active_employees": [],
    "int_sales_summary": [],
    "int_dept_metrics": ["stg_active_employees"],
    "fct_dept_performance": ["int_dept_metrics", "int_sales_summary"],
}

PIPELINE_LOGS = """[2024-03-15 10:00:01] INFO  Pipeline 'dept_performance' started
[2024-03-15 10:00:02] INFO  Running model: stg_active_employees
[2024-03-15 10:00:02] WARN  stg_active_employees: Result has only 2 rows (expected ~8 active employees)
[2024-03-15 10:00:03] INFO  Running model: int_sales_summary
[2024-03-15 10:00:03] INFO  int_sales_summary: OK, 3 rows produced
[2024-03-15 10:00:04] INFO  Running model: int_dept_metrics
[2024-03-15 10:00:04] WARN  int_dept_metrics: Low employee counts detected - metrics may be unreliable
[2024-03-15 10:00:05] INFO  Running model: fct_dept_performance
[2024-03-15 10:00:05] WARN  fct_dept_performance: Only 3 departments in output (expected 4)
[2024-03-15 10:00:05] ERROR fct_dept_performance: Missing departments in final output: Support
[2024-03-15 10:00:06] INFO  Pipeline completed with WARNINGS
[2024-03-15 10:00:06] INFO  Final output: 3 rows (expected 4 departments)
[2024-03-15 10:00:06] ERROR Data validation FAILED: Missing data for department 'Support'
"""


class PipelineTask:
    """Manages the pipeline debugging task state and grading."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.patched_models: Dict[str, str] = {}
        self.max_steps = 10
        self.scores: Dict[str, float] = {}
        self.pipeline_run = False
        self.total_score = 0.0

        # Pre-compute expected output
        self._expected_output = self._run_correct_pipeline()

    def _create_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.executescript(PIPELINE_SETUP_SQL)
        return conn

    def _run_correct_pipeline(self) -> List[tuple]:
        """Run the correct pipeline and return the final output."""
        conn = self._create_db()
        for model_name in EXECUTION_ORDER:
            conn.execute(CORRECT_MODELS[model_name])
        cursor = conn.execute("SELECT * FROM fct_dept_performance ORDER BY dept_id")
        result = cursor.fetchall()
        conn.close()
        return result

    def get_initial_observation(self) -> Dict[str, Any]:
        """Return initial observation for the pipeline task."""
        models_display = {}
        for name, info in BROKEN_MODELS.items():
            models_display[name] = info["sql"]

        return {
            "task_type": "pipeline_debug",
            "task_description": (
                "You are a data engineer debugging a broken data pipeline.\n"
                "The pipeline computes department performance metrics from raw tables.\n"
                "It has 4 SQL models that run in dependency order.\n\n"
                "Review the pipeline logs, the SQL models, and the dependency graph.\n"
                "Identify which models have bugs and fix them.\n\n"
                "Actions:\n"
                "  1. patch_model: payload={model_name, fixed_sql} — fix a model's SQL\n"
                "  2. submit_final: payload={} — run the patched pipeline and grade\n\n"
                "You must patch ALL buggy models before submitting.\n"
                "Models with no bugs should NOT be patched."
            ),
            "pipeline_models": models_display,
            "logs": PIPELINE_LOGS,
            "dependency_graph": DEPENDENCY_GRAPH,
            "schema_info": {
                "raw_departments": "dept_id, dept_name, budget, target_revenue",
                "raw_employees": "emp_id, first_name, last_name, dept_id, salary, hire_date, is_active, performance_rating",
                "raw_sales": "sale_id, emp_id, amount, sale_date, quarter",
            },
            "steps_remaining": self.max_steps,
            "current_score": 0.0,
        }

    def process_action(self, action_type: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool]:
        """Process a pipeline action."""
        if action_type == "patch_model":
            return self._patch_model(payload)
        elif action_type == "submit_final":
            return self._submit_final()
        else:
            return (
                {
                    "error_message": f"Invalid action_type '{action_type}'. Use 'patch_model' or 'submit_final'.",
                    "action_feedback": "Use patch_model or submit_final.",
                },
                -0.05,
                False,
            )

    def _patch_model(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool]:
        """Apply a model patch."""
        model_name = payload.get("model_name", "")
        fixed_sql = payload.get("fixed_sql", "")

        if not model_name or not fixed_sql:
            return (
                {"error_message": "payload must contain 'model_name' and 'fixed_sql'"},
                -0.05,
                False,
            )

        if model_name not in BROKEN_MODELS:
            return (
                {"error_message": f"Unknown model '{model_name}'. Valid: {list(BROKEN_MODELS.keys())}"},
                -0.05,
                False,
            )

        # Validate SQL syntax
        test_conn = self._create_db()
        try:
            # Run prerequisite models first
            for dep in EXECUTION_ORDER:
                if dep == model_name:
                    break
                sql = self.patched_models.get(dep, BROKEN_MODELS[dep]["sql"])
                try:
                    test_conn.execute(sql)
                except Exception:
                    pass

            test_conn.execute(fixed_sql)
            self.patched_models[model_name] = fixed_sql

            # Partial reward for patching a buggy model
            is_buggy = BROKEN_MODELS[model_name]["bug_description"] is not None
            reward = 0.05 if is_buggy else -0.03  # Small penalty for patching a correct model

            return (
                {
                    "action_feedback": f"Model '{model_name}' patched successfully. SQL validated OK.",
                    "current_score": self.total_score,
                },
                reward,
                False,
            )
        except Exception as e:
            return (
                {
                    "error_message": f"SQL error in patched model: {str(e)}",
                    "action_feedback": "Fix the SQL syntax and retry.",
                },
                -0.1,
                False,
            )
        finally:
            test_conn.close()

    def _submit_final(self) -> Tuple[Dict[str, Any], float, bool]:
        """Run the patched pipeline and grade the output."""
        conn = self._create_db()
        errors = []
        models_ok = 0

        for model_name in EXECUTION_ORDER:
            sql = self.patched_models.get(model_name, BROKEN_MODELS[model_name]["sql"])
            try:
                conn.execute(sql)
                models_ok += 1
            except Exception as e:
                errors.append(f"Model '{model_name}' failed: {str(e)}")
                break

        # Check final output
        if not errors:
            try:
                cursor = conn.execute("SELECT * FROM fct_dept_performance ORDER BY dept_id")
                actual = cursor.fetchall()
            except Exception as e:
                actual = []
                errors.append(f"Final output query failed: {str(e)}")
        else:
            actual = []

        conn.close()

        # Calculate score
        pipeline_score = models_ok / len(EXECUTION_ORDER) * 0.3  # 30% for pipeline running

        # Output match
        output_score = 0.0
        if actual and self._expected_output:
            def normalize(rows):
                return set(tuple(str(v) for v in r) for r in rows)

            expected_set = normalize(self._expected_output)
            actual_set = normalize(actual)

            if expected_set:
                intersection = expected_set & actual_set
                output_score = len(intersection) / len(expected_set)

        # Correct bug identification
        buggy_models = {k for k, v in BROKEN_MODELS.items() if v["bug_description"] is not None}
        patched_models_set = set(self.patched_models.keys())

        correctly_patched = buggy_models & patched_models_set
        wrongly_patched = patched_models_set - buggy_models
        missed_bugs = buggy_models - patched_models_set

        identification_score = len(correctly_patched) / len(buggy_models) if buggy_models else 1.0
        wrong_penalty = len(wrongly_patched) * 0.1

        # Final composite score
        self.total_score = round(min(1.0, max(0.0,
            pipeline_score * 0.2 +
            output_score * 0.5 +
            identification_score * 0.3 -
            wrong_penalty
        )), 4)

        feedback_parts = [
            f"Pipeline execution: {models_ok}/{len(EXECUTION_ORDER)} models ran successfully.",
            f"Output match: {output_score:.2%} of expected rows found.",
            f"Bug identification: {len(correctly_patched)}/{len(buggy_models)} bugs correctly fixed.",
        ]
        if wrongly_patched:
            feedback_parts.append(f"Unnecessary patches: {list(wrongly_patched)}")
        if missed_bugs:
            feedback_parts.append(f"Missed bugs in: {list(missed_bugs)}")
        if errors:
            feedback_parts.append(f"Errors: {'; '.join(errors)}")

        return (
            {
                "action_feedback": " | ".join(feedback_parts),
                "current_score": self.total_score,
            },
            self.total_score,
            True,
        )
