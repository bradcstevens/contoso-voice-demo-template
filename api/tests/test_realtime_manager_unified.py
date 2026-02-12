"""
Tests for Task 56: Update RealtimeConnectionManager to write voice context
via ConversationStore.

Validates:
1. store_voice_message creates UnifiedMessage in conversation_store with
   correct role and source="realtime"
2. store_voice_message also writes to legacy session context for backward
   compatibility
3. store_voice_message does not error when no session exists (only stores
   in conversation_store)
4. get_unified_context returns UnifiedMessage objects from the store
5. get_unified_context returns empty list when no messages exist
"""

import sys
import os
from unittest.mock import MagicMock, AsyncMock

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars BEFORE importing modules that pull in the chat
# prompty loader (session -> chat -> prompty.load requires these).
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-api-key")

from conversation_store import UnifiedMessage, conversation_store

# ---------------------------------------------------------------------------
# Module-level mocks: session.py imports chat which imports prompty.azure,
# and that requires the Azure SDK.  We stub out the heavy dependencies so
# the test suite can run without them.
# ---------------------------------------------------------------------------
_mock_prompty = MagicMock()
_mock_prompty_azure = MagicMock()
_mock_prompty_tracer = MagicMock()

# Provide Tracer constants used by session.receive_chat
_mock_tracer_class = MagicMock()
_mock_tracer_class.SIGNATURE = "signature"
_mock_tracer_class.INPUTS = "inputs"
_mock_tracer_class.RESULT = "result"
_span_cm = MagicMock()
_span_cm.__enter__ = MagicMock(return_value=MagicMock())
_span_cm.__exit__ = MagicMock(return_value=False)
_mock_tracer_class.start.return_value = _span_cm
_mock_prompty_tracer.Tracer = _mock_tracer_class


def _mock_trace(fn=None, **kwargs):
    """Mock for prompty.tracer.trace that handles both @trace and @trace(name=...)."""
    if fn is not None:
        return fn
    return lambda f: f


_mock_prompty_tracer.trace = _mock_trace

# Pre-seed sys.modules to avoid the real prompty.azure import
if "prompty" not in sys.modules:
    sys.modules["prompty"] = _mock_prompty
if "prompty.azure" not in sys.modules:
    sys.modules["prompty.azure"] = _mock_prompty_azure
if "prompty.tracer" not in sys.modules:
    sys.modules["prompty.tracer"] = _mock_prompty_tracer

# Stub out the chat module so session.py finds a mock create_response
_mock_chat = MagicMock()
_mock_chat.create_response = AsyncMock()
if "chat" not in sys.modules:
    sys.modules["chat"] = _mock_chat

