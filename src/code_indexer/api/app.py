"""FastAPI application for the code indexer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from code_indexer.api.routes import health
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

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "Code Indexer API", "version": "0.1.0"}

    return app