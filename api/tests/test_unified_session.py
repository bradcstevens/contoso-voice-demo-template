"""
Tests for Task 37: Unified text+voice session management.

Validates:
1. ChatSession supports detach_client/detach_voice for lifecycle management
2. Voice context writeback to shared session
3. RealtimeClient tracks microphone_active state for modality switching
4. RealtimeClient handles "text" messages for text-only responses
5. SessionManager preserves session across chat disconnect for voice reuse
"""

import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session import ChatSession, SessionManager
from voice import RealtimeClient, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket with configurable state."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_realtime_client(is_ga_mode=False):
    """Create a RealtimeClient with mocked dependencies."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_realtime.response = MagicMock()
    mock_realtime.response.create = AsyncMock()
    mock_ws = _make_mock_websocket()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )


# ---------------------------------------------------------------------------
# Test 1: ChatSession detach_client preserves context in SessionManager
# ---------------------------------------------------------------------------

class TestSessionLifecycleManagement:
    """ChatSession.detach_client() should null the WebSocket without
    destroying the session, so context survives for voice reuse."""

    @pytest.mark.asyncio
    async def test_detach_client_preserves_context(self):
        """After detach_client, session remains in SessionManager with context."""
        SessionManager.sessions = {}

        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-1", ws)
        session.context.append("User asked about resistors")
        session.context.append("Assistant recommended 10k ohm")

        # Detach the WebSocket (simulates chat disconnect)
        session.detach_client()

        # Session still in manager with context intact
        retrieved = SessionManager.get_session("thread-1")
        assert retrieved is not None
        assert len(retrieved.context) == 2
        assert retrieved.context[0] == "User asked about resistors"
        assert retrieved.client is None


# ---------------------------------------------------------------------------
# Test 2: ChatSession voice context writeback
# ---------------------------------------------------------------------------

class TestVoiceContextWriteback:
    """ChatSession.add_voice_context() appends voice transcript context
    so future chat/voice interactions have full history."""

    @pytest.mark.asyncio
    async def test_add_voice_context(self):
        """Voice context is appended to session context list."""
        SessionManager.sessions = {}

        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-wb", ws)
        session.context.append("Chat: user asked about LEDs")

        session.add_voice_context("Voice: user asked about LED brightness specs")

        assert len(session.context) == 2
        assert "Voice: user asked about LED brightness specs" in session.context


# ---------------------------------------------------------------------------
# Test 3: ChatSession.detach_voice nulls realtime without closing session
# ---------------------------------------------------------------------------

class TestVoiceDetachment:
    """ChatSession.detach_voice() clears the realtime client reference
    without closing the whole session."""

    @pytest.mark.asyncio
    async def test_detach_voice_keeps_session_alive(self):
        """After voice detaches, session is not closed if chat client active."""
        SessionManager.sessions = {}

        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-rt", ws)

        mock_realtime = MagicMock()
        mock_realtime.closed = False
        session.add_realtime(mock_realtime)

        session.detach_voice()
        assert session.realtime is None
        assert session.is_closed() is False


# ---------------------------------------------------------------------------
# Test 4: RealtimeClient tracks microphone_active state
# ---------------------------------------------------------------------------

class TestRealtimeClientMicrophoneState:
    """RealtimeClient should have a microphone_active attribute
    for dynamic modality switching between text and audio."""

    def test_microphone_active_defaults_false(self):
        """microphone_active should default to False."""
        client = _make_realtime_client()
        assert client.microphone_active is False

    def test_microphone_active_can_be_toggled(self):
        """microphone_active should be settable."""
        client = _make_realtime_client()
        client.microphone_active = True
        assert client.microphone_active is True
        client.microphone_active = False
        assert client.microphone_active is False


# ---------------------------------------------------------------------------
# Test 5: RealtimeClient._response_text_delta sends text to frontend
# ---------------------------------------------------------------------------

class TestResponseTextDeltaForwarding:
    """When operating in text-only mode, _response_text_delta should
    forward text deltas to the frontend client."""

    @pytest.mark.asyncio
    async def test_response_text_delta_sends_message(self):
        """_response_text_delta should send text delta as assistant message."""
        client = _make_realtime_client()

        # Create a mock event with a delta attribute
        mock_event = MagicMock()
        mock_event.delta = "Here are some resistor options"

        await client._response_text_delta(mock_event)

        # Should have sent an assistant message to the client
        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant_delta"
        assert sent["payload"] == "Here are some resistor options"

    @pytest.mark.asyncio
    async def test_response_text_delta_skips_empty(self):
        """_response_text_delta should not send when delta is empty/None."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.delta = None

        await client._response_text_delta(mock_event)

        client.client.send_json.assert_not_called()
