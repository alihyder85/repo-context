"""Basic tests for the code indexer."""

import pytest

from code_indexer.utils.config import settings


def test_settings_loaded():
    """Test that settings are loaded correctly."""
    assert settings.database_url is not None
    assert settings.log_level == "INFO"
    assert isinstance(settings.ignore_patterns, list)


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health endpoint."""
    from code_indexer.api.routes.health import health_check

    result = await health_check()
    assert result == {"status": "healthy"}