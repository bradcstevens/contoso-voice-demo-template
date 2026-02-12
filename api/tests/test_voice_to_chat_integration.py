"""
Integration tests for Task #58: Voice-to-Chat context switching.

Validates that voice conversation transcripts stored via the unified
ConversationStore are available to the chat pipeline when a user switches
from voice back to text chat.  Covers:

1. Voice transcripts available in Chat Completions API format via get_chat_format()
2. Voice messages carry correct source metadata (source="realtime", audioPresent=True)
3. Mixed chat + voice messages maintain insertion order and correct sources
4. RealtimeConnectionManager.store_voice_message dual-writes to both
   ConversationStore and legacy session context
5. get_chat_format() returns clean Chat Completions format (text only, no audio metadata)
6. Empty / unused thread_id returns empty list from get_chat_format()
"""

import os
import sys
import types

# Set required env vars BEFORE importing modules that transitively load the
# prompty configuration (session -> chat -> prompty.load).
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-api-key")

# Ensure the api directory is on the import path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Mock heavy dependencies that are NOT under test but are pulled in
# transitively by session.py (session -> chat -> prompty.azure, models).
# Without azure SDK installed, these imports would fail at collection time.
# ---------------------------------------------------------------------------

# Mock the 'chat' module so 'from chat import create_response' succeeds.
if "chat" not in sys.modules:
    _mock_chat = types.ModuleType("chat")
    _mock_chat.create_response = None  # type: ignore[attr-defined]
    sys.modules["chat"] = _mock_chat

# Mock the 'models' module so 'from models import ...' succeeds.
if "models" not in sys.modules:
    _mock_models = types.ModuleType("models")
    # Provide the names that session.py imports.
    for _name in [
        "ClientMessage", "send_action", "send_context",
        "start_assistant", "stop_assistant", "stream_assistant",
    ]:
        setattr(_mock_models, _name, None)
    sys.modules["models"] = _mock_models

# Mock prompty modules that are transitively imported.
for _mod_name in ["prompty", "prompty.azure", "prompty.tracer"]:
    if _mod_name not in sys.modules:
        _m = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _m

# prompty.tracer needs 'trace' (used as decorator) and 'Tracer'.
_tracer_mod = sys.modules["prompty.tracer"]
if not hasattr(_tracer_mod, "trace"):
    # Make trace() a no-op decorator that works with and without arguments.
    def _trace_decorator(fn=None, **kwargs):
        if fn is not None:
            return fn
        return lambda f: f
    _tracer_mod.trace = _trace_decorator  # type: ignore[attr-defined]

if not hasattr(_tracer_mod, "Tracer"):
    from unittest.mock import MagicMock as _MagicMock
    _tracer_mod.Tracer = _MagicMock()  # type: ignore[attr-defined]

import pytest
from unittest.mock import MagicMock, AsyncMock

from conversation_store import ConversationStore, UnifiedMessage
from conversation_utils import (
    realtime_transcript_to_unified,
    user_message_to_unified,
    chat_response_to_unified,
)
from realtime_manager import RealtimeConnectionManager
from session import ChatSession, SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket with configurable client_state."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _fresh_store() -> ConversationStore:
    """Return a new, empty ConversationStore for test isolation."""
    return ConversationStore()


# ---------------------------------------------------------------------------
# Test 1: Voice transcripts available in chat format
# ---------------------------------------------------------------------------

class TestVoiceTranscriptsInChatFormat:
    """After storing voice transcripts via realtime_transcript_to_unified() +
    store.add_message(), get_chat_format() should return them as standard
    Chat Completions API messages."""

    def test_voice_transcripts_appear_in_chat_format(self):
        """User and assistant voice transcripts should be returned by
        get_chat_format() as {role, content} dicts."""
        store = _fresh_store()
        thread_id = "thread-voice-chat-1"

        # Simulate a voice user transcript
        user_msg = realtime_transcript_to_unified(
            transcript="What resistors do you have in stock?",
            role="user",
            thread_id=thread_id,
            realtime_item_id="item-001",
        )
        store.add_message(thread_id, user_msg)

        # Simulate a voice assistant transcript
        assistant_msg = realtime_transcript_to_unified(
            transcript="We have a wide selection of resistors. What value are you looking for?",
            role="assistant",
            thread_id=thread_id,
        )
        store.add_message(thread_id, assistant_msg)

        # Retrieve in Chat Completions format
        chat_messages = store.get_chat_format(thread_id)

        assert len(chat_messages) == 2

        assert chat_messages[0] == {
            "role": "user",
            "content": "What resistors do you have in stock?",
        }
        assert chat_messages[1] == {
            "role": "assistant",
            "content": "We have a wide selection of resistors. What value are you looking for?",
        }


