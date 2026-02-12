"""
Tests for Task 30 (subtask 30.6): Dual-mode compatibility.

Validates that the same RealtimeClient code works correctly in both
GA and preview modes without errors:

1. Both modes can create RealtimeClient instances
2. Both modes can call update_realtime_session successfully
3. Both modes have all required handler methods
4. Speech-started interrupt works in both modes
5. Audio delta handler works in both modes
6. Response done handler works in both modes
7. Client receive loop handles messages in both modes
"""

import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INSTRUCTIONS = "You are a helpful electronics expert."


def _make_client(is_ga_mode: bool, debug: bool = False):
    """Create a RealtimeClient for the given mode with full mock setup."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_realtime.response = MagicMock()
    mock_realtime.response.create = AsyncMock()

    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=debug,
        is_ga_mode=is_ga_mode,
    )


def _make_mock_event(event_type: str, **kwargs):
    """Create a mock event with the given type and attributes."""
    event = MagicMock()
    event.type = event_type
    for key, value in kwargs.items():
        setattr(event, key, value)
    return event


# ---------------------------------------------------------------------------
# Session Update Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeSessionUpdate:
    """Both GA and preview modes should successfully call update_realtime_session."""

    @pytest.mark.asyncio
    async def test_ga_session_update_succeeds(self):
        """GA mode update_realtime_session should complete without error."""
        client = _make_client(is_ga_mode=True)
        # Should not raise
        await client.update_realtime_session(
            INSTRUCTIONS, threshold=0.6, silence_duration_ms=400, prefix_padding_ms=250
        )
        client.realtime.session.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_session_update_succeeds(self):
        """Preview mode update_realtime_session should complete without error."""
        client = _make_client(is_ga_mode=False)
        # Should not raise
        await client.update_realtime_session(
            INSTRUCTIONS, threshold=0.6, silence_duration_ms=400, prefix_padding_ms=250
        )
        client.realtime.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_modes_noop_when_disconnected(self):
        """Both modes should be no-ops when realtime is None."""
        for mode in [True, False]:
            client = _make_client(is_ga_mode=mode)
            client.realtime = None
            # Should not raise
            await client.update_realtime_session(INSTRUCTIONS)


# ---------------------------------------------------------------------------
# Handler Method Availability in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeHandlerAvailability:
    """All handler methods should exist on RealtimeClient regardless of mode."""

    REQUIRED_HANDLERS = [
        "_handle_error",
        "_session_created",
        "_session_updated",
        "_conversation_created",
        "_conversation_item_created",
        "_conversation_item_input_audio_transcription_completed",
        "_input_audio_buffer_speech_started",
        "_input_audio_buffer_speech_stopped",
        "_response_created",
        "_response_done",
        "_response_text_delta",
        "_response_audio_transcript_delta",
        "_response_audio_transcript_done",
        "_response_audio_delta",
        "_response_audio_done",
        "_response_function_call_arguments_done",
        "_rate_limits_updated",
        "_conversation_item_added",
        "_conversation_item_done",
    ]

    def test_ga_mode_has_all_handlers(self):
        """GA mode client should have all required handler methods."""
        client = _make_client(is_ga_mode=True)
        for handler in self.REQUIRED_HANDLERS:
            assert hasattr(client, handler), f"GA client missing handler: {handler}"
            assert callable(getattr(client, handler))

    def test_preview_mode_has_all_handlers(self):
        """Preview mode client should have all required handler methods."""
        client = _make_client(is_ga_mode=False)
        for handler in self.REQUIRED_HANDLERS:
            assert hasattr(client, handler), f"Preview client missing handler: {handler}"
            assert callable(getattr(client, handler))


# ---------------------------------------------------------------------------
# Speech Interrupt Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeSpeechInterrupt:
    """Speech started interrupt should work identically in both modes."""

    @pytest.mark.asyncio
    async def test_ga_speech_started_sends_interrupt(self):
        """GA mode should send interrupt message on speech_started event."""
        client = _make_client(is_ga_mode=True)
        mock_event = _make_mock_event("input_audio_buffer.speech_started")

        await client._input_audio_buffer_speech_started(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "interrupt"

    @pytest.mark.asyncio
    async def test_preview_speech_started_sends_interrupt(self):
        """Preview mode should send interrupt message on speech_started event."""
        client = _make_client(is_ga_mode=False)
        mock_event = _make_mock_event("input_audio_buffer.speech_started")

        await client._input_audio_buffer_speech_started(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "interrupt"


# ---------------------------------------------------------------------------
# Audio Delta Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeAudioDelta:
    """Audio delta handler should send audio data in both modes."""

    @pytest.mark.asyncio
    async def test_ga_audio_delta_sends_audio(self):
        """GA mode should send audio data via _response_audio_delta."""
        client = _make_client(is_ga_mode=True)
        mock_event = _make_mock_event("response.output_audio.delta", delta="AQIDBA==")

        await client._response_audio_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "audio"
        assert sent["payload"] == "AQIDBA=="

    @pytest.mark.asyncio
    async def test_preview_audio_delta_sends_audio(self):
        """Preview mode should send audio data via _response_audio_delta."""
        client = _make_client(is_ga_mode=False)
        mock_event = _make_mock_event("response.audio.delta", delta="BQYHCA==")

        await client._response_audio_delta(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "audio"
        assert sent["payload"] == "BQYHCA=="


# ---------------------------------------------------------------------------
# Audio Transcript Done Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeTranscriptDone:
    """Audio transcript done handler should send assistant messages in both modes."""

    @pytest.mark.asyncio
    async def test_ga_transcript_done_sends_message(self):
        """GA mode should send assistant message when transcript is done."""
        client = _make_client(is_ga_mode=True)
        mock_event = _make_mock_event(
            "response.output_audio_transcript.done",
            transcript="Hello, how can I help you with electronics today?"
        )

        await client._response_audio_transcript_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert "electronics" in sent["payload"]

    @pytest.mark.asyncio
    async def test_preview_transcript_done_sends_message(self):
        """Preview mode should send assistant message when transcript is done."""
        client = _make_client(is_ga_mode=False)
        mock_event = _make_mock_event(
            "response.audio_transcript.done",
            transcript="I can help you find the right capacitor."
        )

        await client._response_audio_transcript_done(mock_event)

        client.client.send_json.assert_called_once()
        sent = client.client.send_json.call_args[0][0]
        assert sent["type"] == "assistant"
        assert "capacitor" in sent["payload"]

    @pytest.mark.asyncio
    async def test_empty_transcript_skipped_in_both_modes(self):
        """Empty transcripts should not send messages in either mode."""
        for mode in [True, False]:
            client = _make_client(is_ga_mode=mode)
            mock_event = _make_mock_event(
                "response.audio_transcript.done", transcript=""
            )
            await client._response_audio_transcript_done(mock_event)
            client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Response Done Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeResponseDone:
    """Response done handler should process outputs in both modes."""

    @pytest.mark.asyncio
    async def test_ga_response_done_with_message_output(self):
        """GA mode response.done with message output should send console data."""
        client = _make_client(is_ga_mode=True)

        # Build a mock response.done event with message output
        mock_content = MagicMock()
        mock_content.transcript = "Test transcript"
        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.id = "output_001"
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
        assert payload["content"] == "Test transcript"
        assert payload["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_preview_response_done_with_message_output(self):
        """Preview mode response.done with message output should send console data."""
        client = _make_client(is_ga_mode=False)

        mock_content = MagicMock()
        mock_content.transcript = "Preview transcript"
        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.id = "output_002"
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
        assert payload["content"] == "Preview transcript"

    @pytest.mark.asyncio
    async def test_response_done_sets_active_false(self):
        """response_done should set active=False in both modes."""
        for mode in [True, False]:
            client = _make_client(is_ga_mode=mode)
            client.active = True

            mock_response = MagicMock()
            mock_response.output = []  # empty output

            mock_event = MagicMock()
            mock_event.response = mock_response

            await client._response_done(mock_event)
            assert client.active is False


# ---------------------------------------------------------------------------
# Message Model Consistency
# ---------------------------------------------------------------------------


class TestMessageModelConsistency:
    """Message model should work the same regardless of mode."""

    def test_message_types_valid(self):
        """All expected message types should be constructable."""
        valid_types = ["user", "assistant", "audio", "console", "interrupt", "messages", "function"]
        for msg_type in valid_types:
            msg = Message(type=msg_type, payload="test")
            assert msg.type == msg_type
            assert msg.payload == "test"

    def test_message_model_dump(self):
        """Message.model_dump() should produce a serializable dict."""
        msg = Message(type="audio", payload="base64data")
        dumped = msg.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["type"] == "audio"
        assert dumped["payload"] == "base64data"


# ---------------------------------------------------------------------------
# Close Works in Both Modes
# ---------------------------------------------------------------------------


class TestDualModeClose:
    """close() should work in both modes without errors."""

    @pytest.mark.asyncio
    async def test_ga_mode_close(self):
        """GA mode close should call client.close() and realtime.close()."""
        client = _make_client(is_ga_mode=True)
        client.client.close = AsyncMock()
        client.realtime.close = AsyncMock()

        await client.close()

        client.client.close.assert_called_once()
        client.realtime.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_mode_close(self):
        """Preview mode close should call client.close() and realtime.close()."""
        client = _make_client(is_ga_mode=False)
        client.client.close = AsyncMock()
        client.realtime.close = AsyncMock()

        await client.close()

        client.client.close.assert_called_once()
        client.realtime.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_none(self):
        """close() should be a no-op when client and realtime are None."""
        for mode in [True, False]:
            client = _make_client(is_ga_mode=mode)
            client.client = None
            client.realtime = None
            # Should not raise
            await client.close()
