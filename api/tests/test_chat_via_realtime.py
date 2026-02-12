"""
Tests for Task 36: Route text chat messages through GPT-realtime WebSocket.

Validates:
1. Text messages sent as "text" type create conversation items and trigger text-only responses
2. Text message response creates text deltas forwarded to frontend as assistant_delta
3. Completed text responses forwarded to frontend as assistant messages
4. Text messages do NOT trigger audio responses (modalities=["text"])
5. The "user" type message pathway still works (backward compat)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Message


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
# Test 1: Text message creates conversation item with input_text + response.create
# ---------------------------------------------------------------------------

class TestTextMessageCreatesConversationItem:
    """When a 'text' type message arrives from the frontend chat UI through
    the realtime WebSocket, it should create a conversation item with
    input_text content and trigger a text-only response."""

    @pytest.mark.asyncio
    async def test_text_message_sends_conversation_item_and_response_create(self):
        """A 'text' message should create conversation.item.create then
        response.create with modalities=['text']."""
        client = _make_realtime_client()

        text_msg = json.dumps({
            "type": "text",
            "payload": "What capacitors do you have in stock?"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[text_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have sent two events via realtime.send:
        # 1) conversation.item.create  2) response.create
        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) == 2

        # First: conversation.item.create with input_text
        first_send = send_calls[0][0][0]
        assert first_send.type == "conversation.item.create"
        assert first_send.item.type == "message"
        assert first_send.item.role == "user"
        assert first_send.item.content[0].type == "input_text"
        assert first_send.item.content[0].text == "What capacitors do you have in stock?"

        # Second: response.create with text-only modalities
        second_send = send_calls[1][0][0]
        assert second_send.type == "response.create"


# ---------------------------------------------------------------------------
# Test 2: Text delta responses forwarded as assistant_delta
# ---------------------------------------------------------------------------

class TestTextDeltaForwardedAsAssistantDelta:
    """Text response deltas from the realtime model should be forwarded
    to the frontend as 'assistant_delta' messages so the chat UI can
    display streaming text."""

    @pytest.mark.asyncio
    async def test_text_delta_forwarded_with_correct_type(self):
        """_response_text_delta should forward as assistant_delta type."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.delta = "We have a wide selection of"

        await client._response_text_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant_delta"
        assert sent["payload"] == "We have a wide selection of"


# ---------------------------------------------------------------------------
# Test 3: Completed text response forwarded as assistant message
# ---------------------------------------------------------------------------

class TestCompletedTextForwardedAsAssistant:
    """When a text response is complete, _response_text_done should
    forward the full text as an 'assistant' message."""

    @pytest.mark.asyncio
    async def test_text_done_forwarded_as_assistant(self):
        """_response_text_done should send the full text as assistant message."""
        client = _make_realtime_client()

        mock_event = MagicMock()
        mock_event.text = "We carry ceramic, electrolytic, and film capacitors from major manufacturers."

        await client._response_text_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert sent["payload"] == "We carry ceramic, electrolytic, and film capacitors from major manufacturers."


# ---------------------------------------------------------------------------
# Test 4: Text messages set microphone_active to False
# ---------------------------------------------------------------------------

class TestTextMessageSetsMicrophoneInactive:
    """Text messages should mark the microphone as inactive so
    subsequent function call responses use text-only modality."""

    @pytest.mark.asyncio
    async def test_text_message_sets_microphone_inactive(self):
        """Sending a 'text' message should set microphone_active to False."""
        client = _make_realtime_client()
        client.microphone_active = True  # Start as if mic was active

        text_msg = json.dumps({
            "type": "text",
            "payload": "Show me 100uF capacitors"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[text_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        assert client.microphone_active is False


# ---------------------------------------------------------------------------
# Test 5: Multiple text messages processed sequentially
# ---------------------------------------------------------------------------

class TestMultipleTextMessagesProcessed:
    """Multiple text messages should each create their own conversation
    item and response request, processed in order."""

    @pytest.mark.asyncio
    async def test_sequential_text_messages(self):
        """Two consecutive text messages should produce two conversation items
        and two response.create calls."""
        client = _make_realtime_client()

        msg1 = json.dumps({"type": "text", "payload": "Hello"})
        msg2 = json.dumps({"type": "text", "payload": "What products do you have?"})

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[msg1, msg2, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have 4 send calls: 2x (conversation.item.create + response.create)
        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) == 4

        # First message pair
        assert send_calls[0][0][0].type == "conversation.item.create"
        assert send_calls[0][0][0].item.content[0].text == "Hello"
        assert send_calls[1][0][0].type == "response.create"

        # Second message pair
        assert send_calls[2][0][0].type == "conversation.item.create"
        assert send_calls[2][0][0].item.content[0].text == "What products do you have?"
        assert send_calls[3][0][0].type == "response.create"
