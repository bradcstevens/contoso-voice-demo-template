"""
Tests for RealtimeClient.update_realtime_session dual-mode support.

Validates that:
1. GA mode produces the correct nested audio dict format
2. Preview mode still produces the existing Session() typed-object format
3. Voice, VAD, and transcription settings are preserved in both modes
4. GA mode includes create_response: True in turn_detection
5. No-op when realtime connection is None
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

# We need to import the module under test. The GA imports may or may not
# be available depending on the SDK version, but the module handles that
# via try/except. We import after the module has been loaded.
from api.voice import RealtimeClient, Session, SessionUpdateEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(is_ga_mode: bool):
    """Create a RealtimeClient with a mock realtime connection."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_ws = MagicMock()
    client = RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )
    return client


INSTRUCTIONS = "You are a helpful electronics assistant."
THRESHOLD = 0.6
SILENCE_MS = 400
PREFIX_MS = 250


# ---------------------------------------------------------------------------
# Test 1: GA mode uses nested dict format with session.update()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ga_mode_uses_nested_audio_dict():
    """GA mode should call realtime.session.update() with a nested audio dict."""
    client = _make_client(is_ga_mode=True)

    await client.update_realtime_session(
        INSTRUCTIONS,
        threshold=THRESHOLD,
        silence_duration_ms=SILENCE_MS,
        prefix_padding_ms=PREFIX_MS,
    )

    # GA mode should use realtime.session.update(), NOT realtime.send()
    client.realtime.session.update.assert_called_once()
    client.realtime.send.assert_not_called()

    # Inspect the session dict passed to session.update()
    call_kwargs = client.realtime.session.update.call_args
    session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")

    assert isinstance(session_dict, dict), "GA session should be a plain dict"
    assert session_dict["type"] == "realtime"
    assert session_dict["instructions"] == INSTRUCTIONS
    assert session_dict["output_modalities"] == ["text"]
    assert session_dict["temperature"] == 0.8

    # Verify nested audio structure
    audio = session_dict["audio"]
    assert audio["input"]["transcription"]["model"] == "whisper-1"
    assert audio["input"]["format"]["type"] == "audio/pcm"
    assert audio["input"]["format"]["rate"] == 24000
    assert audio["output"]["voice"] == "sage"
    assert audio["output"]["format"]["type"] == "audio/pcm"
    assert audio["output"]["format"]["rate"] == 24000


# ---------------------------------------------------------------------------
# Test 2: Preview mode uses Session() typed-object with send()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_mode_uses_session_object():
    """Preview mode should call realtime.send() with SessionUpdateEvent."""
    client = _make_client(is_ga_mode=False)

    await client.update_realtime_session(
        INSTRUCTIONS,
        threshold=THRESHOLD,
        silence_duration_ms=SILENCE_MS,
        prefix_padding_ms=PREFIX_MS,
    )

    # Preview mode should use realtime.send(), NOT realtime.session.update()
    client.realtime.send.assert_called_once()
    client.realtime.session.update.assert_not_called()

    # Inspect the event passed to send()
    sent_event = client.realtime.send.call_args[0][0]
    assert isinstance(sent_event, SessionUpdateEvent)
    assert sent_event.type == "session.update"

    session = sent_event.session
    assert isinstance(session, Session)
    assert session.instructions == INSTRUCTIONS
    assert session.voice == "sage"
    assert session.input_audio_format == "pcm16"
    assert session.modalities == ["text"]


# ---------------------------------------------------------------------------
# Test 3: GA mode VAD settings match parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ga_mode_vad_settings():
    """GA mode turn_detection should reflect the method parameters."""
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


# ---------------------------------------------------------------------------
# Test 4: Preview mode VAD settings match parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_mode_vad_settings():
    """Preview mode turn_detection should reflect the method parameters."""
    client = _make_client(is_ga_mode=False)

    await client.update_realtime_session(
        INSTRUCTIONS,
        threshold=THRESHOLD,
        silence_duration_ms=SILENCE_MS,
        prefix_padding_ms=PREFIX_MS,
    )

    sent_event = client.realtime.send.call_args[0][0]
    td = sent_event.session.turn_detection

    assert td.type == "server_vad"
    assert td.threshold == THRESHOLD
    assert td.silence_duration_ms == SILENCE_MS
    assert td.prefix_padding_ms == PREFIX_MS


# ---------------------------------------------------------------------------
# Test 5: No-op when realtime is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_noop_when_realtime_is_none():
    """update_realtime_session should be a no-op when realtime is None."""
    mock_ws = MagicMock()
    client = RealtimeClient(
        realtime=AsyncMock(),
        client=mock_ws,
        debug=False,
        is_ga_mode=False,
    )
    # Simulate disconnected state
    client.realtime = None

    # Should not raise
    await client.update_realtime_session(INSTRUCTIONS)
