"""
Tests for Task 31: End-to-end voice session tests for Preview mode (backward compatibility).

Validates that the preview-mode voice flow still works correctly:
1. Full voice session lifecycle in preview mode
2. System prompt rendering (same template, different session format)
3. Preview-mode session.update uses SessionUpdateEvent (not session.update())
4. Error handling remains consistent in preview mode
5. Client message forwarding works with preview event names

These tests mirror test_voice_e2e_ga.py but with AZURE_VOICE_API_MODE=preview.
"""

import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Message, SessionUpdateEvent
from jinja2 import Environment, FileSystemLoader


# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------

VOICE_TEMPLATE_DIR = Path(__file__).parent.parent / "voice"

SAMPLE_PRODUCTS = [
    {
        "Description": {
            "ProductDescription": "RES 10K OHM 1% 0402",
            "DetailedDescription": "10 kOhms 1% 0.063W Thick Film Resistor 0402",
        },
        "Manufacturer": {"Id": 100, "Name": "Yageo"},
        "ManufacturerProductNumber": "RC0402FR-0710KL",
        "UnitPrice": 0.01,
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
    {"name": "user", "text": "I need a 10k resistor for my circuit"},
    {"name": "assistant", "text": "I can help you select a suitable resistor."},
]

SAMPLE_SETTINGS = {
    "user": "PreviewUser",
    "threshold": 0.8,
    "silence": 500,
    "prefix": 300,
}


def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket client."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_mock_realtime_connection():
    """Create a mock realtime connection."""
    mock_rt = AsyncMock()
    mock_rt.send = AsyncMock()
    mock_rt.close = AsyncMock()
    mock_rt.session = MagicMock()
    mock_rt.session.update = AsyncMock()
    mock_rt.response = MagicMock()
    mock_rt.response.create = AsyncMock()
    return mock_rt


def _make_preview_client(debug=False):
    """Create a RealtimeClient in Preview mode with mocked dependencies."""
    mock_rt = _make_mock_realtime_connection()
    mock_ws = _make_mock_websocket()
    client = RealtimeClient(
        realtime=mock_rt,
        client=mock_ws,
        debug=debug,
        is_ga_mode=False,
    )
    return client


# ---------------------------------------------------------------------------
# Test 1: Preview session lifecycle
# ---------------------------------------------------------------------------


class TestPreviewVoiceSessionLifecycle:
    """End-to-end test of the preview voice session lifecycle."""

    @pytest.mark.asyncio
    async def test_preview_session_configure_uses_send(self):
        """Preview mode should call realtime.send() with a SessionUpdateEvent,
        not realtime.session.update()."""
        client = _make_preview_client()

        await client.update_realtime_session(
            instructions="You are a helpful assistant.",
            threshold=0.8,
            silence_duration_ms=500,
            prefix_padding_ms=300,
        )

        client.realtime.send.assert_called_once()
        client.realtime.session.update.assert_not_called()

        sent_event = client.realtime.send.call_args[0][0]
        assert isinstance(sent_event, SessionUpdateEvent)

    @pytest.mark.asyncio
    async def test_preview_session_update_event_structure(self):
        """Preview SessionUpdateEvent should have flat voice, modalities,
        and pcm16 audio format."""
        client = _make_preview_client()

        await client.update_realtime_session(
            instructions="You are a helpful assistant.",
            threshold=0.8,
            silence_duration_ms=500,
            prefix_padding_ms=300,
        )

        sent_event = client.realtime.send.call_args[0][0]
        session = sent_event.session

        assert session.voice == "sage"
        assert session.modalities == ["text"]
        assert session.input_audio_format == "pcm16"
        assert session.instructions == "You are a helpful assistant."
        assert session.turn_detection.threshold == 0.8
        assert session.turn_detection.silence_duration_ms == 500
        assert session.turn_detection.prefix_padding_ms == 300

    @pytest.mark.asyncio
    async def test_preview_audio_delta_forwarded_to_client(self):
        """Preview mode audio delta events should be forwarded to the client."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.type = "response.audio.delta"
        mock_event.delta = "previewaudiocontent"

        await client._response_audio_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "audio"
        assert sent["payload"] == "previewaudiocontent"

    @pytest.mark.asyncio
    async def test_preview_transcript_done_sends_assistant(self):
        """Preview mode transcript done should forward as assistant message."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.type = "response.audio_transcript.done"
        mock_event.transcript = "Here are my recommendations."

        await client._response_audio_transcript_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert sent["payload"] == "Here are my recommendations."

    @pytest.mark.asyncio
    async def test_preview_session_close_cleans_up(self):
        """Closing a preview session should close both connections."""
        client = _make_preview_client()

        await client.close()

        client.client.close.assert_called_once()
        client.realtime.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: Preview mode backward compatibility
# ---------------------------------------------------------------------------


class TestPreviewBackwardCompatibility:
    """Verify that preview mode still operates correctly alongside GA mode."""

    def test_preview_client_is_ga_mode_false(self):
        """Preview client should have is_ga_mode=False."""
        client = _make_preview_client()
        assert client.is_ga_mode is False

    @pytest.mark.asyncio
    async def test_preview_text_delta_forwards_message(self):
        """Preview response.text.delta should forward text deltas as
        assistant_delta type to the client for streaming display."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.delta = "Some text content"

        await client._response_text_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant_delta"
        assert sent["payload"] == "Some text content"

    @pytest.mark.asyncio
    async def test_preview_speech_started_sends_interrupt(self):
        """Preview speech_started should send an interrupt to the client."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.type = "input_audio_buffer.speech_started"

        await client._input_audio_buffer_speech_started(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "interrupt"

    @pytest.mark.asyncio
    async def test_preview_user_transcription_forwarded(self):
        """Preview transcription.completed should forward user transcript."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.transcript = "Can you recommend a resistor?"

        await client._conversation_item_input_audio_transcription_completed(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "user"
        assert sent["payload"] == "Can you recommend a resistor?"


# ---------------------------------------------------------------------------
# Test 3: Preview error handling
# ---------------------------------------------------------------------------


class TestPreviewErrorHandling:
    """Error handling in preview mode should be consistent with GA mode."""

    @pytest.mark.asyncio
    async def test_preview_error_event_no_crash(self):
        """Preview error events should not crash the session."""
        client = _make_preview_client()

        mock_event = MagicMock()
        mock_event.type = "error"
        mock_event.error = {"message": "rate limit", "code": "rate_limit_exceeded"}

        await client._handle_error(mock_event)

    @pytest.mark.asyncio
    async def test_preview_close_with_none_realtime(self):
        """Closing preview session with None realtime should not raise."""
        client = _make_preview_client()
        client.client = None
        client.realtime = None

        await client.close()

    @pytest.mark.asyncio
    async def test_preview_update_with_none_realtime(self):
        """Preview update_realtime_session with None realtime should return early."""
        client = _make_preview_client()
        client.realtime = None

        await client.update_realtime_session("instructions")

        # No calls should have been made since realtime is None


# ---------------------------------------------------------------------------
# Test 4: Preview response.done behavior
# ---------------------------------------------------------------------------


class TestPreviewResponseDone:
    """Test response.done handler behavior in preview mode."""

    @pytest.mark.asyncio
    async def test_preview_response_done_message_output(self):
        """Preview response.done with message output sends console data."""
        client = _make_preview_client()

        mock_content = MagicMock()
        mock_content.transcript = "I recommend the Yageo resistor."

        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.id = "msg_preview_001"
        mock_output.role = "assistant"
        mock_output.content = [mock_content]

        mock_response = MagicMock()
        mock_response.output = [mock_output]

        mock_event = MagicMock()
        mock_event.response = mock_response

        await client._response_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "console"
        payload = json.loads(sent["payload"])
        assert payload["id"] == "msg_preview_001"
        assert payload["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_preview_response_done_sets_active_false(self):
        """Preview response.done should set active to False."""
        client = _make_preview_client()
        client.active = True

        mock_response = MagicMock()
        mock_response.output = []

        mock_event = MagicMock()
        mock_event.response = mock_response

        await client._response_done(mock_event)

        assert client.active is False


# ---------------------------------------------------------------------------
# Test 5: Preview system prompt rendering
# ---------------------------------------------------------------------------


class TestPreviewSystemPromptRendering:
    """Verify system prompt renders correctly for preview mode sessions.
    The template is shared between GA and preview modes."""

    def test_preview_template_renders_with_customer_data(self):
        """Preview mode uses the same Jinja2 template and should render correctly."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="PreviewUser",
            purchases=SAMPLE_PURCHASES,
            context=SAMPLE_CHAT_ITEMS,
            products=SAMPLE_PRODUCTS,
        )

        assert "PreviewUser" in rendered
        assert "STM32F405RGT6" in rendered
        assert "RC0402FR-0710KL" in rendered
        assert "I need a 10k resistor" in rendered

    def test_preview_template_renders_empty_context(self):
        """Preview mode should handle empty chat context gracefully."""
        env = Environment(loader=FileSystemLoader(VOICE_TEMPLATE_DIR))
        rendered = env.get_template("script.jinja2").render(
            customer="EmptyUser",
            purchases=[],
            context=[],
            products=[],
        )

        assert "EmptyUser" in rendered
        assert len(rendered) > 50
