"""
DataOps Environment HTTP Client.

This client connects to the DataOps environment server over HTTP
and provides methods to interact with the environment remotely.

Usage:
    client = DataOpsClient("http://localhost:7860")
    obs = client.reset(task_type="data_quality_audit")
    obs = client.step({"action_type": "submit_report", "payload": {...}})
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

try:
    from .models import DataOpsAction, DataOpsObservation
except ImportError:
    from models import DataOpsAction, DataOpsObservation


@dataclass
class StepResult:
    """Result from a single environment step."""
    observation: Dict[str, Any]
    reward: Optional[float] = None
    done: bool = False


class DataOpsClient:
    """HTTP client for the DataOps environment."""

    def __init__(self, base_url: str, timeout_s: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> "DataOpsClient":
        self._ensure_client()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def health(self) -> Dict[str, Any]:
        """Check if the server is healthy."""
        client = self._ensure_client()
        response = client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def reset(self, **kwargs: Any) -> StepResult:
        """Reset the environment with optional parameters."""
        client = self._ensure_client()
        response = client.post(
            f"{self.base_url}/reset",
            json=kwargs if kwargs else None,
        )
        response.raise_for_status()
        data = response.json()
        obs = data.get("observation", data)
        return StepResult(
            observation=obs,
            reward=data.get("reward"),
            done=data.get("done", False),
        )

    def step(self, action: Dict[str, Any] | DataOpsAction) -> StepResult:
        """Execute an action in the environment."""
        if isinstance(action, DataOpsAction):
            action_payload = action.model_dump(exclude_none=True)
        else:
            action_payload = action

        client = self._ensure_client()
        response = client.post(
            f"{self.base_url}/step",
            json=action_payload,
        )
        response.raise_for_status()
        data = response.json()
        obs = data.get("observation", data)
        return StepResult(
            observation=obs,
            reward=data.get("reward"),
            done=data.get("done", False),
        )

    def state(self) -> Dict[str, Any]:
        """Get the current environment state."""
        client = self._ensure_client()
        response = client.get(f"{self.base_url}/state")
        response.raise_for_status()
        return response.json()

    def schema(self) -> Dict[str, Any]:
        """Get the action/observation schemas."""
        client = self._ensure_client()
        response = client.get(f"{self.base_url}/schema")
        response.raise_for_status()
        return response.json()


def main():
    """Quick smoke test against a running server."""
    import argparse

    parser = argparse.ArgumentParser(description="DataOps Environment Client")
    parser.add_argument(
        "--url",
        default="http://localhost:7860",
        help="Server URL",
    )
    args = parser.parse_args()

    with DataOpsClient(args.url) as client:
        # Health check
        health = client.health()
        print(f"Health: {health}")

        # Reset
        result = client.reset(task_type="data_quality_audit")
        print(f"Reset done={result.done}")
        print(f"Task: {result.observation.get('task_type', 'unknown')}")

        # Step with an empty report
        result = client.step({
            "action_type": "submit_report",
            "payload": {"issues": []},
        })
        print(f"Step done={result.done}, reward={result.reward}")


if __name__ == "__main__":
    main()
