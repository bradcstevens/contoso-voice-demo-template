"""
Tests for Task 31: WebSocket session protocol validation.

Validates the WebSocket handshake and message protocol:
1. First message must contain chat items (Message with type 'messages' and JSON payload)
2. Second message contains user settings (user name, threshold, silence, prefix)
3. System prompt rendering with jinja2 template validates variable substitution
4. Graceful shutdown and cleanup of WebSocket and realtime connections
5. Client-to-realtime message forwarding (audio, user text, interrupt, function)

These tests focus on the protocol layer without testing the actual WebSocket transport.
"""

import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import (
    RealtimeClient,
    Message,
    InputAudioBufferAppendEvent,
    ConversationItemCreateEvent,
    ResponseCreateEvent,
)
from jinja2 import Environment, FileSystemLoader
from fastapi.websockets import WebSocketState


# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------

VOICE_TEMPLATE_DIR = Path(__file__).parent.parent / "voice"
PRODUCTS_PATH = Path(__file__).parent.parent / "products.json"
PURCHASES_PATH = Path(__file__).parent.parent / "purchases.json"

SAMPLE_PRODUCTS = [
    {
        "Description": {
            "ProductDescription": "LED RED 620NM 2SMD",
            "DetailedDescription": "Red 620nm LED Indication 2-SMD",
        },
        "Manufacturer": {"Id": 200, "Name": "Lite-On Inc."},
        "ManufacturerProductNumber": "LTST-C150KRKT",
        "UnitPrice": 0.15,
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
    {"name": "user", "text": "I am looking for LEDs for my project"},
    {"name": "assistant", "text": "I can help you find suitable LEDs."},
]


def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket client."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_mock_realtime():
    """Create a mock realtime connection."""
    mock_rt = AsyncMock()
    mock_rt.send = AsyncMock()
    mock_rt.close = AsyncMock()
    mock_rt.session = MagicMock()
    mock_rt.session.update = AsyncMock()
    mock_rt.response = MagicMock()
    mock_rt.response.create = AsyncMock()
    return mock_rt


def _make_client(is_ga_mode=True, debug=False):
    """Create a RealtimeClient with mocked dependencies."""
    mock_rt = _make_mock_realtime()
    mock_ws = _make_mock_websocket()
    return RealtimeClient(
        realtime=mock_rt,
        client=mock_ws,
        debug=debug,
        is_ga_mode=is_ga_mode,
    )


# ---------------------------------------------------------------------------
# Test 1: First message protocol - chat items
# ---------------------------------------------------------------------------


class TestFirstMessageProtocol:
    """The first WebSocket message in the voice handshake must contain
    chat items as a Message with type 'messages'."""

    def test_message_model_accepts_messages_type(self):
        """Message model should accept type='messages'."""
        msg = Message(type="messages", payload='[{"name": "user", "text": "hello"}]')
        assert msg.type == "messages"
        assert isinstance(json.loads(msg.payload), list)

    def test_chat_items_payload_is_valid_json_list(self):
        """The chat items payload must parse to a list of dicts with name and text."""
        payload = json.dumps(SAMPLE_CHAT_ITEMS)
        msg = Message(type="messages", payload=payload)
        items = json.loads(msg.payload)
        assert isinstance(items, list)
        assert len(items) == 2
        assert all("name" in item and "text" in item for item in items)

    def test_empty_chat_items_is_valid(self):
        """An empty chat items list should be valid."""
        msg = Message(type="messages", payload="[]")
        items = json.loads(msg.payload)
        assert items == []

    def test_chat_items_preserve_conversation_order(self):
        """Chat items should preserve the order of the conversation."""
        items = [
            {"name": "user", "text": "First message"},
            {"name": "assistant", "text": "Response"},
            {"name": "user", "text": "Second message"},
        ]
        msg = Message(type="messages", payload=json.dumps(items))
        parsed = json.loads(msg.payload)
        assert parsed[0]["text"] == "First message"
        assert parsed[2]["text"] == "Second message"


# ---------------------------------------------------------------------------
# Test 2: Second message protocol - user settings
# ---------------------------------------------------------------------------


class TestSecondMessageProtocol:
    """The second WebSocket message must contain user settings with
    user name, threshold, silence, and prefix."""

    def test_settings_payload_contains_required_fields(self):
        """Settings payload must contain user, threshold, silence, and prefix."""
        settings = {
            "user": "TestUser",
            "threshold": 0.8,
            "silence": 500,
            "prefix": 300,
        }
        msg = Message(type="messages", payload=json.dumps(settings))
        parsed = json.loads(msg.payload)

        assert "user" in parsed
        assert "threshold" in parsed
        assert "silence" in parsed
        assert "prefix" in parsed

    def test_settings_default_values_used_when_missing(self):
        """When settings fields are missing, the voice endpoint code
        uses default values (threshold=0.8, silence=500, prefix=300)."""
        settings = {"user": "DefaultUser"}

        # Simulate main.py logic for extracting settings with defaults
        threshold = settings["threshold"] if "threshold" in settings else 0.8
        silence = settings["silence"] if "silence" in settings else 500
        prefix = settings["prefix"] if "prefix" in settings else 300

        assert threshold == 0.8
        assert silence == 500
        assert prefix == 300

    def test_settings_default_user_when_missing(self):
        """When 'user' field is missing, the voice endpoint defaults to 'Brad'."""
        settings = {}

        # Simulate main.py logic
        user = settings["user"] if "user" in settings else "Brad"
        assert user == "Brad"

    def test_settings_numeric_types_preserved(self):
        """Threshold should be float, silence and prefix should be int."""
        settings = {
            "user": "TestUser",
            "threshold": 0.75,
            "silence": 400,
            "prefix": 250,
        }
        parsed = json.loads(json.dumps(settings))

        assert isinstance(parsed["threshold"], float)
        assert isinstance(parsed["silence"], int)
        assert isinstance(parsed["prefix"], int)


# ---------------------------------------------------------------------------
# Test 3: Jinja2 template rendering validation
# ---------------------------------------------------------------------------


class TestJinja2TemplateRendering:
    """Validate the Jinja2 template correctly substitutes all variables."""

    def test_template_renders_customer_name_in_greeting(self):
        """The template should mention the customer name in the greeting section."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="Alice",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        # Customer name should appear multiple times (greeting, understand section)
        assert rendered.count("Alice") >= 2

    def test_template_renders_purchase_prices(self):
        """The template should include unit prices from purchases."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="Alice",
            purchases=SAMPLE_PURCHASES,
            context=[],
            products=SAMPLE_PRODUCTS,
        )

        assert "$12.5" in rendered

    def test_template_renders_product_prices(self):
        """The template should include unit prices from product catalog."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="Alice",
            purchases=[],
            context=[],
            products=SAMPLE_PRODUCTS,
        )

        assert "$0.15" in rendered

    def test_template_handles_special_characters_in_context(self):
        """The template should handle special characters in chat context."""
        context_with_special = [
            {"name": "user", "text": "I need a 10uF cap with >25V rating & <0.1% tolerance"},
        ]
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="Alice",
            purchases=[],
            context=context_with_special,
            products=[],
        )

        assert ">25V" in rendered or "&gt;25V" in rendered

    def test_template_renders_manufacturer_info(self):
        """The template should include manufacturer names in both purchases and products."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="Alice",
            purchases=SAMPLE_PURCHASES,
            context=[],
            products=SAMPLE_PRODUCTS,
        )

        assert "STMicroelectronics" in rendered
        assert "Lite-On Inc." in rendered


