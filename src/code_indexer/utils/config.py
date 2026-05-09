"""Configuration management for the code indexer."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


"""Configuration management for the code indexer."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(default="sqlite:///code_indexer.db")

    # Logging
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default=None)

    # Scanner
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [".git", "__pycache__", "*.pyc", "node_modules", ".venv"]
    )
    max_file_size_mb: int = Field(default=10)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Development
    debug: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
    )

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Get the data directory."""
        return self.project_root / "data"

    @property
    def logs_dir(self) -> Path:
        """Get the logs directory."""
        return self.project_root / "logs"


# Global settings instance
settings = Settings()