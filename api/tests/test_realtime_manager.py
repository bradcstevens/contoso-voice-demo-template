"""
Tests for Task 35: Unified realtime connection manager.

Validates:
1. GA mode creates client with correct websocket_base_url (/openai/v1)
2. Preview mode creates client WITHOUT websocket_base_url override
3. Connection lifecycle: register, unregister, and track active connections
4. Chat context retrieval via SessionManager integration
5. Stale connection cleanup
"""

import os
import sys

# Set required env vars BEFORE importing modules that pull in the chat
# prompty loader (session -> chat -> prompty.load requires these).
# The global prompty.json config needs AZURE_OPENAI_ENDPOINT and
# AZURE_OPENAI_API_KEY; chat.prompty needs AZURE_OPENAI_DEPLOYMENT.
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-api-key")

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from realtime_manager import RealtimeConnectionManager
from session import SessionManager


# ---------------------------------------------------------------------------
# Test 1: GA mode creates client with websocket_base_url override
# ---------------------------------------------------------------------------

class TestGAClientFactory:
    """RealtimeConnectionManager should build AsyncAzureOpenAI with
    websocket_base_url = wss://{host}/openai/v1 for GA mode."""

    @patch("realtime_manager.AsyncAzureOpenAI")
    def test_ga_mode_creates_client_with_ws_base_url(self, mock_client_cls):
        """create_client() in GA mode should pass websocket_base_url."""
        manager = RealtimeConnectionManager(
            endpoint="https://my-resource.openai.azure.com",
            api_key="test-key",
            deployment="gpt-realtime",
            api_mode="ga",
        )

        manager.create_client()

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["websocket_base_url"] == "wss://my-resource.openai.azure.com/openai/v1"
        assert call_kwargs["azure_endpoint"] == "https://my-resource.openai.azure.com"
        assert call_kwargs["api_key"] == "test-key"

    @patch("realtime_manager.AsyncAzureOpenAI")
    def test_ga_mode_strips_trailing_slash(self, mock_client_cls):
        """Trailing slashes should be stripped before building the WS URL."""
        manager = RealtimeConnectionManager(
            endpoint="https://my-resource.openai.azure.com/",
            api_key="test-key",
            deployment="gpt-realtime",
            api_mode="ga",
        )

        manager.create_client()

        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["websocket_base_url"] == "wss://my-resource.openai.azure.com/openai/v1"


# ---------------------------------------------------------------------------
# Test 2: Preview mode creates client without websocket_base_url
# ---------------------------------------------------------------------------

class TestPreviewClientFactory:
    """RealtimeConnectionManager should build AsyncAzureOpenAI WITHOUT
    websocket_base_url for preview mode (SDK handles URL construction)."""

    @patch("realtime_manager.AsyncAzureOpenAI")
    def test_preview_mode_no_ws_base_url(self, mock_client_cls):
        """create_client() in preview mode should NOT pass websocket_base_url."""
        manager = RealtimeConnectionManager(
            endpoint="https://my-resource.openai.azure.com",
            api_key="test-key",
            deployment="gpt-realtime",
            api_mode="preview",
        )

        manager.create_client()

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert "websocket_base_url" not in call_kwargs
        assert call_kwargs["api_version"] == "2025-04-01-preview"


# ---------------------------------------------------------------------------
# Test 3: Connection lifecycle - register, unregister, track
# ---------------------------------------------------------------------------

class TestConnectionLifecycle:
    """RealtimeConnectionManager should track active connections per thread_id
    and support register/unregister operations."""

    def test_register_and_retrieve_connection(self):
        """Registering a connection makes it retrievable by thread_id."""
        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        mock_connection = MagicMock()
        manager.register_connection("thread-1", mock_connection)

        assert manager.get_connection("thread-1") is mock_connection

    def test_unregister_removes_connection(self):
        """Unregistering a connection removes it from tracking."""
        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        mock_connection = MagicMock()
        manager.register_connection("thread-1", mock_connection)
        manager.unregister_connection("thread-1")

        assert manager.get_connection("thread-1") is None

    def test_unregister_nonexistent_is_safe(self):
        """Unregistering a thread_id that doesn't exist should not raise."""
        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        # Should not raise
        manager.unregister_connection("nonexistent-thread")


# ---------------------------------------------------------------------------
# Test 4: Chat context retrieval via SessionManager integration
# ---------------------------------------------------------------------------

class TestSessionManagerIntegration:
    """RealtimeConnectionManager should retrieve and write back
    chat context for a thread_id via SessionManager."""

    @pytest.mark.asyncio
    async def test_get_chat_context_from_session(self):
        """get_chat_context should return context from an existing session."""
        SessionManager.sessions = {}

        ws = MagicMock()
        ws.client_state = "CONNECTED"
        ws.send_json = AsyncMock()
        session = await SessionManager.create_session("thread-ctx", ws)
        session.context.append("User asked about capacitors")
        session.context.append("Assistant explained ceramic vs electrolytic")

        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        context = manager.get_chat_context("thread-ctx")
        assert context == [
            "User asked about capacitors",
            "Assistant explained ceramic vs electrolytic",
        ]

    def test_get_chat_context_returns_empty_for_missing_session(self):
        """get_chat_context should return [] when no session exists."""
        SessionManager.sessions = {}

        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        context = manager.get_chat_context("nonexistent-thread")
        assert context == []

    @pytest.mark.asyncio
    async def test_write_voice_context_to_session(self):
        """write_voice_context should append context to an existing session."""
        SessionManager.sessions = {}

        ws = MagicMock()
        ws.client_state = "CONNECTED"
        ws.send_json = AsyncMock()
        session = await SessionManager.create_session("thread-wb2", ws)

        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        manager.write_voice_context("thread-wb2", "Voice: user asked about voltage regulators")
        assert "Voice: user asked about voltage regulators" in session.context


# ---------------------------------------------------------------------------
# Test 5: Stale connection cleanup
# ---------------------------------------------------------------------------

class TestStaleConnectionCleanup:
    """cleanup_stale_connections should remove connections whose
    underlying realtime client is closed."""

    def test_cleanup_removes_closed_connections(self):
        """Closed connections should be removed during cleanup."""
        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        # Active connection
        active_conn = MagicMock()
        active_conn.closed = False
        manager.register_connection("thread-active", active_conn)

        # Stale/closed connection
        stale_conn = MagicMock()
        stale_conn.closed = True
        manager.register_connection("thread-stale", stale_conn)

        manager.cleanup_stale_connections()

        assert manager.get_connection("thread-active") is active_conn
        assert manager.get_connection("thread-stale") is None

    def test_cleanup_with_no_connections_is_safe(self):
        """Cleanup with empty connections dict should not raise."""
        manager = RealtimeConnectionManager(
            endpoint="https://example.com",
            api_key="key",
            deployment="gpt-realtime",
        )

        # Should not raise
        manager.cleanup_stale_connections()
        assert len(manager._connections) == 0
