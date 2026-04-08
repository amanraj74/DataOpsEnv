"""
Task 1: Data Quality Audit (Easy)

The agent inspects a CSV dataset against a schema definition and must
identify data quality issues: null values, duplicate primary keys,
invalid data types, outliers, and foreign key violations.

Graded by F1 score comparing agent's found issues vs ground-truth manifest.
"""

import csv
import io
import json
import random
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Deterministic dataset + issue generation
# ──────────────────────────────────────────────────────────────────────

SCHEMA = {
    "table_name": "employees",
    "columns": {
        "employee_id": {"type": "integer", "primary_key": True, "nullable": False},
        "first_name": {"type": "string", "nullable": False, "max_length": 50},
        "last_name": {"type": "string", "nullable": False, "max_length": 50},
        "email": {"type": "string", "nullable": False, "unique": True},
        "department_id": {
            "type": "integer",
            "nullable": False,
            "foreign_key": {"table": "departments", "column": "dept_id"},
        },
        "salary": {"type": "float", "nullable": False, "min_value": 0, "max_value": 500000},
        "hire_date": {"type": "date", "nullable": False, "format": "YYYY-MM-DD"},
        "is_active": {"type": "boolean", "nullable": False},
        "age": {"type": "integer", "nullable": False, "min_value": 18, "max_value": 80},
        "performance_score": {
            "type": "float",
            "nullable": True,
            "min_value": 0.0,
            "max_value": 5.0,
        },
    },
}

VALID_DEPARTMENT_IDS = [101, 102, 103, 104, 105, 106, 107, 108]

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
    "Ivy", "Jack", "Karen", "Leo", "Mona", "Nick", "Olivia", "Paul",
    "Quinn", "Rita", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zach", "Aiden", "Beth", "Carl", "Donna", "Erik", "Fiona",
    "George", "Helen", "Ian", "Julia", "Kevin", "Laura", "Mark", "Nina",
    "Oscar", "Pam", "Ray", "Susan", "Tom", "Ursula", "Vince", "Wilma",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
]


