"""FastAPI application for the code indexer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from code_indexer.api.routes import health
from code_indexer.api.routes import symbols as symbols_router
from code_indexer.api.routes import files as files_router
from code_indexer.utils.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Code Indexer API",
        description="AI Code Indexing & Token Optimization System API",
        version="0.1.0",
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(symbols_router.router, prefix=prefix, tags=["symbols"])
    app.include_router(files_router.router, prefix=prefix, tags=["files"])

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Code Indexer API", "version": "0.1.0"}

    return app
