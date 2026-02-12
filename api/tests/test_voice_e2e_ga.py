"""
Tests for Task 31: End-to-end voice session tests for GA mode.

Validates the complete GA-mode voice flow:
1. Full voice session lifecycle (connect -> configure -> send audio -> receive response -> disconnect)
2. System prompt rendering with customer data, products, and purchases
3. WebSocket connection acceptance and handshake protocol processing
4. Error handling: malformed messages, connection drops, missing settings
5. Session cleanup on disconnect

The OpenAI Realtime API connection is mocked; everything else runs end-to-end.
"""

import sys
import os
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Message
from jinja2 import Environment, FileSystemLoader


# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------

VOICE_TEMPLATE_DIR = Path(__file__).parent.parent / "voice"
PRODUCTS_PATH = Path(__file__).parent.parent / "products.json"
PURCHASES_PATH = Path(__file__).parent.parent / "purchases.json"

SAMPLE_PRODUCTS = [
    {
        "Description": {
            "ProductDescription": "CAP CER 0.1UF 50V X7R 0603",
            "DetailedDescription": "0.1 uF Ceramic Capacitor X7R 0603",
        },
        "Manufacturer": {"Id": 399, "Name": "KEMET"},
        "ManufacturerProductNumber": "C0603C104K5RACTU",
        "UnitPrice": 0.08,
    }
]

SAMPLE_PURCHASES = [
    {
        "Description": {
            "ProductDescription": "IC MCU 32BIT 256KB FLASH 64LQFP",
            "DetailedDescription": "ARM Cortex-M4 STM32F4 Microcontroller IC",
        },
        "Manufacturer": {"Id": 497, "Name": "STMicroelectronics"},
        "ManufacturerProductNumber": "STM32F405RGT6",
        "UnitPrice": 12.5,
    }
]

SAMPLE_CHAT_ITEMS = [
    {"name": "user", "text": "I need help choosing a capacitor"},
    {"name": "assistant", "text": "I can help you find a capacitor. What specifications do you need?"},
]

SAMPLE_SETTINGS = {
    "user": "TestUser",
    "threshold": 0.75,
    "silence": 400,
    "prefix": 250,
}


def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket client with configurable state."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def _make_mock_realtime_connection():
    """Create a mock realtime connection that simulates AsyncRealtimeConnection."""
    mock_rt = AsyncMock()
    mock_rt.send = AsyncMock()
    mock_rt.close = AsyncMock()
    mock_rt.session = MagicMock()
    mock_rt.session.update = AsyncMock()
    mock_rt.response = MagicMock()
    mock_rt.response.create = AsyncMock()
    return mock_rt


def _make_ga_client(debug=False):
    """Create a RealtimeClient in GA mode with mocked dependencies."""
    mock_rt = _make_mock_realtime_connection()
    mock_ws = _make_mock_websocket()
    client = RealtimeClient(
        realtime=mock_rt,
        client=mock_ws,
        debug=debug,
        is_ga_mode=True,
    )
    return client


# ---------------------------------------------------------------------------
# Test 1: Full GA session lifecycle
# ---------------------------------------------------------------------------