# ---------------------------------------------------------------------------
# Test 2: Voice messages have correct source metadata
# ---------------------------------------------------------------------------

class TestVoiceMessageMetadata:
    """Voice messages created via realtime_transcript_to_unified() should
    carry source='realtime' and metadata['audioPresent']=True."""

    def test_voice_message_source_and_metadata(self):
        """Stored voice messages should have realtime source and audio flag."""
        store = _fresh_store()
        thread_id = "thread-meta-check"

        user_msg = realtime_transcript_to_unified(
            transcript="Tell me about capacitors",
            role="user",
            thread_id=thread_id,
            realtime_item_id="item-100",
        )
        store.add_message(thread_id, user_msg)

        assistant_msg = realtime_transcript_to_unified(
            transcript="Capacitors store electrical charge.",
            role="assistant",
            thread_id=thread_id,
        )
        store.add_message(thread_id, assistant_msg)

        messages = store.get_messages(thread_id)

        assert len(messages) == 2

        # User message assertions
        assert messages[0].source == "realtime"
        assert messages[0].role == "user"
        assert messages[0].metadata is not None
        assert messages[0].metadata["audioPresent"] is True
        assert messages[0].metadata["realtimeItemId"] == "item-100"

        # Assistant message assertions
        assert messages[1].source == "realtime"
        assert messages[1].role == "assistant"
        assert messages[1].metadata is not None
        assert messages[1].metadata["audioPresent"] is True
        # No realtime_item_id was provided for the assistant message
        assert "realtimeItemId" not in messages[1].metadata


# ---------------------------------------------------------------------------
# Test 3: Mixed chat + voice messages preserve order and sources
# ---------------------------------------------------------------------------

class TestMixedChatVoiceOrder:
    """When a user chats via text and then switches to voice, all messages
    should be stored in chronological order with their respective sources."""

    def test_mixed_messages_preserve_order_and_source(self):
        """Chat and voice messages interleaved should maintain insertion order."""
        store = _fresh_store()
        thread_id = "thread-mixed-order"

        # Step 1: Chat user message
        chat_user = user_message_to_unified(
            text="Hi, I need help finding a component.",
            thread_id=thread_id,
        )
        store.add_message(thread_id, chat_user)

        # Step 2: Chat assistant message
        chat_assistant = chat_response_to_unified(
            response_text="Sure! What component are you looking for?",
            thread_id=thread_id,
        )
        store.add_message(thread_id, chat_assistant)

        # Step 3: Voice user message (user switches to voice)
        voice_user = realtime_transcript_to_unified(
            transcript="I need a 100 microfarad capacitor",
            role="user",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_user)

        # Step 4: Voice assistant message
        voice_assistant = realtime_transcript_to_unified(
            transcript="We have several 100 microfarad options available.",
            role="assistant",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_assistant)

        messages = store.get_messages(thread_id)

        assert len(messages) == 4

        # Verify order and sources
        assert messages[0].role == "user"
        assert messages[0].source == "chat"
        assert messages[0].content == "Hi, I need help finding a component."

        assert messages[1].role == "assistant"
        assert messages[1].source == "chat"
        assert messages[1].content == "Sure! What component are you looking for?"

        assert messages[2].role == "user"
        assert messages[2].source == "realtime"
        assert messages[2].content == "I need a 100 microfarad capacitor"

        assert messages[3].role == "assistant"
        assert messages[3].source == "realtime"
        assert messages[3].content == "We have several 100 microfarad options available."

        # Verify get_chat_format returns all four in order
        chat_format = store.get_chat_format(thread_id)
        assert len(chat_format) == 4
        assert chat_format[0]["role"] == "user"
        assert chat_format[1]["role"] == "assistant"
        assert chat_format[2]["role"] == "user"
        assert chat_format[3]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Test 4: store_voice_message dual-writes to ConversationStore + legacy session
# ---------------------------------------------------------------------------

