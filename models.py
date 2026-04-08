"""
Data models for the DataOps Environment.

Defines the Action and Observation Pydantic models for the DataOps benchmark
environment that evaluates AI agents on data engineering tasks.
"""

from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class DataOpsAction(Action):
    """Action for the DataOps environment.

    The agent submits actions to interact with the environment:
    - submit_report: Submit data quality audit findings
    - submit_fix: Submit a fixed SQL query
    - patch_model: Patch a SQL model in the pipeline
    - submit_final: Finalize the pipeline fix submission
    """

    action_type: str = Field(
        ...,
        description="Type of action: submit_report | submit_fix | patch_model | submit_final",
    )
    task_id: str = Field(
        default="",
        description="Identifier for the current task",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action payload - contents depend on action_type",
    )


class DataOpsObservation(Observation):
    """Observation from the DataOps environment.

    Provides the agent with context about the current task state:
    - Task type and description
    - Data preview (CSV rows, SQL queries, logs)
    - Schema definitions
    - Error messages and feedback
    - Progress tracking
    """

    task_type: str = Field(
        default="",
        description="Current task: data_quality_audit | sql_bug_fix | pipeline_debug",
    )
    task_description: str = Field(
        default="",
        description="Human-readable description of the current task objective",
    )
    data_preview: Optional[str] = Field(
        default=None,
        description="Preview of the dataset (first N rows as CSV text)",
    )
    sql_query: Optional[str] = Field(
        default=None,
        description="SQL query to fix or inspect",
    )
    pipeline_models: Optional[Dict[str, str]] = Field(
        default=None,
        description="Pipeline SQL models: {model_name: sql_code}",
    )
    schema_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Database/dataset schema definitions",
    )
    logs: Optional[str] = Field(
        default=None,
        description="Pipeline execution logs or error traces",
    )
    dependency_graph: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Pipeline model dependency graph: {model: [dependencies]}",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message from the last action, null if no error",
    )
    steps_remaining: int = Field(
        default=10,
        description="Number of steps remaining before episode ends",
    )
    current_score: float = Field(
        default=0.0,
        description="Running cumulative score for the current episode [0.0-1.0]",
    )
    action_feedback: Optional[str] = Field(
        default=None,
        description="Feedback from the last action taken",
    )
