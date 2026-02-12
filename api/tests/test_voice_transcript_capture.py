"""
Tests for Tasks 54 & 55: Capture voice transcripts as UnifiedMessages.

Task 54: User voice transcripts (input_audio_transcription.completed) are
         stored in ConversationStore as UnifiedMessage(role="user", source="realtime").

Task 55: Assistant voice responses (_response_text_done and
         _response_audio_transcript_done) are stored as
         UnifiedMessage(role="assistant", source="realtime").

These tests validate that the RealtimeClient event handlers write to the
ConversationStore correctly, including metadata, while still forwarding
messages to the frontend WebSocket (no regressions on existing behavior).
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient
from conversation_store import ConversationStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(thread_id: str | None = "test-thread", store: ConversationStore | None = None):
    """Create a RealtimeClient with mocked connections and an isolated store."""
    mock_realtime = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()

    client = RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=False,
        thread_id=thread_id,
    )
    # Inject an isolated ConversationStore so tests don't pollute each other
    # or rely on the module-level singleton.
    if store is not None:
        client._conversation_store = store
    else:
        client._conversation_store = ConversationStore()
    return client


def _make_user_transcription_event(transcript: str, item_id: str | None = None):
    """Mock ConversationItemInputAudioTranscriptionCompletedEvent."""
    event = MagicMock()
    event.type = "conversation.item.input_audio_transcription.completed"
    event.transcript = transcript
    if item_id is not None:
        event.item_id = item_id
    return event


def _make_text_done_event(text: str):
    """Mock ResponseTextDoneEvent."""
    event = MagicMock()
    event.type = "response.text.done"
    event.text = text
    return event


def _make_audio_transcript_done_event(transcript: str):
    """Mock ResponseAudioTranscriptDoneEvent."""
    event = MagicMock()
    event.type = "response.audio_transcript.done"
    event.transcript = transcript
    return event


# ---------------------------------------------------------------------------
# Test 1: User transcript stored with correct role and source (Task 54)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_transcript_stored_as_unified_message():
    """User voice transcript should be stored as UnifiedMessage with
    role='user', source='realtime', and metadata containing audioPresent=True."""
    store = ConversationStore()
    client = _make_client(thread_id="thread-1", store=store)

    event = _make_user_transcription_event("What resistors do you carry?", item_id="item-42")
    await client._conversation_item_input_audio_transcription_completed(event)

    messages = store.get_messages("thread-1")
    assert len(messages) == 1
    msg = messages[0]
    assert msg.role == "user"
    assert msg.content == "What resistors do you carry?"
    assert msg.source == "realtime"
    assert msg.metadata is not None
    assert msg.metadata["audioPresent"] is True
    assert msg.metadata["realtimeItemId"] == "item-42"

    # Frontend forwarding still works (no regression)
    client.client.send_json.assert_called_once()
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "user"


# ---------------------------------------------------------------------------
# Test 2: No storage when thread_id is None (Task 54 + 55 shared)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_storage_when_thread_id_is_none():
    """When thread_id is None, transcripts should NOT be stored but still forwarded."""
    store = ConversationStore()
    client = _make_client(thread_id=None, store=store)

    # User transcript
    await client._conversation_item_input_audio_transcription_completed(
        _make_user_transcription_event("Hello")
    )
    # Assistant text
    await client._response_text_done(_make_text_done_event("Hi there"))
    # Assistant audio transcript
    await client._response_audio_transcript_done(
        _make_audio_transcript_done_event("Hi there audio")
    )

    # Nothing stored in any thread
    assert store.get_messages("") == []
    # But all three messages were forwarded to the frontend
    assert client.client.send_json.call_count == 3


# ---------------------------------------------------------------------------
# Test 3: Empty transcripts are not stored (Task 54 + 55 shared)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_transcript_not_stored():
    """Empty or None transcripts should not be stored or forwarded."""
    store = ConversationStore()
    client = _make_client(thread_id="thread-2", store=store)

    # Empty user transcript
    await client._conversation_item_input_audio_transcription_completed(
        _make_user_transcription_event("")
    )
    # Empty assistant text
    await client._response_text_done(_make_text_done_event(""))
    # Empty assistant audio transcript
    await client._response_audio_transcript_done(
        _make_audio_transcript_done_event("")
    )

    assert store.get_messages("thread-2") == []
    client.client.send_json.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Assistant text response stored correctly (Task 55)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assistant_text_response_stored():
    """_response_text_done should store assistant text as UnifiedMessage
    with role='assistant' and source='realtime'."""
    store = ConversationStore()
    client = _make_client(thread_id="thread-3", store=store)

    event = _make_text_done_event("We carry a wide range of resistors.")
    await client._response_text_done(event)

    messages = store.get_messages("thread-3")
    assert len(messages) == 1
    msg = messages[0]
    assert msg.role == "assistant"
    assert msg.content == "We carry a wide range of resistors."
    assert msg.source == "realtime"
    assert msg.metadata is not None
    assert msg.metadata["audioPresent"] is True

    # Frontend still gets the message
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "assistant"


# ---------------------------------------------------------------------------
# Test 5: Assistant audio transcript stored correctly (Task 55)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assistant_audio_transcript_stored():
    """_response_audio_transcript_done should store assistant audio transcript
    as UnifiedMessage with role='assistant' and source='realtime'."""
    store = ConversationStore()
    client = _make_client(thread_id="thread-4", store=store)

    event = _make_audio_transcript_done_event("Let me look that up for you.")
    await client._response_audio_transcript_done(event)

    messages = store.get_messages("thread-4")
    assert len(messages) == 1
    msg = messages[0]
    assert msg.role == "assistant"
    assert msg.content == "Let me look that up for you."
    assert msg.source == "realtime"
    assert msg.metadata is not None
    assert msg.metadata["audioPresent"] is True

    # Frontend still gets the message
    sent = client.client.send_json.call_args[0][0]
    assert sent["type"] == "assistant"
