"""
Tests for Task 37: Unified text+voice session support in /api/voice endpoint.

Validates:
1. RealtimeClient._response_text_delta forwards text deltas to frontend
2. RealtimeClient._response_text_done forwards completed text to frontend
3. RealtimeClient.receive_client handles "text" messages by creating conversation item + response
4. RealtimeClient.receive_client handles "modality_switch" messages
5. RealtimeClient.update_realtime_session defaults to text-only modalities
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from api.voice import RealtimeClient, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_realtime_client(is_ga_mode=False):
    """Create a RealtimeClient with mocked dependencies for testing."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_realtime.response = MagicMock()
    mock_realtime.response.create = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()
    mock_ws.receive_text = AsyncMock()
    mock_ws.close = AsyncMock()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )


# ---------------------------------------------------------------------------
# Test 1: _response_text_delta forwards text deltas to the frontend
# ---------------------------------------------------------------------------

class TestResponseTextDeltaForwarding:
    """When the realtime model sends text deltas (text-only mode),
    they should be forwarded to the frontend as assistant messages."""

    @pytest.mark.asyncio
    async def test_text_delta_sent_as_assistant_message(self):
        """_response_text_delta should send the delta text as an assistant message."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.delta = "Here are some capacitor options"

        await client._response_text_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant_delta"
        assert sent["payload"] == "Here are some capacitor options"

    @pytest.mark.asyncio
    async def test_text_delta_skips_none(self):
        """_response_text_delta should not send when delta is None."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.delta = None

        await client._response_text_delta(mock_event)
        client.client.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_delta_skips_empty_string(self):
        """_response_text_delta should not send when delta is empty string."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.delta = ""

        await client._response_text_delta(mock_event)
        client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: _response_text_done forwards completed text to the frontend
# ---------------------------------------------------------------------------

class TestResponseTextDoneForwarding:
    """When the realtime model finishes a text response,
    _response_text_done should forward it as an assistant message."""

    @pytest.mark.asyncio
    async def test_text_done_sent_as_assistant_message(self):
        """_response_text_done should send the full text as an assistant message."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.text = "I recommend the 100uF capacitor for that circuit."

        await client._response_text_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert sent["payload"] == "I recommend the 100uF capacitor for that circuit."

    @pytest.mark.asyncio
    async def test_text_done_skips_empty(self):
        """_response_text_done should not send when text is empty or None."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.text = None

        await client._response_text_done(mock_event)
        client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: receive_client handles "text" messages
# ---------------------------------------------------------------------------

class TestReceiveClientTextMessage:
    """When the frontend sends a text message through the voice WebSocket,
    receive_client should create a conversation item and trigger a response."""

    @pytest.mark.asyncio
    async def test_text_message_creates_conversation_item_and_response(self):
        """A 'text' message should send conversation.item.create then response.create."""
        client = _make_realtime_client()

        text_msg = json.dumps({"type": "text", "payload": "What resistors do you recommend?"})

        # Make receive_text return the text message once, then raise disconnect
        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[text_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have sent two events via realtime.send:
        # 1) conversation.item.create  2) response.create
        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) >= 2

        # First send should be the conversation item create
        first_send = send_calls[0][0][0]
        assert first_send.type == "conversation.item.create"
        assert first_send.item.type == "message"
        assert first_send.item.role == "user"
        assert first_send.item.content[0].type == "input_text"
        assert first_send.item.content[0].text == "What resistors do you recommend?"

        # Second send should be a response.create event
        second_send = send_calls[1][0][0]
        assert second_send.type == "response.create"


# ---------------------------------------------------------------------------
# Test 4: receive_client handles "modality_switch" messages
# ---------------------------------------------------------------------------

class TestReceiveClientModalitySwitch:
    """When the frontend sends a modality_switch message,
    the session should be updated with the new modalities."""

    @pytest.mark.asyncio
    async def test_modality_switch_to_text_only_preview(self):
        """Switching to text-only modality in preview mode should update the session."""
        client = _make_realtime_client(is_ga_mode=False)

        switch_msg = json.dumps({
            "type": "modality_switch",
            "payload": json.dumps({"modalities": ["text"]})
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[switch_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have sent a session.update event
        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.type == "session.update"
        assert sent_event.session.modalities == ["text"]

    @pytest.mark.asyncio
    async def test_modality_switch_to_text_audio_ga(self):
        """Switching to text+audio in GA mode should update session with output_modalities."""
        client = _make_realtime_client(is_ga_mode=True)

        switch_msg = json.dumps({
            "type": "modality_switch",
            "payload": json.dumps({"modalities": ["text", "audio"]})
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[switch_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have called session.update with the right modalities
        client.realtime.session.update.assert_called_once()
        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")
        assert session_dict["output_modalities"] == ["text", "audio"]


# ---------------------------------------------------------------------------
# Test 5: update_realtime_session defaults to text-only modalities
# ---------------------------------------------------------------------------

class TestSessionDefaultsTextOnly:
    """The initial session configuration should default to text-only modalities
    so the connection starts in text mode before the user enables their mic."""

    @pytest.mark.asyncio
    async def test_preview_defaults_to_text_only(self):
        """Preview mode should default to modalities=['text'] on initial setup."""
        client = _make_realtime_client(is_ga_mode=False)

        await client.update_realtime_session("Test instructions")

        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.session.modalities == ["text"]

    @pytest.mark.asyncio
    async def test_ga_defaults_to_text_only(self):
        """GA mode should default to output_modalities=['text'] on initial setup."""
        client = _make_realtime_client(is_ga_mode=True)

        await client.update_realtime_session("Test instructions")

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")
        assert session_dict["output_modalities"] == ["text"]