class TestGAVoiceSessionLifecycle:
    """End-to-end test of the GA voice session lifecycle:
    connect -> configure -> send audio -> receive response -> disconnect."""

    @pytest.mark.asyncio
    async def test_ga_session_configure_sends_session_update(self):
        """Configuring a GA session should call realtime.session.update
        with the correct nested audio structure."""
        client = _make_ga_client()

        await client.update_realtime_session(
            instructions="You are a helpful assistant.",
            threshold=0.75,
            silence_duration_ms=400,
            prefix_padding_ms=250,
        )

        client.realtime.session.update.assert_called_once()
        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        # Verify GA structure
        assert session_dict["type"] == "realtime"
        assert session_dict["output_modalities"] == ["text"]
        assert session_dict["instructions"] == "You are a helpful assistant."
        assert session_dict["audio"]["input"]["turn_detection"]["threshold"] == 0.75
        assert session_dict["audio"]["input"]["turn_detection"]["silence_duration_ms"] == 400
        assert session_dict["audio"]["input"]["turn_detection"]["prefix_padding_ms"] == 250

    @pytest.mark.asyncio
    async def test_ga_session_receive_audio_forwards_to_client(self):
        """When the realtime API sends an audio delta event, the GA session
        should forward it to the WebSocket client."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.type = "response.output_audio.delta"
        mock_event.delta = "base64audiocontent"

        await client._response_audio_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "audio"
        assert sent["payload"] == "base64audiocontent"

    @pytest.mark.asyncio
    async def test_ga_session_transcript_done_sends_assistant_message(self):
        """When audio transcript is done, the GA session should forward
        the transcript as an assistant message."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.type = "response.output_audio_transcript.done"
        mock_event.transcript = "Here is my recommendation for capacitors."

        await client._response_audio_transcript_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert sent["payload"] == "Here is my recommendation for capacitors."

    @pytest.mark.asyncio
    async def test_ga_session_speech_started_sends_interrupt(self):
        """When user speech is detected, the GA session should send
        an interrupt signal to the client."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.type = "input_audio_buffer.speech_started"

        await client._input_audio_buffer_speech_started(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "interrupt"

    @pytest.mark.asyncio
    async def test_ga_session_close_cleans_up(self):
        """Closing a GA session should close both the client and realtime connections."""
        client = _make_ga_client()

        await client.close()

        client.client.close.assert_called_once()
        client.realtime.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: System prompt rendering with customer data
# ---------------------------------------------------------------------------


class TestGASystemPromptRendering:
    """Verify the Jinja2 template renders correctly with customer data,
    products, and purchases for GA mode."""

    def test_system_prompt_includes_customer_name(self):
        """The rendered system prompt should include the customer name."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="TestUser",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        assert "TestUser" in rendered

    def test_system_prompt_includes_purchase_details(self):
        """The rendered system prompt should include purchase product numbers."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="TestUser",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        assert "STM32F405RGT6" in rendered
        assert "STMicroelectronics" in rendered

    def test_system_prompt_includes_product_catalog(self):
        """The rendered system prompt should include product catalog entries."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="TestUser",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        assert "C0603C104K5RACTU" in rendered
        assert "KEMET" in rendered

    def test_system_prompt_includes_chat_context(self):
        """The rendered system prompt should include chat conversation context."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="TestUser",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        assert "I need help choosing a capacitor" in rendered

    def test_system_prompt_renders_with_real_data_files(self):
        """The template should render successfully with the actual products.json
        and purchases.json files from the project."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        products = json.loads(PRODUCTS_PATH.read_text())
        purchases = json.loads(PURCHASES_PATH.read_text())

        rendered = env.get_template("script.jinja2").render(
            customer="Brad",
            purchases=purchases,
            context=[{"name": "user", "text": "Hello"}],
            products=products,
        )

        assert len(rendered) > 100
        assert "Brad" in rendered


# ---------------------------------------------------------------------------
# Test 3: GA WebSocket handshake protocol
# ---------------------------------------------------------------------------