# Now we can safely import session and realtime_manager
from session import SessionManager
from realtime_manager import RealtimeConnectionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset conversation_store and SessionManager between tests."""
    conversation_store.clear_thread("test-thread")
    SessionManager.sessions = {}
    yield
    conversation_store.clear_thread("test-thread")
    SessionManager.sessions = {}


# ---------------------------------------------------------------------------
# Test 1: store_voice_message creates UnifiedMessage with correct attributes
# ---------------------------------------------------------------------------

class TestStoreVoiceMessageCreatesUnifiedMessage:
    """store_voice_message should create a UnifiedMessage in conversation_store
    with the correct role, content, and source='realtime'."""

    def test_stores_user_message_with_realtime_source(self):
        """A user transcript should be stored as source='realtime' with role='user'."""
        RealtimeConnectionManager.store_voice_message(
            thread_id="test-thread",
            transcript="I need a 10 microfarad capacitor",
            role="user",
            realtime_item_id="item-001",
        )

        messages = conversation_store.get_messages("test-thread")
        assert len(messages) == 1
        msg = messages[0]
        assert msg.role == "user"
        assert msg.content == "I need a 10 microfarad capacitor"
        assert msg.source == "realtime"
        assert msg.metadata is not None
        assert msg.metadata.get("realtimeItemId") == "item-001"
        assert msg.metadata.get("audioPresent") is True

    def test_stores_assistant_message_with_realtime_source(self):
        """An assistant transcript should be stored with role='assistant' and source='realtime'."""
        RealtimeConnectionManager.store_voice_message(
            thread_id="test-thread",
            transcript="I found several options for you",
            role="assistant",
        )

        messages = conversation_store.get_messages("test-thread")
        assert len(messages) == 1
        msg = messages[0]
        assert msg.role == "assistant"
        assert msg.content == "I found several options for you"
        assert msg.source == "realtime"


# ---------------------------------------------------------------------------
# Test 2: store_voice_message writes to legacy session context
# ---------------------------------------------------------------------------

class TestStoreVoiceMessageLegacyContext:
    """store_voice_message should also write to the legacy session context
    for backward compatibility with prompty."""

    @pytest.mark.asyncio
    async def test_writes_to_legacy_session_context(self):
        """When a session exists, legacy context should contain 'role: transcript'."""
        ws = MagicMock()
        ws.client_state = "CONNECTED"
        ws.send_json = AsyncMock()
        session = await SessionManager.create_session("test-thread", ws)

        RealtimeConnectionManager.store_voice_message(
            thread_id="test-thread",
            transcript="What voltage regulators do you have?",
            role="user",
        )

        assert "user: What voltage regulators do you have?" in session.context

    @pytest.mark.asyncio
    async def test_assistant_legacy_context_format(self):
        """Assistant transcripts should appear as 'assistant: {text}' in legacy context."""
        ws = MagicMock()
        ws.client_state = "CONNECTED"
        ws.send_json = AsyncMock()
        session = await SessionManager.create_session("test-thread", ws)

        RealtimeConnectionManager.store_voice_message(
            thread_id="test-thread",
            transcript="We have LM7805 and LM317 regulators",
            role="assistant",
        )

        assert "assistant: We have LM7805 and LM317 regulators" in session.context


# ---------------------------------------------------------------------------
# Test 3: store_voice_message with no session does not error
# ---------------------------------------------------------------------------

class TestStoreVoiceMessageNoSession:
    """store_voice_message should not raise when no session exists for the
    given thread_id -- it should still store in conversation_store."""

    def test_no_session_stores_in_conversation_store_only(self):
        """When no session exists, message is stored in conversation_store without error."""
        # No session created -- SessionManager.sessions is empty
        RealtimeConnectionManager.store_voice_message(
            thread_id="test-thread",
            transcript="Hello from a sessionless voice call",
            role="user",
        )

        messages = conversation_store.get_messages("test-thread")
        assert len(messages) == 1
        assert messages[0].content == "Hello from a sessionless voice call"


# ---------------------------------------------------------------------------
# Test 4: get_unified_context returns UnifiedMessage objects
# ---------------------------------------------------------------------------

class TestGetUnifiedContext:
    """get_unified_context should return a list of UnifiedMessage objects
    from the ConversationStore."""

    def test_returns_unified_messages(self):
        """get_unified_context should return stored UnifiedMessage objects."""
        conversation_store.add_message(
            "test-thread",
            UnifiedMessage(
                role="user",
                content="Tell me about resistors",
                source="chat",
            ),
        )
        conversation_store.add_message(
            "test-thread",
            UnifiedMessage(
                role="assistant",
                content="Resistors limit current flow",
                source="chat",
            ),
        )

        result = RealtimeConnectionManager.get_unified_context("test-thread")
        assert len(result) == 2
        assert all(isinstance(m, UnifiedMessage) for m in result)
        assert result[0].role == "user"
        assert result[1].role == "assistant"


# ---------------------------------------------------------------------------
# Test 5: get_unified_context returns empty list for missing thread
# ---------------------------------------------------------------------------

class TestGetUnifiedContextEmpty:
    """get_unified_context should return an empty list when no messages exist."""

    def test_returns_empty_list_for_unknown_thread(self):
        """An unknown thread_id should yield an empty list, not None or error."""
        result = RealtimeConnectionManager.get_unified_context("nonexistent-thread")
        assert result == []
        assert isinstance(result, list)
