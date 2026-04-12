"""
DataOps Environment Implementation.

A production-grade OpenEnv benchmark environment that evaluates AI agents
on real-world data engineering tasks with deterministic grading and dense
reward signals.

Three tasks with increasing difficulty:
  1. Data Quality Audit (Easy)  detect issues in a dataset
  2. SQL Bug Fix (Medium)  fix broken SQL queries
  3. Pipeline Debug (Hard)  debug a multi-step data pipeline
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import DataOpsAction, DataOpsObservation
except ImportError:
    from models import DataOpsAction, DataOpsObservation

from server.tasks.task_audit import AuditTask
from server.tasks.task_sql_fix import SqlFixTask
from server.tasks.task_pipeline import PipelineTask


TASK_TYPES = ["data_quality_audit", "sql_bug_fix", "pipeline_debug"]


class DataOpsEnvironment(Environment):
    """
    DataOps Environment  AI Data Engineering Agent Benchmark.

    Simulates real-world data engineering workflows where agents must:
    - Audit data quality in datasets
    - Fix broken SQL queries
    - Debug multi-step data pipelines

    Provides dense reward signals, partial credit, and deterministic grading.

    Example:
        >>> env = DataOpsEnvironment()
        >>> obs = env.reset(task_type="data_quality_audit")
        >>> print(obs.task_type)  # "data_quality_audit"
        >>>
        >>> obs = env.step(DataOpsAction(
        ...     action_type="submit_report",
        ...     payload={"issues": [...]}
        ... ))
        >>> print(obs.reward)  # Graded F1 score
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(self):
        """Initialize the DataOps environment."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0
        self._task = None
        self._task_type = ""
        self._steps_remaining = 0
        self._total_reward = 0.0
        self._rewards: List[float] = []
        self._done = False
        self._seed = 42

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> DataOpsObservation:
        """
        Reset the environment with a specific task.

        Args:
            seed: Random seed for deterministic episodes (default: 42)
            episode_id: Optional custom episode ID
            **kwargs: Additional options, including:
                - task_type: One of 'data_quality_audit', 'sql_bug_fix', 'pipeline_debug'

        Returns:
            DataOpsObservation with the initial task state
        """
        self._seed = seed if seed is not None else 42
        self._state = State(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
        )
        self._reset_count += 1
        self._total_reward = 0.0
        self._rewards = []
        self._done = False

        # Determine task type
        task_type = kwargs.get("task_type", "data_quality_audit")
        if task_type not in TASK_TYPES:
            task_type = "data_quality_audit"

        self._task_type = task_type

        # Initialize the task
        if task_type == "data_quality_audit":
            self._task = AuditTask(seed=self._seed)
        elif task_type == "sql_bug_fix":
            self._task = SqlFixTask(seed=self._seed)
        elif task_type == "pipeline_debug":
            self._task = PipelineTask(seed=self._seed)

        self._steps_remaining = self._task.max_steps

        # Get initial observation from the task
        initial_obs = self._task.get_initial_observation()

        return DataOpsObservation(
            task_type=initial_obs.get("task_type", task_type),
            task_description=initial_obs.get("task_description", ""),
            data_preview=initial_obs.get("data_preview") or initial_obs.get("full_data"),
            sql_query=initial_obs.get("sql_query"),
            pipeline_models=initial_obs.get("pipeline_models"),
            schema_info=initial_obs.get("schema_info", {}),
            logs=initial_obs.get("logs"),
            dependency_graph=initial_obs.get("dependency_graph"),
            error_message=None,
            steps_remaining=self._steps_remaining,
            current_score=0.0,
            action_feedback=None,
            done=False,
            reward=0.0,
        )

    def step(self, action: DataOpsAction) -> DataOpsObservation:  # type: ignore[override]
        """
        Execute a step in the environment.

        Args:
            action: DataOpsAction with action_type and payload

        Returns:
            DataOpsObservation with updated state, reward, and feedback
        """
        self._state.step_count += 1
        self._steps_remaining -= 1

        # Check if already done
        if self._done:
            return DataOpsObservation(
                task_type=self._task_type,
                task_description="Episode is already complete.",
                error_message="Episode already done. Call reset() to start a new one.",
                steps_remaining=0,
                current_score=self._total_reward,
                done=True,
                reward=0.0,
            )

        # Check if out of steps
        if self._steps_remaining < 0:
            self._done = True
            return DataOpsObservation(
                task_type=self._task_type,
                task_description="No steps remaining.",
                error_message="Out of steps. Episode ended.",
                steps_remaining=0,
                current_score=self._total_reward,
                done=True,
                reward=-0.1,
            )

        # Route to the current task
        if self._task is None:
            return DataOpsObservation(
                error_message="No task initialized. Call reset() first.",
                done=True,
                reward=0.0,
            )

        # Process the action
        obs_update, reward, done = self._task.process_action(
            action.action_type,
            action.payload or {},
        )

        # Track rewards
        reward = round(reward, 4)
        self._rewards.append(reward)
        self._total_reward = round(
            obs_update.get("current_score", self._total_reward),
            4
        )
        self._done = done

        # Build observation
        return DataOpsObservation(
            task_type=self._task_type,
            task_description=obs_update.get("task_description", ""),
            data_preview=obs_update.get("data_preview"),
            sql_query=obs_update.get("sql_query"),
            pipeline_models=obs_update.get("pipeline_models"),
            schema_info=obs_update.get("schema_info", {}),
            logs=obs_update.get("logs"),
            dependency_graph=obs_update.get("dependency_graph"),
            error_message=obs_update.get("error_message"),
            steps_remaining=max(0, self._steps_remaining),
            current_score=self._total_reward,
            action_feedback=obs_update.get("action_feedback"),
            done=done,
            reward=reward,
        )

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return self._state
