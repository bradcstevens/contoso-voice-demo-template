"""
Tests for Task 52: Update ChatSession to store UnifiedMessage history.

Validates:
1. ChatSession.__init__ stores thread_id as an attribute
2. receive_chat stores messages in both self.context and conversation_store
3. get_chat_messages returns Chat Completions API format from the store
4. get_unified_messages returns UnifiedMessage objects from the store
5. SessionManager.create_session passes thread_id to ChatSession
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

# Now we can safely import session
from session import ChatSession, SessionManager


# ---------------------------------------------------------------------------
# Test 1: ChatSession.__init__ stores thread_id
# ---------------------------------------------------------------------------

class TestChatSessionStoresThreadId:
    """ChatSession should accept and store a thread_id attribute alongside
    the existing client, realtime, and context attributes."""

    def test_init_stores_thread_id(self):
        """thread_id passed to __init__ should be accessible as self.thread_id."""
        mock_ws = MagicMock()
        session = ChatSession(mock_ws, "thread-42")

        assert session.thread_id == "thread-42"
        assert session.client is mock_ws
        assert session.context == []
        assert session.realtime is None


# ---------------------------------------------------------------------------
# Test 2: receive_chat stores in both context list AND conversation_store
# ---------------------------------------------------------------------------

class TestReceiveChatStoresUnifiedMessages:
    """After a simulated chat turn, both the legacy self.context list and
    the global conversation_store should contain entries."""

    @pytest.mark.asyncio
    async def test_receive_chat_stores_in_both(self):
        """A single chat turn should produce entries in self.context and
        conversation_store for the session's thread_id."""
        thread_id = "test-thread-receive"
        # Clear any leftover state in the singleton store
        conversation_store.clear_thread(thread_id)

        mock_ws = AsyncMock()

        from fastapi.websockets import WebSocketState
        mock_ws.client_state = WebSocketState.CONNECTED

        call_count = 0

        async def receive_json_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"name": "TestUser", "text": "What is camping?", "image": None}
            # After first message, disconnect to break the loop
            mock_ws.client_state = WebSocketState.DISCONNECTED
            raise Exception("disconnect")

        mock_ws.receive_json = AsyncMock(side_effect=receive_json_side_effect)
        mock_ws.send_json = AsyncMock()

        session = ChatSession(mock_ws, thread_id)

        mock_response = {
            "response": "test answer",
            "context": "context summary",
            "call": 1,
        }

        with patch("session.create_response", new_callable=AsyncMock, return_value=mock_response):
            try:
                await session.receive_chat()
            except Exception:
                pass  # Expected: loop exits via disconnect/exception

        # Legacy context should have the context summary
        assert len(session.context) >= 1
        assert "context summary" in session.context

        # conversation_store should have both user and assistant messages
        messages = conversation_store.get_messages(thread_id)
        assert len(messages) >= 2

        roles = [m.role for m in messages]
        assert "user" in roles
        assert "assistant" in roles

        user_msg = next(m for m in messages if m.role == "user")
        assert user_msg.content == "What is camping?"
        assert user_msg.source == "chat"

        assistant_msg = next(m for m in messages if m.role == "assistant")
        assert assistant_msg.content == "test answer"
        assert assistant_msg.source == "chat"

        # Cleanup
        conversation_store.clear_thread(thread_id)


# ---------------------------------------------------------------------------
# Test 3: get_chat_messages returns Chat Completions API format
# ---------------------------------------------------------------------------

class TestGetChatMessages:
    """get_chat_messages should delegate to conversation_store.get_chat_format
    and return list of {'role': ..., 'content': ...} dicts."""

    def test_get_chat_messages_returns_correct_format(self):
        """Messages stored in conversation_store should be returned in
        Chat Completions API format via session.get_chat_messages()."""
        thread_id = "chat-format-thread"
        conversation_store.clear_thread(thread_id)

        # Pre-populate store
        conversation_store.add_message(
            thread_id,
            UnifiedMessage(role="user", content="Hello", source="chat"),
        )
        conversation_store.add_message(
            thread_id,
            UnifiedMessage(role="assistant", content="Hi there!", source="chat"),
        )

        mock_ws = MagicMock()
        session = ChatSession(mock_ws, thread_id)

        result = session.get_chat_messages()
        assert result == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Cleanup
        conversation_store.clear_thread(thread_id)


# ---------------------------------------------------------------------------
# Test 4: get_unified_messages returns UnifiedMessage objects
# ---------------------------------------------------------------------------

class TestGetUnifiedMessages:
    """get_unified_messages should return a list of UnifiedMessage instances
    from the conversation_store for the session's thread_id."""

    def test_get_unified_messages_returns_objects(self):
        """Returned items should be UnifiedMessage instances with correct data."""
        thread_id = "unified-msg-thread"
        conversation_store.clear_thread(thread_id)

        msg1 = UnifiedMessage(role="user", content="test", source="chat")
        msg2 = UnifiedMessage(role="assistant", content="reply", source="chat")
        conversation_store.add_message(thread_id, msg1)
        conversation_store.add_message(thread_id, msg2)

        mock_ws = MagicMock()
        session = ChatSession(mock_ws, thread_id)

        messages = session.get_unified_messages()
        assert len(messages) == 2
        assert all(isinstance(m, UnifiedMessage) for m in messages)
        assert messages[0].content == "test"
        assert messages[1].content == "reply"

        # Cleanup
        conversation_store.clear_thread(thread_id)


# ---------------------------------------------------------------------------
# Test 5: SessionManager.create_session passes thread_id to ChatSession
# ---------------------------------------------------------------------------

class TestSessionManagerPassesThreadId:
    """SessionManager.create_session should pass thread_id when constructing
    a ChatSession, so the resulting session knows its thread_id."""

    @pytest.mark.asyncio
    async def test_create_session_passes_thread_id(self):
        """The session created by SessionManager should have the thread_id set."""
        mock_ws = AsyncMock()
        session = await SessionManager.create_session("mgr-thread-99", mock_ws)

        assert session.thread_id == "mgr-thread-99"
        assert SessionManager.sessions.get("mgr-thread-99") is session

        # Cleanup
        del SessionManager.sessions["mgr-thread-99"]