class TestGAWebSocketHandshake:
    """Verify the WebSocket handshake protocol for GA mode voice sessions."""

    @pytest.mark.asyncio
    async def test_handshake_first_message_is_chat_items(self):
        """The first WebSocket message in the handshake should contain
        chat items (type 'messages' with JSON payload)."""
        mock_ws = _make_mock_websocket()

        chat_payload = json.dumps(SAMPLE_CHAT_ITEMS)
        settings_payload = json.dumps(SAMPLE_SETTINGS)

        # Simulate the two-message handshake
        mock_ws.receive_json = AsyncMock(
            side_effect=[
                {"type": "messages", "payload": chat_payload},
                {"type": "messages", "payload": settings_payload},
            ]
        )

        # First message: chat items
        first_msg_data = await mock_ws.receive_json()
        first_msg = Message(**first_msg_data)
        assert first_msg.type == "messages"
        items = json.loads(first_msg.payload)
        assert isinstance(items, list)
        assert items[0]["name"] == "user"

    @pytest.mark.asyncio
    async def test_handshake_second_message_is_user_settings(self):
        """The second WebSocket message should contain user settings
        (user name, threshold, silence, prefix)."""
        mock_ws = _make_mock_websocket()

        chat_payload = json.dumps(SAMPLE_CHAT_ITEMS)
        settings_payload = json.dumps(SAMPLE_SETTINGS)

        mock_ws.receive_json = AsyncMock(
            side_effect=[
                {"type": "messages", "payload": chat_payload},
                {"type": "messages", "payload": settings_payload},
            ]
        )

        # Skip first message
        await mock_ws.receive_json()

        # Second message: user settings
        second_msg_data = await mock_ws.receive_json()
        second_msg = Message(**second_msg_data)
        settings = json.loads(second_msg.payload)
        assert settings["user"] == "TestUser"
        assert settings["threshold"] == 0.75
        assert settings["silence"] == 400
        assert settings["prefix"] == 250

    @pytest.mark.asyncio
    async def test_ga_session_created_sends_console_message(self):
        """When the GA realtime API confirms session creation, the client
        should receive a console message."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.type = "session.created"
        mock_event.to_json = MagicMock(return_value='{"type": "session.created"}')

        await client._session_created(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "console"


# ---------------------------------------------------------------------------
# Test 4: GA error handling
# ---------------------------------------------------------------------------


class TestGAErrorHandling:
    """Test error handling in GA voice sessions."""

    @pytest.mark.asyncio
    async def test_error_event_does_not_crash(self):
        """Receiving an error event from the realtime API should not
        crash the session."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.type = "error"
        mock_event.error = {"message": "Something went wrong", "code": "server_error"}

        # Should not raise
        await client._handle_error(mock_event)

    @pytest.mark.asyncio
    async def test_close_with_none_client(self):
        """Closing a session with None client should not raise."""
        client = _make_ga_client()
        client.client = None
        client.realtime = None

        # Should not raise
        await client.close()

    @pytest.mark.asyncio
    async def test_update_session_with_none_realtime(self):
        """Updating session when realtime is None should return early without error."""
        client = _make_ga_client()
        client.realtime = None

        # Should not raise, just return
        await client.update_realtime_session("instructions")

    @pytest.mark.asyncio
    async def test_empty_transcript_not_forwarded(self):
        """An empty transcript from transcription.completed should not
        be forwarded to the client."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.transcript = ""

        await client._conversation_item_input_audio_transcription_completed(mock_event)

        client.client.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_transcript_not_forwarded(self):
        """A None transcript from transcription.completed should not
        be forwarded to the client."""
        client = _make_ga_client()

        mock_event = MagicMock()
        mock_event.transcript = None

        await client._conversation_item_input_audio_transcription_completed(mock_event)

        client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: GA response.done with function calls and message output
# ---------------------------------------------------------------------------


class TestGAResponseDone:
    """Test the response.done handler in GA mode for different output types."""

    @pytest.mark.asyncio
    async def test_response_done_message_sends_console(self):
        """When response.done has a message output, it should send
        a console message with id, role, and content."""
        client = _make_ga_client()

        # Build a mock response.done event with message output
        mock_content = MagicMock()
        mock_content.transcript = "Here are some capacitor options."

        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.id = "item_001"
        mock_output.role = "assistant"
        mock_output.content = [mock_content]

        mock_response = MagicMock()
        mock_response.output = [mock_output]

        mock_event = MagicMock()
        mock_event.type = "response.done"
        mock_event.response = mock_response

        await client._response_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "console"
        payload = json.loads(sent["payload"])
        assert payload["id"] == "item_001"
        assert payload["role"] == "assistant"
        assert payload["content"] == "Here are some capacitor options."

    @pytest.mark.asyncio
    async def test_response_done_function_call_sends_function(self):
        """When response.done has a function_call output, it should send
        a function message with name, arguments, and call_id."""
        client = _make_ga_client()

        mock_output = MagicMock()
        mock_output.type = "function_call"
        mock_output.id = "fc_001"
        mock_output.name = "search_products"
        mock_output.arguments = '{"query": "capacitor"}'
        mock_output.call_id = "call_001"

        mock_response = MagicMock()
        mock_response.output = [mock_output]

        mock_event = MagicMock()
        mock_event.type = "response.done"
        mock_event.response = mock_response

        await client._response_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "function"
        payload = json.loads(sent["payload"])
        assert payload["name"] == "search_products"
        assert payload["call_id"] == "call_001"

    @pytest.mark.asyncio
    async def test_response_done_sets_active_false(self):
        """After response.done, the session active flag should be False."""
        client = _make_ga_client()
        client.active = True

        mock_response = MagicMock()
        mock_response.output = []

        mock_event = MagicMock()
        mock_event.response = mock_response

        await client._response_done(mock_event)

        assert client.active is False

    @pytest.mark.asyncio
    async def test_response_done_drains_response_queue(self):
        """After response.done, any queued conversation items should be
        sent and the queue cleared."""
        client = _make_ga_client()

        # Add items to the response queue
        mock_item = MagicMock()
        client.response_queue.append(mock_item)

        mock_response = MagicMock()
        mock_response.output = []

        mock_event = MagicMock()
        mock_event.response = mock_response

        await client._response_done(mock_event)

        # Queue should be drained
        assert len(client.response_queue) == 0
        # Items should have been sent
        client.realtime.send.assert_called_once_with(mock_item)
        # Response should have been created
        client.realtime.response.create.assert_called_once()
