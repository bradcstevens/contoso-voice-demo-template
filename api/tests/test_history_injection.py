"""
Tests for Task 53: Inject conversation history into realtime sessions
via conversation.item.create events.

Validates:
1. inject_conversation_history sends typed ConversationItemCreateEvent objects
2. User messages use input_text content type; assistant messages use text
3. System messages are skipped during injection
4. Empty history returns 0 without error
5. Returns 0 when realtime connection is None
"""

import sys
import os
import asyncio

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock
from conversation_store import ConversationStore, UnifiedMessage, conversation_store
from voice import RealtimeClient, ConversationItemCreateEvent


class MockRealtimeConnection:
    """Mock realtime connection that records sent events."""

    def __init__(self):
        self.sent_events = []

    async def send(self, event):
        self.sent_events.append(event)


def _make_client_with_mock(debug=False):
    """Create a RealtimeClient with a MockRealtimeConnection."""
    mock_realtime = MockRealtimeConnection()
    mock_websocket = MagicMock()
    mock_websocket.client_state = "CONNECTED"
    client = RealtimeClient(
        realtime=mock_realtime,
        client=mock_websocket,
        debug=debug,
        is_ga_mode=False,
    )
    return client, mock_realtime


# ---------------------------------------------------------------------------
# Test 1: inject_conversation_history sends correct number of typed events
# ---------------------------------------------------------------------------

class TestHistoryInjectionSendsEvents:
    """inject_conversation_history should send one ConversationItemCreateEvent
    per non-system message and return the count of injected items."""

    @pytest.mark.asyncio
    async def test_injects_correct_count_with_typed_events(self):
        """Should send exactly one typed ConversationItemCreateEvent per
        user/assistant message and return the count."""
        store = ConversationStore()
        thread_id = "test-inject-count"
        store.add_message(thread_id, UnifiedMessage(role="user", content="Hello"))
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="Hi there"))
        store.add_message(thread_id, UnifiedMessage(role="user", content="How are you?"))

        client, mock_rt = _make_client_with_mock()

        result = await client.inject_conversation_history(thread_id, store=store)

        assert result == 3
        assert len(mock_rt.sent_events) == 3
        # All events should be typed ConversationItemCreateEvent objects
        for event in mock_rt.sent_events:
            assert isinstance(event, ConversationItemCreateEvent), (
                f"Expected ConversationItemCreateEvent, got {type(event).__name__}"
            )


# ---------------------------------------------------------------------------
# Test 2: User messages use input_text; assistant messages use text
# ---------------------------------------------------------------------------

class TestContentTypeMapping:
    """User messages should use 'input_text' content type and assistant
    messages should use 'text' content type in the injected events."""

    @pytest.mark.asyncio
    async def test_user_input_text_and_assistant_text(self):
        """User content type should be input_text; assistant should be text."""
        store = ConversationStore()
        thread_id = "test-content-types"
        store.add_message(thread_id, UnifiedMessage(role="user", content="question"))
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="answer"))

        client, mock_rt = _make_client_with_mock()

        await client.inject_conversation_history(thread_id, store=store)

        assert len(mock_rt.sent_events) == 2

        user_event = mock_rt.sent_events[0]
        assert user_event.item.role == "user"
        assert user_event.item.content[0].type == "input_text"
        assert user_event.item.content[0].text == "question"

        assistant_event = mock_rt.sent_events[1]
        assert assistant_event.item.role == "assistant"
        assert assistant_event.item.content[0].type == "text"
        assert assistant_event.item.content[0].text == "answer"


# ---------------------------------------------------------------------------
# Test 3: System messages are skipped
# ---------------------------------------------------------------------------

class TestSystemMessagesSkipped:
    """System messages should be excluded from injection since they are
    provided via session.update instructions instead."""

    @pytest.mark.asyncio
    async def test_system_messages_not_injected(self):
        """Only user and assistant messages should be injected."""
        store = ConversationStore()
        thread_id = "test-skip-system"
        store.add_message(thread_id, UnifiedMessage(role="system", content="You are helpful"))
        store.add_message(thread_id, UnifiedMessage(role="user", content="Hi"))
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="Hello!"))

        client, mock_rt = _make_client_with_mock()

        result = await client.inject_conversation_history(thread_id, store=store)

        assert result == 2
        assert len(mock_rt.sent_events) == 2
        roles = [evt.item.role for evt in mock_rt.sent_events]
        assert "system" not in roles
        assert roles == ["user", "assistant"]


# ---------------------------------------------------------------------------
# Test 4: Empty history returns 0 without error
# ---------------------------------------------------------------------------

class TestEmptyHistoryReturnsZero:
    """When there is no conversation history for a thread, the method
    should return 0 and not send any events."""

    @pytest.mark.asyncio
    async def test_empty_thread_returns_zero(self):
        """No messages for the thread should return 0."""
        store = ConversationStore()
        client, mock_rt = _make_client_with_mock()

        result = await client.inject_conversation_history("empty-thread", store=store)

        assert result == 0
        assert len(mock_rt.sent_events) == 0


# ---------------------------------------------------------------------------
# Test 5: Returns 0 when realtime is None
# ---------------------------------------------------------------------------

class TestRealtimeNoneReturnsZero:
    """When the realtime connection is None (disconnected), the method
    should return 0 immediately."""

    @pytest.mark.asyncio
    async def test_none_realtime_returns_zero(self):
        """inject_conversation_history should return 0 when realtime is None."""
        mock_websocket = MagicMock()
        mock_websocket.client_state = "CONNECTED"
        client = RealtimeClient(
            realtime=AsyncMock(),
            client=mock_websocket,
            debug=False,
            is_ga_mode=False,
        )
        # Force realtime to None to simulate disconnected state
        client.realtime = None

        store = ConversationStore()
        store.add_message("t1", UnifiedMessage(role="user", content="hello"))

        result = await client.inject_conversation_history("t1", store=store)
        assert result == 0
