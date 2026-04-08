"""
Task 2: SQL Bug Fix & Optimization (Medium)

The agent receives broken SQL queries along with schema and business
requirements. Must fix joins, correct filters, fix aggregation, and
remove cartesian products.

Graded by executing fixed SQL against an in-memory SQLite database
and comparing output with expected results (row-level match ratio).
"""

import sqlite3
import json
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Database schema + seed data
# ──────────────────────────────────────────────────────────────────────

SETUP_SQL = """
CREATE TABLE IF NOT EXISTS departments (
    dept_id INTEGER PRIMARY KEY,
    dept_name TEXT NOT NULL,
    budget REAL NOT NULL,
    location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
    emp_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    dept_id INTEGER NOT NULL,
    salary REAL NOT NULL,
    hire_date TEXT NOT NULL,
    manager_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id),
    FOREIGN KEY (manager_id) REFERENCES employees(emp_id)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL,
    dept_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    budget REAL NOT NULL,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);

CREATE TABLE IF NOT EXISTS project_assignments (
    assignment_id INTEGER PRIMARY KEY,
    emp_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    hours_allocated REAL NOT NULL,
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS salary_history (
    history_id INTEGER PRIMARY KEY,
    emp_id INTEGER NOT NULL,
    old_salary REAL NOT NULL,
    new_salary REAL NOT NULL,
    change_date TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id)
);

-- Seed departments
INSERT INTO departments VALUES (101, 'Engineering', 5000000, 'San Francisco');
INSERT INTO departments VALUES (102, 'Marketing', 2000000, 'New York');
INSERT INTO departments VALUES (103, 'Sales', 3000000, 'Chicago');
INSERT INTO departments VALUES (104, 'HR', 1500000, 'San Francisco');
INSERT INTO departments VALUES (105, 'Finance', 2500000, 'New York');
INSERT INTO departments VALUES (106, 'Operations', 1800000, 'Chicago');

-- Seed employees
INSERT INTO employees VALUES (1, 'Alice', 'Smith', 'alice.smith@co.com', 101, 150000, '2019-03-15', NULL, 1);
INSERT INTO employees VALUES (2, 'Bob', 'Johnson', 'bob.johnson@co.com', 101, 130000, '2020-06-01', 1, 1);
INSERT INTO employees VALUES (3, 'Charlie', 'Williams', 'charlie.w@co.com', 102, 95000, '2021-01-10', NULL, 1);
INSERT INTO employees VALUES (4, 'Diana', 'Brown', 'diana.b@co.com', 102, 88000, '2021-07-22', 3, 1);
INSERT INTO employees VALUES (5, 'Eve', 'Garcia', 'eve.g@co.com', 103, 110000, '2018-11-03', NULL, 1);
INSERT INTO employees VALUES (6, 'Frank', 'Miller', 'frank.m@co.com', 103, 95000, '2020-04-15', 5, 1);
INSERT INTO employees VALUES (7, 'Grace', 'Davis', 'grace.d@co.com', 104, 85000, '2022-02-28', NULL, 1);
INSERT INTO employees VALUES (8, 'Henry', 'Rodriguez', 'henry.r@co.com', 101, 140000, '2019-08-10', 1, 1);
INSERT INTO employees VALUES (9, 'Ivy', 'Martinez', 'ivy.m@co.com', 105, 120000, '2020-12-01', NULL, 1);
INSERT INTO employees VALUES (10, 'Jack', 'Lopez', 'jack.l@co.com', 106, 78000, '2023-03-20', NULL, 1);
INSERT INTO employees VALUES (11, 'Karen', 'Wilson', 'karen.w@co.com', 101, 125000, '2021-09-14', 1, 0);
INSERT INTO employees VALUES (12, 'Leo', 'Anderson', 'leo.a@co.com', 103, 92000, '2022-05-30', 5, 1);

-- Seed projects
INSERT INTO projects VALUES (1001, 'Platform Rewrite', 101, '2023-01-01', '2024-06-30', 'active', 800000);
INSERT INTO projects VALUES (1002, 'Brand Campaign', 102, '2023-06-01', '2023-12-31', 'completed', 300000);
INSERT INTO projects VALUES (1003, 'Sales Dashboard', 103, '2024-01-01', NULL, 'active', 150000);
INSERT INTO projects VALUES (1004, 'HR System', 104, '2023-09-01', '2024-03-31', 'active', 200000);
INSERT INTO projects VALUES (1005, 'Budget Tool', 105, '2024-02-01', NULL, 'active', 250000);

-- Seed project assignments
INSERT INTO project_assignments VALUES (1, 1, 1001, 'Lead', 40);
INSERT INTO project_assignments VALUES (2, 2, 1001, 'Developer', 35);
INSERT INTO project_assignments VALUES (3, 8, 1001, 'Developer', 30);
INSERT INTO project_assignments VALUES (4, 3, 1002, 'Lead', 40);
INSERT INTO project_assignments VALUES (5, 4, 1002, 'Designer', 25);
INSERT INTO project_assignments VALUES (6, 5, 1003, 'Lead', 40);
INSERT INTO project_assignments VALUES (7, 6, 1003, 'Analyst', 30);
INSERT INTO project_assignments VALUES (8, 12, 1003, 'Analyst', 20);
INSERT INTO project_assignments VALUES (9, 7, 1004, 'Lead', 40);
INSERT INTO project_assignments VALUES (10, 9, 1005, 'Lead', 35);

-- Seed salary history
INSERT INTO salary_history VALUES (1, 1, 120000, 150000, '2022-01-01', 'promotion');
INSERT INTO salary_history VALUES (2, 2, 110000, 130000, '2022-06-01', 'annual raise');
INSERT INTO salary_history VALUES (3, 5, 95000, 110000, '2021-01-01', 'promotion');
INSERT INTO salary_history VALUES (4, 8, 125000, 140000, '2022-01-01', 'annual raise');
INSERT INTO salary_history VALUES (5, 9, 100000, 120000, '2023-01-01', 'promotion');
"""


