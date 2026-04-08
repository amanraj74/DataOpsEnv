"""
FastAPI application for the DataOps Environment.

This module creates an HTTP server that exposes the DataOpsEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

try:
    from openenv.core.env_server.http_server import create_app
except ImportError as e:
    raise ImportError(
        "openenv-core is required. Install with: pip install openenv-core[core]"
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

@app.get("/health")
def health_check():
    return {"status": "healthy"}


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct execution.

    Usage:
        python -m server.app
        python -m server.app --port 8001
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