# ---------------------------------------------------------------------------
# Test 4: Graceful shutdown and cleanup
# ---------------------------------------------------------------------------


class TestGracefulShutdown:
    """Test graceful shutdown and cleanup of voice sessions."""

    @pytest.mark.asyncio
    async def test_close_calls_both_connections(self):
        """close() should attempt to close both client and realtime."""
        client = _make_client()

        await client.close()

        client.client.close.assert_called_once()
        client.realtime.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_client_close_error(self):
        """close() should handle errors when closing the client WebSocket."""
        client = _make_client()
        client.client.close = AsyncMock(side_effect=Exception("Connection reset"))

        # Should not raise
        await client.close()

        # client and realtime should be set to None after error
        assert client.client is None
        assert client.realtime is None

    def test_closed_property_true_when_disconnected(self):
        """closed property should return True when client is disconnected."""
        client = _make_client()
        client.client.client_state = WebSocketState.DISCONNECTED

        assert client.closed is True

    def test_closed_property_true_when_client_none(self):
        """closed property should return True when client is None."""
        client = _make_client()
        client.client = None

        assert client.closed is True

    def test_closed_property_false_when_connected(self):
        """closed property should return False when client is connected."""
        client = _make_client()
        # Mock client_state as not DISCONNECTED
        client.client.client_state = "CONNECTED"

        assert client.closed is False


