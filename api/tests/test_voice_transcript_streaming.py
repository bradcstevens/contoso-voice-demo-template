"""
Tests for voice transcript streaming -- ensuring audio transcript deltas
are forwarded to the frontend as assistant_delta messages.

During voice sessions, the Azure OpenAI Realtime API sends:
- response.audio_transcript.delta: streaming chunks of the AI's speech text
- response.audio_transcript.done: the complete transcript

The delta events must be forwarded as type="assistant_delta" messages so
the frontend can display the AI's spoken response as a streaming chat
message in real time (rather than waiting for the complete transcript).

This test suite validates:
1. _response_audio_transcript_delta forwards deltas as assistant_delta
2. _response_audio_transcript_done still sends type="assistant" (no regression)
3. User transcription completed still sends type="user" (no regression)
4. The complete voice transcript flow: user STT -> AI TTS deltas -> AI TTS done
"""
import sys
import os
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(is_ga_mode: bool = False, debug: bool = False):
    """Create a RealtimeClient with mocked connections."""
    mock_realtime = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()

    client = RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=debug,
        is_ga_mode=is_ga_mode,
    )
    return client


def _make_transcript_delta_event(delta_text: str):
    """Create a mock ResponseAudioTranscriptDeltaEvent."""
    event = MagicMock()
    event.type = "response.audio_transcript.delta"
    event.delta = delta_text
    return event


def _make_transcript_done_event(transcript: str):
    """Create a mock ResponseAudioTranscriptDoneEvent."""
    event = MagicMock()
    event.type = "response.audio_transcript.done"
    event.transcript = transcript
    return event


def _make_user_transcription_event(transcript: str):
    """Create a mock ConversationItemInputAudioTranscriptionCompletedEvent."""
    event = MagicMock()
    event.type = "conversation.item.input_audio_transcription.completed"
    event.transcript = transcript
    return event


# ---------------------------------------------------------------------------
# Test 1: Audio transcript delta forwards as assistant_delta
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_transcript_delta_forwards_as_assistant_delta():
    """_response_audio_transcript_delta should send type=assistant_delta to frontend."""
    client = _make_client()

    event = _make_transcript_delta_event("Hello, ")
    await client._response_audio_transcript_delta(event)

    # Verify send_json was called with the correct message
    client.client.send_json.assert_called_once()
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "assistant_delta"
    assert sent["payload"] == "Hello, "


# ---------------------------------------------------------------------------
# Test 2: Audio transcript done still sends type=assistant (no regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_transcript_done_sends_assistant():
    """_response_audio_transcript_done should send type=assistant (unchanged)."""
    client = _make_client()

    event = _make_transcript_done_event("Hello, how can I help?")
    await client._response_audio_transcript_done(event)

    client.client.send_json.assert_called_once()
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "assistant"
    assert sent["payload"] == "Hello, how can I help?"


# ---------------------------------------------------------------------------
# Test 3: User transcription completed still sends type=user (no regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_transcription_sends_user_message():
    """_conversation_item_input_audio_transcription_completed sends type=user."""
    client = _make_client()

    event = _make_user_transcription_event("What resistors do you have?")
    await client._conversation_item_input_audio_transcription_completed(event)

    client.client.send_json.assert_called_once()
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "user"
    assert sent["payload"] == "What resistors do you have?"


# ---------------------------------------------------------------------------
# Test 4: Empty transcript delta is not forwarded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_transcript_delta_not_forwarded():
    """_response_audio_transcript_delta should skip empty deltas."""
    client = _make_client()

    event = _make_transcript_delta_event("")
    await client._response_audio_transcript_delta(event)

    client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Multiple deltas followed by done -- correct sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_voice_transcript_streaming_sequence():
    """Simulates the full sequence: multiple deltas then done.

    The frontend should receive:
    1. assistant_delta with "We "
    2. assistant_delta with "have "
    3. assistant_delta with "resistors."
    4. assistant with "We have resistors." (complete)
    """
    client = _make_client()

    # Stream deltas
    await client._response_audio_transcript_delta(
        _make_transcript_delta_event("We ")
    )
    await client._response_audio_transcript_delta(
        _make_transcript_delta_event("have ")
    )
    await client._response_audio_transcript_delta(
        _make_transcript_delta_event("resistors.")
    )

    # Complete
    await client._response_audio_transcript_done(
        _make_transcript_done_event("We have resistors.")
    )

    # Should have 4 send_json calls total
    assert client.client.send_json.call_count == 4

    calls = [c[0][0] for c in client.client.send_json.call_args_list]

    # First 3 are assistant_delta
    assert calls[0]["type"] == "assistant_delta"
    assert calls[0]["payload"] == "We "
    assert calls[1]["type"] == "assistant_delta"
    assert calls[1]["payload"] == "have "
    assert calls[2]["type"] == "assistant_delta"
    assert calls[2]["payload"] == "resistors."

    # Last is assistant (complete)
    assert calls[3]["type"] == "assistant"
    assert calls[3]["payload"] == "We have resistors."
