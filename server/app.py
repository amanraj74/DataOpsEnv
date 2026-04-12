"""
FastAPI application for the DataOps Environment.

This module creates an HTTP server that exposes the DataOpsEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - GET  /        : Environment info (landing page)
    - GET  /health  : Health check
    - POST /reset   : Reset the environment
    - POST /step    : Execute an action
    - GET  /state   : Get current environment state
    - GET  /schema  : Get action/observation schemas
    - WS   /ws      : WebSocket endpoint for persistent sessions
"""

import os

try:
    from openenv.core.env_server.http_server import create_app
except ImportError as e:
    raise ImportError(
        "openenv-core is required. Install with: pip install openenv-core"
    ) from e

try:
    from ..models import DataOpsAction, DataOpsObservation
    from .dataops_environment import DataOpsEnvironment
except ImportError:
    from models import DataOpsAction, DataOpsObservation
    from server.dataops_environment import DataOpsEnvironment


# Create the app with OpenEnv HTTP server infrastructure
app = create_app(
    DataOpsEnvironment,
    DataOpsAction,
    DataOpsObservation,
    env_name="dataops_env",
    max_concurrent_envs=1,
)


@app.get("/")
def root():
    """Landing page - confirms the environment is alive."""
    return {
        "name": "dataops_env",
        "version": "1.0.0",
        "status": "running",
        "description": "AI Data Engineering Agent Benchmark",
        "endpoints": {
            "health": "/health",
            "reset": "/reset",
            "step": "/step",
            "state": "/state",
            "schema": "/schema",
            "docs": "/docs",
        },
        "tasks": [
            "data_quality_audit",
            "sql_bug_fix",
            "pipeline_debug",
        ],
    }


@app.get("/health")
def health_check():
    """Health check endpoint for Docker/HF Spaces."""
    return {"status": "healthy"}


def main(host: str = "0.0.0.0", port: int = None):
    """Entry point for direct execution."""
    import uvicorn

    if port is None:
        port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()