class TestStoreVoiceMessageDualWrite:
    """RealtimeConnectionManager.store_voice_message() should write to both
    the unified ConversationStore and the legacy ChatSession.context."""

    @pytest.mark.asyncio
    async def test_dual_write_to_store_and_session(self):
        """store_voice_message should add a UnifiedMessage to conversation_store
        AND append 'role: transcript' to the legacy session context."""
        # Reset SessionManager state for isolation
        SessionManager.sessions = {}

        # Create a ChatSession with a mock WebSocket
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-dual", ws)

        # Call store_voice_message (it uses the module-level conversation_store
        # and SessionManager singletons)
        RealtimeConnectionManager.store_voice_message(
            thread_id="thread-dual",
            transcript="hello, can you help me?",
            role="user",
        )

        # Verify: message in the module-level conversation_store
        from conversation_store import conversation_store
        messages = conversation_store.get_messages("thread-dual")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "hello, can you help me?"
        assert messages[0].source == "realtime"

        # Verify: legacy context on the session
        assert "user: hello, can you help me?" in session.context

        # Clean up: clear the thread from the module-level store so other
        # tests using the singleton are not affected.
        conversation_store.clear_thread("thread-dual")
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_dual_write_assistant_message(self):
        """store_voice_message with role='assistant' should also dual-write."""
        SessionManager.sessions = {}

        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-dual-asst", ws)

        RealtimeConnectionManager.store_voice_message(
            thread_id="thread-dual-asst",
            transcript="I can help you find the right component.",
            role="assistant",
            realtime_item_id="rt-item-42",
        )

        from conversation_store import conversation_store
        messages = conversation_store.get_messages("thread-dual-asst")
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert messages[0].content == "I can help you find the right component."
        assert messages[0].metadata["realtimeItemId"] == "rt-item-42"

        assert "assistant: I can help you find the right component." in session.context

        # Clean up
        conversation_store.clear_thread("thread-dual-asst")
        SessionManager.sessions = {}


# ---------------------------------------------------------------------------
# Test 5: get_chat_format returns proper Chat Completions format (text only)
# ---------------------------------------------------------------------------

class TestGetChatFormatAfterVoice:
    """After a multi-turn voice conversation, get_chat_format() should return
    a list of {role, content} dicts containing only text -- no audio metadata,
    no source field, no timestamp."""

    def test_chat_format_is_clean_after_voice(self):
        """get_chat_format output should contain only 'role' and 'content' keys."""
        store = _fresh_store()
        thread_id = "thread-clean-format"

        # Three voice turns: user, assistant, user
        store.add_message(thread_id, realtime_transcript_to_unified(
            transcript="Do you sell Arduino boards?",
            role="user",
            thread_id=thread_id,
            realtime_item_id="item-a",
        ))
        store.add_message(thread_id, realtime_transcript_to_unified(
            transcript="Yes, we carry several Arduino models.",
            role="assistant",
            thread_id=thread_id,
        ))
        store.add_message(thread_id, realtime_transcript_to_unified(
            transcript="Which one do you recommend for beginners?",
            role="user",
            thread_id=thread_id,
            realtime_item_id="item-b",
        ))

        chat_format = store.get_chat_format(thread_id)

        assert len(chat_format) == 3

        # Each entry should have exactly 'role' and 'content', nothing else
        for entry in chat_format:
            assert set(entry.keys()) == {"role", "content"}
            assert isinstance(entry["role"], str)
            assert isinstance(entry["content"], str)

        # Verify content ordering
        assert chat_format[0] == {
            "role": "user",
            "content": "Do you sell Arduino boards?",
        }
        assert chat_format[1] == {
            "role": "assistant",
            "content": "Yes, we carry several Arduino models.",
        }
        assert chat_format[2] == {
            "role": "user",
            "content": "Which one do you recommend for beginners?",
        }


# ---------------------------------------------------------------------------
# Test 6: Empty voice history returns empty list
# ---------------------------------------------------------------------------

class TestEmptyVoiceHistory:
    """get_chat_format() with an unused thread_id should return an empty list,
    not raise an error."""

    def test_unused_thread_returns_empty_list(self):
        """A thread_id with no messages should yield []."""
        store = _fresh_store()
        result = store.get_chat_format("thread-never-used")
        assert result == []

    def test_cleared_thread_returns_empty_list(self):
        """After clear_thread(), get_chat_format should return []."""
        store = _fresh_store()
        thread_id = "thread-cleared"

        store.add_message(thread_id, realtime_transcript_to_unified(
            transcript="Hello",
            role="user",
            thread_id=thread_id,
        ))
        assert len(store.get_chat_format(thread_id)) == 1

        store.clear_thread(thread_id)
        assert store.get_chat_format(thread_id) == []
