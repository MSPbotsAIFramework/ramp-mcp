"""Process entrypoint: uvicorn serving /health and the MCP app."""

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from ramp_mcp.config import get_settings
from ramp_mcp.server import RampCredentialsMiddleware, build_mcp


async def _health(_request: Request) -> JSONResponse:
    # Pure local probe -- never calls Ramp (SOP SS1.1).
    return JSONResponse({"status": "ok"})


def build_app() -> Starlette:
    mcp = build_mcp()
    mcp_app = mcp.streamable_http_app()
    app = Starlette(
        routes=[
            Route("/health", _health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        # Mount() alone does not run a mounted sub-app's lifespan; without
        # this, /mcp fails with "Task group is not initialized" while
        # /health keeps returning 200 (SOP SS7 known pitfall).
        lifespan=mcp_app.router.lifespan_context,
    )
    return RampCredentialsMiddleware(app)


def run() -> None:
    settings = get_settings()
    uvicorn.run(build_app(), host=settings.mcp_http_host, port=settings.mcp_http_port)


if __name__ == "__main__":
    run()