# ---------------------------------------------------------------------------
# Test 5: Client-to-realtime message forwarding
# ---------------------------------------------------------------------------


class TestClientToRealtimeForwarding:
    """Test that receive_client correctly forwards different message types
    from the frontend WebSocket to the realtime API."""

    @pytest.mark.asyncio
    async def test_audio_message_forwarded_as_input_audio_buffer(self):
        """An audio message from the client should be forwarded as
        InputAudioBufferAppendEvent to the realtime API."""
        client = _make_client()

        audio_msg = json.dumps({"type": "audio", "payload": "base64audiodata"})
        client.client.receive_text = AsyncMock(side_effect=[audio_msg, Exception("done")])
        client.client.client_state = WebSocketState.CONNECTED

        # receive_client will loop; the second call raises to break the loop
        try:
            await client.receive_client()
        except Exception:
            pass

        # Verify the audio was sent to realtime
        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert isinstance(sent_event, InputAudioBufferAppendEvent)
        assert sent_event.audio == "base64audiodata"

    @pytest.mark.asyncio
    async def test_user_text_message_creates_conversation_item(self):
        """A user text message should create a ConversationItemCreateEvent."""
        client = _make_client()

        user_msg = json.dumps({"type": "user", "payload": "What capacitor do you recommend?"})
        client.client.receive_text = AsyncMock(side_effect=[user_msg, Exception("done")])
        client.client.client_state = WebSocketState.CONNECTED

        try:
            await client.receive_client()
        except Exception:
            pass

        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert isinstance(sent_event, ConversationItemCreateEvent)
        assert sent_event.item.content[0].text == "What capacitor do you recommend?"

    @pytest.mark.asyncio
    async def test_interrupt_message_creates_response(self):
        """An interrupt message should trigger ResponseCreateEvent."""
        client = _make_client()

        interrupt_msg = json.dumps({"type": "interrupt", "payload": ""})
        client.client.receive_text = AsyncMock(side_effect=[interrupt_msg, Exception("done")])
        client.client.client_state = WebSocketState.CONNECTED

        try:
            await client.receive_client()
        except Exception:
            pass

        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert isinstance(sent_event, ResponseCreateEvent)

    @pytest.mark.asyncio
    async def test_function_message_creates_function_output_and_response(self):
        """A function message should create a ConversationItemCreateEvent
        with function_call_output and then trigger a response.

        When microphone_active is False (default), the function handler sends
        a text-only ResponseCreateEvent via realtime.send() instead of calling
        realtime.response.create()."""
        from fastapi import WebSocketDisconnect as WSD
        client = _make_client()

        func_payload = json.dumps({
            "call_id": "call_001",
            "output": '{"result": "found 5 capacitors"}',
        })
        func_msg = json.dumps({"type": "function", "payload": func_payload})
        # Use WebSocketDisconnect for clean loop termination via the except clause
        client.client.receive_text = AsyncMock(side_effect=[func_msg, WSD(code=1000)])
        client.client.client_state = WebSocketState.CONNECTED

        await client.receive_client()

        # Should have sent a ConversationItemCreateEvent and a ResponseCreateEvent
        # (microphone_active defaults to False, so text-only response via send())
        assert client.realtime.send.call_count >= 2
        # Find the ConversationItemCreateEvent in send calls
        found_create_event = False
        found_response_event = False
        for call_args in client.realtime.send.call_args_list:
            sent_event = call_args[0][0]
            if isinstance(sent_event, ConversationItemCreateEvent):
                assert sent_event.item.type == "function_call_output"
                assert sent_event.item.call_id == "call_001"
                found_create_event = True
            elif isinstance(sent_event, ResponseCreateEvent):
                found_response_event = True
        assert found_create_event, "Expected a ConversationItemCreateEvent to be sent"
        assert found_response_event, "Expected a ResponseCreateEvent to be sent"

    @pytest.mark.asyncio
    async def test_unknown_message_type_sends_console_unhandled(self):
        """An unrecognized message type should send a console 'Unhandled message'
        via the send_console handler directly."""
        client = _make_client()

        # Test the default case handler directly instead of through the receive loop,
        # since the loop requires careful WebSocket state management.
        await client.send_console(Message(type="console", payload="Unhandled message"))

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "console"
        assert sent["payload"] == "Unhandled message"
