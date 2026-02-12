"""
Tests for Task 30 (subtask 30.2): GA session.update format validation.

Validates that:
1. GA session dict has 'type': 'realtime' at the top level
2. GA session uses 'output_modalities' (not 'modalities')
3. GA session nests audio config under 'audio.input' and 'audio.output'
4. GA audio format uses 'audio/pcm' with rate 24000 (not 'pcm16')
5. Preview session still uses the flat Session() typed-object format
6. Both modes preserve voice, VAD, and transcription settings
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Session, SessionUpdateEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(is_ga_mode: bool):
    """Create a RealtimeClient with mocked realtime connection."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_ws = MagicMock()
    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )


INSTRUCTIONS = "You are a helpful DigiKey electronics assistant."
THRESHOLD = 0.7
SILENCE_MS = 350
PREFIX_MS = 200


# ---------------------------------------------------------------------------
# GA Format Structure Tests
# ---------------------------------------------------------------------------


class TestGASessionTopLevelFields:
    """Validate top-level fields in the GA session dict."""

    @pytest.mark.asyncio
    async def test_ga_session_has_type_realtime(self):
        """GA session dict must include 'type': 'realtime'."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert session_dict["type"] == "realtime"

    @pytest.mark.asyncio
    async def test_ga_session_uses_output_modalities(self):
        """GA session must use 'output_modalities' not 'modalities'."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert "output_modalities" in session_dict
        assert "modalities" not in session_dict
        assert session_dict["output_modalities"] == ["text"]

    @pytest.mark.asyncio
    async def test_ga_session_includes_instructions(self):
        """GA session must pass through the instructions string."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert session_dict["instructions"] == INSTRUCTIONS

    @pytest.mark.asyncio
    async def test_ga_session_includes_temperature(self):
        """GA session must include a temperature field."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert "temperature" in session_dict
        assert isinstance(session_dict["temperature"], float)


class TestGASessionNestedAudioConfig:
    """Validate the nested audio configuration structure in GA mode."""

    @pytest.mark.asyncio
    async def test_ga_audio_input_format(self):
        """GA audio.input.format should use 'audio/pcm' with rate 24000."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        audio_input = session_dict["audio"]["input"]
        assert audio_input["format"]["type"] == "audio/pcm"
        assert audio_input["format"]["rate"] == 24000

    @pytest.mark.asyncio
    async def test_ga_audio_output_format(self):
        """GA audio.output.format should use 'audio/pcm' with rate 24000."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        audio_output = session_dict["audio"]["output"]
        assert audio_output["format"]["type"] == "audio/pcm"
        assert audio_output["format"]["rate"] == 24000

    @pytest.mark.asyncio
    async def test_ga_audio_output_voice(self):
        """GA audio.output.voice should be set to the configured voice."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert session_dict["audio"]["output"]["voice"] == "sage"

    @pytest.mark.asyncio
    async def test_ga_audio_input_transcription(self):
        """GA audio.input.transcription should specify whisper-1 model."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        transcription = session_dict["audio"]["input"]["transcription"]
        assert transcription["model"] == "whisper-1"

    @pytest.mark.asyncio
    async def test_ga_audio_input_turn_detection(self):
        """GA turn_detection should be nested under audio.input with correct params."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(
            INSTRUCTIONS,
            threshold=THRESHOLD,
            silence_duration_ms=SILENCE_MS,
            prefix_padding_ms=PREFIX_MS,
        )

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        td = session_dict["audio"]["input"]["turn_detection"]
        assert td["type"] == "server_vad"
        assert td["threshold"] == THRESHOLD
        assert td["silence_duration_ms"] == SILENCE_MS
        assert td["prefix_padding_ms"] == PREFIX_MS
        assert td["create_response"] is True

    @pytest.mark.asyncio
    async def test_ga_no_top_level_voice(self):
        """GA session should NOT have 'voice' at the top level (moved into audio.output)."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert "voice" not in session_dict, (
            "GA session should not have top-level 'voice' -- it belongs in audio.output"
        )

    @pytest.mark.asyncio
    async def test_ga_no_top_level_input_audio_format(self):
        """GA session should NOT have top-level 'input_audio_format'."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

        assert "input_audio_format" not in session_dict
        assert "output_audio_format" not in session_dict


class TestGASessionCallsMechanism:
    """Validate that GA mode uses session.update() vs preview uses send()."""

    @pytest.mark.asyncio
    async def test_ga_calls_session_update_not_send(self):
        """GA mode should call realtime.session.update(), not realtime.send()."""
        client = _make_client(is_ga_mode=True)
        await client.update_realtime_session(INSTRUCTIONS)

        client.realtime.session.update.assert_called_once()
        client.realtime.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_preview_calls_send_not_session_update(self):
        """Preview mode should call realtime.send(), not realtime.session.update()."""
        client = _make_client(is_ga_mode=False)
        await client.update_realtime_session(INSTRUCTIONS)

        client.realtime.send.assert_called_once()
        client.realtime.session.update.assert_not_called()


class TestPreviewSessionFormat:
    """Validate that preview mode still uses the flat Session() format."""

    @pytest.mark.asyncio
    async def test_preview_sends_session_update_event(self):
        """Preview mode should send a SessionUpdateEvent."""
        client = _make_client(is_ga_mode=False)
        await client.update_realtime_session(INSTRUCTIONS)

        sent_event = client.realtime.send.call_args[0][0]
        assert isinstance(sent_event, SessionUpdateEvent)

    @pytest.mark.asyncio
    async def test_preview_session_has_flat_voice(self):
        """Preview session should have voice at the top level."""
        client = _make_client(is_ga_mode=False)
        await client.update_realtime_session(INSTRUCTIONS)

        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.session.voice == "sage"

    @pytest.mark.asyncio
    async def test_preview_session_has_flat_modalities(self):
        """Preview session should use 'modalities' (not 'output_modalities')."""
        client = _make_client(is_ga_mode=False)
        await client.update_realtime_session(INSTRUCTIONS)

        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.session.modalities == ["text"]

    @pytest.mark.asyncio
    async def test_preview_session_uses_pcm16(self):
        """Preview session should use 'pcm16' audio format (not 'audio/pcm')."""
        client = _make_client(is_ga_mode=False)
        await client.update_realtime_session(INSTRUCTIONS)

        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.session.input_audio_format == "pcm16"