def generate_dataset_and_manifest(seed: int = 42) -> Tuple[str, List[Dict[str, Any]]]:
    """Generate a deterministic CSV dataset with injected issues.

    Returns:
        Tuple of (csv_string, issues_manifest)
    """
    rng = random.Random(seed)
    rows = []
    issues = []

    # Generate 200 clean rows first
    used_emails = set()
    used_ids = set()

    for i in range(1, 201):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        dept = rng.choice(VALID_DEPARTMENT_IDS)
        salary = round(rng.uniform(30000, 200000), 2)
        year = rng.randint(2010, 2024)
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        hire_date = f"{year}-{month:02d}-{day:02d}"
        is_active = rng.choice(["true", "false"])
        age = rng.randint(22, 65)
        perf = round(rng.uniform(1.0, 5.0), 1) if rng.random() > 0.1 else ""

        rows.append({
            "employee_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": dept,
            "salary": salary,
            "hire_date": hire_date,
            "is_active": is_active,
            "age": age,
            "performance_score": perf,
        })
        used_emails.add(email)
        used_ids.add(i)

    # ── Inject NULL value issues (rows 201-210) ──
    null_positions = []
    for i in range(201, 211):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        dept = rng.choice(VALID_DEPARTMENT_IDS)
        salary = round(rng.uniform(30000, 200000), 2)
        hire_date = f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
        age = rng.randint(22, 65)

        row = {
            "employee_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": dept,
            "salary": salary,
            "hire_date": hire_date,
            "is_active": rng.choice(["true", "false"]),
            "age": age,
            "performance_score": round(rng.uniform(1.0, 5.0), 1),
        }

        # Null out a non-nullable field
        null_col = rng.choice(["first_name", "last_name", "email", "salary", "hire_date"])
        row[null_col] = ""
        issues.append({
            "issue_type": "null_value",
            "row": i,
            "column": null_col,
            "description": f"NULL value in non-nullable column '{null_col}' at row {i}",
        })
        rows.append(row)
        used_ids.add(i)

    # ── Inject DUPLICATE primary key issues (rows 211-215) ──
    for idx, dup_id in enumerate([3, 7, 15, 42, 100]):
        i = 211 + idx
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        row = {
            "employee_id": dup_id,  # Duplicate!
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": rng.choice(VALID_DEPARTMENT_IDS),
            "salary": round(rng.uniform(30000, 200000), 2),
            "hire_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "is_active": rng.choice(["true", "false"]),
            "age": rng.randint(22, 65),
            "performance_score": round(rng.uniform(1.0, 5.0), 1),
        }
        issues.append({
            "issue_type": "duplicate_primary_key",
            "row": len(rows) + 1,
            "column": "employee_id",
            "description": f"Duplicate primary key employee_id={dup_id} at row {len(rows) + 1}",
            "duplicate_value": dup_id,
        })
        rows.append(row)

    # ── Inject INVALID data type issues (rows 216-223) ──
    type_errors = [
        ("salary", "not_a_number"),
        ("salary", "abc"),
        ("age", "twenty-five"),
        ("age", "NaN"),
        ("department_id", "HR"),
        ("department_id", "null"),
        ("is_active", "maybe"),
        ("hire_date", "13/25/2023"),
    ]
    for idx, (col, bad_val) in enumerate(type_errors):
        i = 216 + idx
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        row = {
            "employee_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": rng.choice(VALID_DEPARTMENT_IDS),
            "salary": round(rng.uniform(30000, 200000), 2),
            "hire_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "is_active": rng.choice(["true", "false"]),
            "age": rng.randint(22, 65),
            "performance_score": round(rng.uniform(1.0, 5.0), 1),
        }
        row[col] = bad_val
        issues.append({
            "issue_type": "invalid_data_type",
            "row": len(rows) + 1,
            "column": col,
            "description": f"Invalid type for '{col}': '{bad_val}' at row {len(rows) + 1}",
            "invalid_value": str(bad_val),
        })
        rows.append(row)

    # ── Inject OUTLIER issues (rows 224-228) ──
    outlier_specs = [
        ("salary", -50000),
        ("salary", 15000000),
        ("age", 5),
        ("age", 150),
        ("performance_score", 99.9),
    ]
    for idx, (col, val) in enumerate(outlier_specs):
        i = 224 + idx
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        row = {
            "employee_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": rng.choice(VALID_DEPARTMENT_IDS),
            "salary": round(rng.uniform(30000, 200000), 2),
            "hire_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "is_active": rng.choice(["true", "false"]),
            "age": rng.randint(22, 65),
            "performance_score": round(rng.uniform(1.0, 5.0), 1),
        }
        row[col] = val
        issues.append({
            "issue_type": "outlier",
            "row": len(rows) + 1,
            "column": col,
            "description": f"Value {val} out of range for '{col}' at row {len(rows) + 1}",
            "outlier_value": val,
        })
        rows.append(row)

    # ── Inject FOREIGN KEY violation issues (rows 229-235) ──
    invalid_depts = [999, 000, 500, 201, 302, 777, 888]
    for idx, bad_dept in enumerate(invalid_depts):
        i = 229 + idx
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@company.com"
        row = {
            "employee_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department_id": bad_dept,
            "salary": round(rng.uniform(30000, 200000), 2),
            "hire_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "is_active": rng.choice(["true", "false"]),
            "age": rng.randint(22, 65),
            "performance_score": round(rng.uniform(1.0, 5.0), 1),
        }
        issues.append({
            "issue_type": "foreign_key_violation",
            "row": len(rows) + 1,
            "column": "department_id",
            "description": f"department_id={bad_dept} not in departments table at row {len(rows) + 1}",
            "invalid_reference": bad_dept,
        })
        rows.append(row)

    # ── Shuffle rows deterministically ──
    rng.shuffle(rows)

    # Build CSV string
    fieldnames = list(SCHEMA["columns"].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return output.getvalue(), issues


class AuditTask:
    """Manages the data quality audit task state and grading."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.csv_data, self.ground_truth_issues = generate_dataset_and_manifest(seed)
        self.submitted = False
        self.score = 0.0
        self.max_steps = 5

    def get_initial_observation(self) -> Dict[str, Any]:
        """Return the initial task observation."""
        # Show first 30 rows as preview
        lines = self.csv_data.strip().split("\n")
        preview = "\n".join(lines[:31])  # header + 30 rows

        return {
            "task_type": "data_quality_audit",
            "task_description": (
                "You are a data engineer. Inspect the employee dataset for data quality issues.\n"
                "Find ALL issues: null values in non-nullable columns, duplicate primary keys,\n"
                "invalid data types, outlier values outside allowed ranges, and foreign key violations.\n"
                "The valid department IDs are: 101, 102, 103, 104, 105, 106, 107, 108.\n\n"
                "Submit your findings using action_type='submit_report' with payload containing\n"
                "'issues': a list of objects with keys: issue_type, row (optional), column, description.\n"
                "Valid issue_types: null_value, duplicate_primary_key, invalid_data_type, outlier, foreign_key_violation."
            ),
            "data_preview": preview,
            "full_data": self.csv_data,
            "schema_info": SCHEMA,
            "steps_remaining": self.max_steps,
            "current_score": 0.0,
        }

    def process_action(self, action_type: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool]:
        """Process an agent action and return (obs_update, reward, done).

        Returns:
            Tuple of (observation_dict, reward, done)
        """
        if action_type == "submit_report":
            return self._grade_report(payload)
        else:
            return (
                {
                    "error_message": f"Invalid action_type '{action_type}' for audit task. Use 'submit_report'.",
                    "action_feedback": "Invalid action. Use action_type='submit_report' with payload.issues list.",
                },
                -0.05,
                False,
            )

    def _grade_report(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool]:
        """Grade the submitted audit report using multi-tier F1 score.

        Scoring tiers:
          - Type-only (20%): Did the agent identify the correct issue types?
          - Type+Column (40%): Did the agent identify the correct (type, column) pairs?
          - Type+Column+Row (40%): Did the agent find the exact issue locations?

        This ensures partial credit even when agents don't specify exact rows.
        """
        submitted_issues = payload.get("issues", [])
        if not isinstance(submitted_issues, list):
            return (
                {"error_message": "payload.issues must be a list", "action_feedback": "Invalid format."},
                -0.05,
                False,
            )

        self.submitted = True

        def f1(tp, fp, fn):
            if tp == 0:
                return 0.0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            if precision + recall == 0:
                return 0.0
            return 2 * precision * recall / (precision + recall)

        # ── Tier 1: Type-only matching (20%) ──
        gt_types = set(issue["issue_type"] for issue in self.ground_truth_issues)
        sub_types = set(issue.get("issue_type", "") for issue in submitted_issues if issue.get("issue_type"))
        type_f1 = f1(len(gt_types & sub_types), len(sub_types - gt_types), len(gt_types - sub_types))

        # ── Tier 2: Type+Column matching (40%) ──
        gt_type_col = set()
        for issue in self.ground_truth_issues:
            gt_type_col.add((issue["issue_type"], issue["column"]))

        sub_type_col = set()
        for issue in submitted_issues:
            it = issue.get("issue_type", "")
            col = issue.get("column", "")
            if it and col:
                sub_type_col.add((it, col))

        tp_coarse = len(gt_type_col & sub_type_col)
        fp_coarse = len(sub_type_col - gt_type_col)
        fn_coarse = len(gt_type_col - sub_type_col)
        coarse_f1 = f1(tp_coarse, fp_coarse, fn_coarse)

        # ── Tier 3: Type+Column+Row matching (40%) ──
        gt_detailed = set()
        for issue in self.ground_truth_issues:
            key = (issue["issue_type"], str(issue.get("row", "")), issue["column"])
            gt_detailed.add(key)

        sub_detailed = set()
        has_row_numbers = False
        for issue in submitted_issues:
            row_val = issue.get("row")
            if row_val is not None and str(row_val) != "":
                has_row_numbers = True
            key = (
                issue.get("issue_type", ""),
                str(row_val) if row_val is not None else "",
                issue.get("column", ""),
            )
            if key[0] and key[2]:
                sub_detailed.add(key)

        tp_fine = len(gt_detailed & sub_detailed)
        fp_fine = len(sub_detailed - gt_detailed)
        fn_fine = len(gt_detailed - sub_detailed)
        fine_f1 = f1(tp_fine, fp_fine, fn_fine)

        # ── Blend tiers (adjust weights if agent doesn't provide rows) ──
        if has_row_numbers:
            score = 0.2 * type_f1 + 0.4 * coarse_f1 + 0.4 * fine_f1
        else:
            # If no row numbers provided, weight coarse tiers higher
            score = 0.35 * type_f1 + 0.65 * coarse_f1

        # Penalty for hallucinated type+column issues
        hallucination_penalty = min(0.05 * fp_coarse, 0.2)
        score = max(0.0, score - hallucination_penalty)

        self.score = round(score, 4)

        obs = {
            "action_feedback": (
                f"Report graded. Type F1: {type_f1:.2f}, Coarse F1: {coarse_f1:.2f}, "
                f"Fine F1: {fine_f1:.2f}. "
                f"Type+Col matches: {tp_coarse}, False positives: {fp_coarse}, "
                f"Missed: {fn_coarse}. Final score: {self.score:.2f}"
            ),
            "current_score": self.score,
        }

        return obs, self.score, True
