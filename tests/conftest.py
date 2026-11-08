"""Shared test setup."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.senec_local.api import _flatten

REPLY = json.loads((Path(__file__).parent / "fixture_reply.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def reply() -> dict:
    """A real reply of the unit (recorded 2026-11-08), decoded."""
    return _flatten(json.loads(json.dumps(REPLY)))


@pytest.fixture
def mock_client(reply):
    with patch(
        "custom_components.senec_local.api.SenecClient.async_get_data",
        return_value=reply,
    ) as mock:
        yield mock
