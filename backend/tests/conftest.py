"""
GARL Protocol v1.0 — pytest configuration and shared fixtures.

Environment variables are set for test environment and Supabase mock is provided.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Test environment variables — must be set before conftest is imported
os.environ["SUPABASE_URL"] = "test"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test"
os.environ["SIGNING_PRIVATE_KEY_HEX"] = (
    "d4333c39a62efc8073ce4a46974d719d688d7baeba825825f99a75fdf4512ee9"
)
os.environ["DEBUG"] = "true"


@pytest.fixture
def mock_supabase():
    """
    Fixture that mocks the get_supabase function.
    Returns MagicMock instead of Supabase client.
    """
    mock_client = MagicMock()
    with patch("app.core.supabase_client.get_supabase", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_supabase_for_routes():
    """
    get_supabase mock for route tests.
    Mocks get_supabase used in agents, traces, and routes modules.
    """
    mock_client = MagicMock()

    # Table mocks — chainable .select().eq().execute() chain
    def table_side_effect(table_name):
        mock_table = MagicMock()
        mock_res = MagicMock()
        mock_res.data = []
        mock_res.count = 0
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.in_.return_value = mock_table
        mock_table.or_.return_value = mock_table
        mock_table.gt.return_value = mock_table
        mock_table.execute.return_value = mock_res
        return mock_table

    mock_client.table.side_effect = table_side_effect

    # Mock all get_supabase usages (in their imported namespaces)
    with patch("app.core.supabase_client.get_supabase", return_value=mock_client):
        with patch("app.services.agents.get_supabase", return_value=mock_client):
            with patch("app.services.traces.get_supabase", return_value=mock_client):
                with patch("app.api.routes._get_supabase", return_value=mock_client):
                    yield mock_client