# ──────────────────────────────────────────────────────────────────────
# Broken queries with expected corrections
# ──────────────────────────────────────────────────────────────────────

QUERIES = [
    {
        "query_id": "q1",
        "title": "Department Salary Report",
        "business_requirement": (
            "Get average salary and employee count per department, "
            "only for active employees, ordered by average salary descending."
        ),
        "broken_sql": (
            "SELECT d.dept_name, AVG(e.salary), COUNT(*)\n"
            "FROM employees e, departments d\n"
            "WHERE e.is_active = 1\n"
            "ORDER BY AVG(e.salary) DESC;"
        ),
        "bugs": ["Missing JOIN condition (cartesian product)", "Missing GROUP BY clause"],
        "correct_sql": (
            "SELECT d.dept_name, AVG(e.salary) AS avg_salary, COUNT(*) AS emp_count\n"
            "FROM employees e\n"
            "JOIN departments d ON e.dept_id = d.dept_id\n"
            "WHERE e.is_active = 1\n"
            "GROUP BY d.dept_name\n"
            "ORDER BY avg_salary DESC;"
        ),
        "difficulty": "easy",
    },
    {
        "query_id": "q2",
        "title": "High-Value Project Team Members",
        "business_requirement": (
            "Find all active employees working on projects with budget > 200000, "
            "showing employee name, project name, role, and project budget. "
            "Order by project budget descending, then employee last name."
        ),
        "broken_sql": (
            "SELECT e.first_name, e.last_name, p.project_name, pa.role, p.budget\n"
            "FROM employees e\n"
            "JOIN project_assignments pa ON e.emp_id = pa.emp_id\n"
            "JOIN projects p ON pa.project_id = p.project_id\n"
            "WHERE p.budget > 200000\n"
            "ORDER BY p.budget DESC, e.last_name;"
        ),
        "bugs": ["Missing filter for active employees (is_active = 1)"],
        "correct_sql": (
            "SELECT e.first_name, e.last_name, p.project_name, pa.role, p.budget\n"
            "FROM employees e\n"
            "JOIN project_assignments pa ON e.emp_id = pa.emp_id\n"
            "JOIN projects p ON pa.project_id = p.project_id\n"
            "WHERE p.budget > 200000 AND e.is_active = 1\n"
            "ORDER BY p.budget DESC, e.last_name;"
        ),
        "difficulty": "easy",
    },
    {
        "query_id": "q3",
        "title": "Salary Growth Analysis",
        "business_requirement": (
            "For each employee who had a salary change, show their name, "
            "current department, total salary increase (sum of all increases), "
            "and number of raises. Only include employees still active."
        ),
        "broken_sql": (
            "SELECT e.first_name, e.last_name, d.dept_name,\n"
            "       SUM(sh.new_salary - sh.old_salary) AS total_increase,\n"
            "       COUNT(sh.history_id) AS num_raises\n"
            "FROM employees e\n"
            "LEFT JOIN salary_history sh ON e.emp_id = sh.emp_id\n"
            "LEFT JOIN departments d ON e.dept_id = d.dept_id\n"
            "WHERE e.is_active = 1\n"
            "GROUP BY e.emp_id;"
        ),
        "bugs": [
            "LEFT JOIN on salary_history includes employees with no history (should be INNER JOIN)",
            "GROUP BY should include all non-aggregated columns",
        ],
        "correct_sql": (
            "SELECT e.first_name, e.last_name, d.dept_name,\n"
            "       SUM(sh.new_salary - sh.old_salary) AS total_increase,\n"
            "       COUNT(sh.history_id) AS num_raises\n"
            "FROM employees e\n"
            "JOIN salary_history sh ON e.emp_id = sh.emp_id\n"
            "JOIN departments d ON e.dept_id = d.dept_id\n"
            "WHERE e.is_active = 1\n"
            "GROUP BY e.first_name, e.last_name, d.dept_name;"
        ),
        "difficulty": "medium",
    },
    {
        "query_id": "q4",
        "title": "Department Budget Utilization",
        "business_requirement": (
            "Show each department's budget, total employee salaries, "
            "total active project budgets, and remaining budget "
            "(dept_budget - total_salaries). Order by remaining budget ascending."
        ),
        "broken_sql": (
            "SELECT d.dept_name, d.budget,\n"
            "       SUM(e.salary) AS total_salaries,\n"
            "       SUM(p.budget) AS total_project_budgets,\n"
            "       d.budget - SUM(e.salary) AS remaining\n"
            "FROM departments d\n"
            "JOIN employees e ON d.dept_id = e.dept_id\n"
            "JOIN projects p ON d.dept_id = p.dept_id\n"
            "GROUP BY d.dept_name\n"
            "ORDER BY remaining ASC;"
        ),
        "bugs": [
            "CROSS multiplication: JOINing employees and projects through departments creates duplicates",
            "Should use subqueries or separate aggregations to avoid inflated sums",
        ],
        "correct_sql": (
            "SELECT d.dept_name, d.budget,\n"
            "       COALESCE(emp.total_salaries, 0) AS total_salaries,\n"
            "       COALESCE(proj.total_project_budgets, 0) AS total_project_budgets,\n"
            "       d.budget - COALESCE(emp.total_salaries, 0) AS remaining\n"
            "FROM departments d\n"
            "LEFT JOIN (\n"
            "    SELECT dept_id, SUM(salary) AS total_salaries\n"
            "    FROM employees WHERE is_active = 1\n"
            "    GROUP BY dept_id\n"
            ") emp ON d.dept_id = emp.dept_id\n"
            "LEFT JOIN (\n"
            "    SELECT dept_id, SUM(budget) AS total_project_budgets\n"
            "    FROM projects WHERE status = 'active'\n"
            "    GROUP BY dept_id\n"
            ") proj ON d.dept_id = proj.dept_id\n"
            "ORDER BY remaining ASC;"
        ),
        "difficulty": "hard",
    },
]


def _create_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with seed data."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SETUP_SQL)
    return conn


def _run_query(conn: sqlite3.Connection, sql: str) -> Optional[List[tuple]]:
    """Execute a SQL query and return results, or None on error."""
    try:
        cursor = conn.execute(sql)
        return cursor.fetchall()
    except Exception:
        return None


class SqlFixTask:
    """Manages the SQL bug fix task state and grading."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.db = _create_db()
        self.queries = QUERIES
        self.current_query_idx = 0
        self.scores: Dict[str, float] = {}
        self.max_steps = 12  # ~3 steps per query
        self.total_score = 0.0

        # Pre-compute expected outputs
        self.expected_outputs: Dict[str, List[tuple]] = {}
        for q in self.queries:
            result = _run_query(self.db, q["correct_sql"])
            self.expected_outputs[q["query_id"]] = result if result else []

    def get_schema_info(self) -> Dict[str, Any]:
        """Return the database schema."""
        return {
            "tables": {
                "departments": {
                    "columns": ["dept_id (PK)", "dept_name", "budget", "location"],
                    "row_count": 6,
                },
                "employees": {
                    "columns": [
                        "emp_id (PK)", "first_name", "last_name", "email",
                        "dept_id (FK→departments)", "salary", "hire_date",
                        "manager_id (FK→employees, nullable)", "is_active",
                    ],
                    "row_count": 12,
                },
                "projects": {
                    "columns": [
                        "project_id (PK)", "project_name", "dept_id (FK→departments)",
                        "start_date", "end_date (nullable)", "status", "budget",
                    ],
                    "row_count": 5,
                },
                "project_assignments": {
                    "columns": [
                        "assignment_id (PK)", "emp_id (FK→employees)",
                        "project_id (FK→projects)", "role", "hours_allocated",
                    ],
                    "row_count": 10,
                },
                "salary_history": {
                    "columns": [
                        "history_id (PK)", "emp_id (FK→employees)",
                        "old_salary", "new_salary", "change_date", "reason",
                    ],
                    "row_count": 5,
                },
            },
        }

    def get_initial_observation(self) -> Dict[str, Any]:
        """Return the initial observation for the SQL fix task."""
        q = self.queries[0]
        return {
            "task_type": "sql_bug_fix",
            "task_description": (
                "You are a data engineer. Fix broken SQL queries.\n"
                "For each query, you'll see the broken SQL, the business requirement,\n"
                "and the database schema. Fix the SQL and submit using\n"
                "action_type='submit_fix' with payload: {query_id, fixed_sql}.\n\n"
                f"Query 1 of {len(self.queries)}: {q['title']}\n"
                f"Business Requirement: {q['business_requirement']}\n"
                f"Known Bugs: {', '.join(q['bugs'])}"
            ),
            "sql_query": q["broken_sql"],
            "schema_info": self.get_schema_info(),
            "steps_remaining": self.max_steps,
            "current_score": 0.0,
        }

    def process_action(self, action_type: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool]:
        """Process a SQL fix submission."""
        if action_type != "submit_fix":
            return (
                {
                    "error_message": f"Invalid action_type '{action_type}' for sql_bug_fix task. Use 'submit_fix'.",
                    "action_feedback": "Use action_type='submit_fix' with payload: {query_id, fixed_sql}",
                },
                -0.05,
                False,
            )

        query_id = payload.get("query_id", "")
        fixed_sql = payload.get("fixed_sql", "")

        if not query_id or not fixed_sql:
            return (
                {"error_message": "payload must contain 'query_id' and 'fixed_sql'"},
                -0.05,
                False,
            )

        # Find the query
        query = None
        for q in self.queries:
            if q["query_id"] == query_id:
                query = q
                break

        if query is None:
            return (
                {"error_message": f"Unknown query_id '{query_id}'"},
                -0.05,
                False,
            )

        # Already graded?
        if query_id in self.scores:
            return (
                {"action_feedback": f"Query {query_id} already graded with score {self.scores[query_id]:.2f}"},
                -0.05,
                False,
            )

        # Execute the fixed SQL
        actual = _run_query(self.db, fixed_sql)
        if actual is None:
            return (
                {
                    "error_message": "SQL execution error. Your query has a syntax error or runtime error.",
                    "action_feedback": "Fix the SQL syntax and resubmit.",
                },
                -0.1,
                False,
            )

        # Compare with expected
        expected = self.expected_outputs[query_id]
        score = self._compare_results(expected, actual)
        self.scores[query_id] = score

        # Weighted score: weight by difficulty
        weight = {"easy": 0.15, "medium": 0.3, "hard": 0.4}.get(query["difficulty"], 0.2)
        reward = score * weight

        # Check if we should move to the next query
        done = len(self.scores) == len(self.queries)
        self.total_score = sum(self.scores.values()) / len(self.queries)

        obs: Dict[str, Any] = {
            "action_feedback": (
                f"Query {query_id} graded: {score:.2f} (row match ratio). "
                f"{len(self.scores)}/{len(self.queries)} queries graded."
            ),
            "current_score": round(self.total_score, 4),
        }

        # Show next query if not done
        if not done:
            remaining = [q for q in self.queries if q["query_id"] not in self.scores]
            if remaining:
                nxt = remaining[0]
                obs.update({
                    "sql_query": nxt["broken_sql"],
                    "task_description": (
                        f"Next query: {nxt['title']}\n"
                        f"Business Requirement: {nxt['business_requirement']}\n"
                        f"Known Bugs: {', '.join(nxt['bugs'])}"
                    ),
                })

        return obs, round(reward, 4), done

    def _compare_results(self, expected: List[tuple], actual: List[tuple]) -> float:
        """Compare query results using row-level match ratio."""
        if not expected and not actual:
            return 1.0
        if not expected or not actual:
            return 0.0

        # Convert to sets of tuples for comparison
        # Normalize: convert to strings for robust comparison
        def normalize_row(row: tuple) -> tuple:
            return tuple(str(v).strip().lower() if v is not None else "" for v in row)

        expected_set = set(normalize_row(r) for r in expected)
        actual_set = set(normalize_row(r) for r in actual)

        if not expected_set:
            return 0.0

        # Calculate Jaccard-like match
        intersection = expected_set & actual_set
        union = expected_set | actual_set

        # Also check column count matches
        if expected and actual:
            if len(expected[0]) != len(actual[0]):
                return max(0.0, len(intersection) / len(union) * 0.5)  # Column mismatch penalty

        return len(intersection) / len(union) if union else 0.0
