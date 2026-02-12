"""
Tests for Task 57: Chat-to-Voice context switching integration.

Validates the end-to-end flow when a user starts with text chat and switches
to voice.  Conversation history accumulated via the ConversationStore must be
properly injected into the realtime session via conversation.item.create events.

Covered scenarios:
1. Full chat->voice flow: messages stored, then injected as ConversationItemCreateEvent
2. Chat messages appear in correct realtime format from get_realtime_items()
3. Empty chat history produces no events and returns 0
4. System messages excluded from realtime injection
5. Message ordering preserved across insertion and retrieval
6. Backward compatibility: ChatSession.context and ConversationStore work independently
"""

import sys
import os

import pytest

# Ensure the api directory is on the path so bare imports resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Module-level mocks: session.py imports chat which imports prompty and the
# Azure SDK.  We stub out the heavy dependencies so the test suite can run
# without Azure environment variables or SDK installs.
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
    """Mock for prompty.tracer.trace: handles both @trace and @trace(name=...)."""
    if fn is not None:
        return fn
    return lambda f: f


_mock_prompty_tracer.trace = _mock_trace

# Pre-seed sys.modules to avoid the real prompty imports
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

# Stub out the models module that session.py imports
_mock_models = MagicMock()
_mock_models.ClientMessage = MagicMock()
_mock_models.send_action = MagicMock(return_value={})
_mock_models.send_context = MagicMock(return_value={})
_mock_models.start_assistant = MagicMock(return_value={})
_mock_models.stop_assistant = MagicMock(return_value={})
_mock_models.stream_assistant = MagicMock(return_value={})
if "models" not in sys.modules:
    sys.modules["models"] = _mock_models

from conversation_store import ConversationStore, UnifiedMessage
from conversation_utils import user_message_to_unified, chat_response_to_unified
from voice import RealtimeClient, ConversationItemCreateEvent
from session import ChatSession, SessionManager


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockRealtimeConnection:
    """Mock realtime connection that records all sent events in order."""

    def __init__(self):
        self.sent_events = []

    async def send(self, event):
        self.sent_events.append(event)


class MockWebSocket:
    """Minimal mock of a FastAPI WebSocket for constructing RealtimeClient."""

    def __init__(self):
        self.sent = []
        self.client_state = "CONNECTED"

    async def send_json(self, data):
        self.sent.append(data)


def _make_client(thread_id="test-thread", debug=False):
    """Create a RealtimeClient backed by MockRealtimeConnection."""
    mock_rt = MockRealtimeConnection()
    mock_ws = MockWebSocket()
    client = RealtimeClient(
        realtime=mock_rt,
        client=mock_ws,
        debug=debug,
        is_ga_mode=False,
        thread_id=thread_id,
    )
    return client, mock_rt


def _build_chat_history(store, thread_id):
    """Populate a store with a realistic chat exchange using the
    conversation_utils helpers (the same path ChatSession.receive_chat uses)."""
    user1 = user_message_to_unified("I need a 10k ohm resistor", thread_id)
    store.add_message(thread_id, user1)

    assistant1 = chat_response_to_unified(
        "Sure! We have several 10k ohm resistors. Do you need through-hole or SMD?",
        thread_id,
    )
    store.add_message(thread_id, assistant1)

    user2 = user_message_to_unified("SMD, 0402 package", thread_id)
    store.add_message(thread_id, user2)

    assistant2 = chat_response_to_unified(
        "Here are three 0402 10k ohm resistors in stock.",
        thread_id,
    )
    store.add_message(thread_id, assistant2)

    return 4  # total non-system messages added


# ---------------------------------------------------------------------------
# Test 1: Full chat -> voice flow
# ---------------------------------------------------------------------------

class TestFullChatToVoiceFlow:
    """Simulate a complete chat session followed by a voice session switch.

    After chat messages are stored via the conversation_utils helpers (the same
    code path used by ChatSession.receive_chat), calling
    inject_conversation_history must send one ConversationItemCreateEvent per
    non-system message with correct content types.
    """

    @pytest.mark.asyncio
    async def test_full_flow_injects_typed_events(self):
        """Chat messages stored via utils should inject as typed
        ConversationItemCreateEvent objects with correct content types."""
        store = ConversationStore()
        thread_id = "chat-to-voice-full"
        expected_count = _build_chat_history(store, thread_id)

        client, mock_rt = _make_client(thread_id=thread_id)

        injected = await client.inject_conversation_history(thread_id, store=store)

        # Correct number of events injected
        assert injected == expected_count
        assert len(mock_rt.sent_events) == expected_count

        # All events are typed ConversationItemCreateEvent
        for event in mock_rt.sent_events:
            assert isinstance(event, ConversationItemCreateEvent), (
                f"Expected ConversationItemCreateEvent, got {type(event).__name__}"
            )

        # User messages have input_text content type
        user_events = [e for e in mock_rt.sent_events if e.item.role == "user"]
        for ue in user_events:
            assert ue.item.content[0].type == "input_text"

        # Assistant messages have text content type
        assistant_events = [e for e in mock_rt.sent_events if e.item.role == "assistant"]
        for ae in assistant_events:
            assert ae.item.content[0].type == "text"

    @pytest.mark.asyncio
    async def test_full_flow_content_preserved(self):
        """The text content of each injected event must match the original
        chat message content."""
        store = ConversationStore()
        thread_id = "chat-to-voice-content"
        _build_chat_history(store, thread_id)

        client, mock_rt = _make_client(thread_id=thread_id)
        await client.inject_conversation_history(thread_id, store=store)

        original_messages = [
            m for m in store.get_messages(thread_id) if m.role != "system"
        ]

        for original, event in zip(original_messages, mock_rt.sent_events):
            assert event.item.content[0].text == original.content


# ---------------------------------------------------------------------------
# Test 2: Chat messages appear in realtime format
# ---------------------------------------------------------------------------

class TestChatMessagesRealtimeFormat:
    """Verify that get_realtime_items returns properly structured dicts
    matching the conversation.item.create event payload schema."""

    def test_three_messages_produce_three_items(self):
        """3 non-system messages should produce exactly 3 realtime items."""
        store = ConversationStore()
        thread_id = "realtime-fmt"
        store.add_message(thread_id, UnifiedMessage(role="user", content="Hello"))
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="Hi!"))
        store.add_message(thread_id, UnifiedMessage(role="user", content="Help me"))

        items = store.get_realtime_items(thread_id)

        assert len(items) == 3

    def test_item_structure_is_valid(self):
        """Each realtime item must have the correct nested structure:
        type, item.type, item.role, item.content[0].type, item.content[0].text."""
        store = ConversationStore()
        thread_id = "realtime-struct"
        store.add_message(thread_id, UnifiedMessage(role="user", content="Query"))
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="Response"))
        store.add_message(thread_id, UnifiedMessage(role="user", content="Follow-up"))

        items = store.get_realtime_items(thread_id)

        for item in items:
            assert item["type"] == "conversation.item.create"
            assert item["item"]["type"] == "message"
            assert item["item"]["role"] in ("user", "assistant")
            assert len(item["item"]["content"]) == 1
            content_entry = item["item"]["content"][0]
            assert "type" in content_entry
            assert "text" in content_entry
            assert content_entry["type"] in ("input_text", "text")

    def test_user_items_use_input_text(self):
        """User messages must use content type 'input_text'."""
        store = ConversationStore()
        thread_id = "user-ct"
        store.add_message(thread_id, UnifiedMessage(role="user", content="test"))

        items = store.get_realtime_items(thread_id)
        assert items[0]["item"]["content"][0]["type"] == "input_text"

    def test_assistant_items_use_text(self):
        """Assistant messages must use content type 'text'."""
        store = ConversationStore()
        thread_id = "asst-ct"
        store.add_message(thread_id, UnifiedMessage(role="assistant", content="reply"))

        items = store.get_realtime_items(thread_id)
        assert items[0]["item"]["content"][0]["type"] == "text"


# ---------------------------------------------------------------------------
# Test 3: Empty chat history
# ---------------------------------------------------------------------------

class TestEmptyChatHistory:
    """When no messages exist for a thread, inject_conversation_history
    should send nothing and return 0."""

    @pytest.mark.asyncio
    async def test_no_events_sent_for_empty_thread(self):
        """inject_conversation_history with unknown thread_id sends 0 events."""
        store = ConversationStore()
        client, mock_rt = _make_client()

        result = await client.inject_conversation_history(
            "nonexistent-thread", store=store
        )

        assert result == 0
        assert len(mock_rt.sent_events) == 0

    @pytest.mark.asyncio
    async def test_cleared_thread_produces_zero(self):
        """After clearing a thread, injection should return 0."""
        store = ConversationStore()
        thread_id = "cleared"
        store.add_message(thread_id, UnifiedMessage(role="user", content="hi"))
        store.clear_thread(thread_id)

        client, mock_rt = _make_client()
        result = await client.inject_conversation_history(thread_id, store=store)

        assert result == 0
        assert len(mock_rt.sent_events) == 0


# ---------------------------------------------------------------------------
# Test 4: System messages excluded
# ---------------------------------------------------------------------------

class TestSystemMessagesExcluded:
    """System messages must be excluded from realtime injection because
    they are provided via session.update instructions instead."""

    def test_get_realtime_items_skips_system(self):
        """Only user and assistant messages should appear in realtime items."""
        store = ConversationStore()
        thread_id = "sys-excluded"
        store.add_message(
            thread_id,
            UnifiedMessage(role="system", content="You are a helpful assistant"),
        )
        store.add_message(thread_id, UnifiedMessage(role="user", content="Hi"))
        store.add_message(
            thread_id, UnifiedMessage(role="assistant", content="Hello!")
        )

        items = store.get_realtime_items(thread_id)

        assert len(items) == 2
        roles = [item["item"]["role"] for item in items]
        assert "system" not in roles
        assert roles == ["user", "assistant"]

    @pytest.mark.asyncio
    async def test_injection_skips_system_messages(self):
        """inject_conversation_history should only inject non-system messages."""
        store = ConversationStore()
        thread_id = "sys-inject"
        store.add_message(
            thread_id,
            UnifiedMessage(role="system", content="System prompt"),
        )
        store.add_message(thread_id, UnifiedMessage(role="user", content="Question"))
        store.add_message(
            thread_id, UnifiedMessage(role="assistant", content="Answer")
        )

        client, mock_rt = _make_client()
        result = await client.inject_conversation_history(thread_id, store=store)

        assert result == 2
        assert len(mock_rt.sent_events) == 2
        injected_roles = [evt.item.role for evt in mock_rt.sent_events]
        assert "system" not in injected_roles


# ---------------------------------------------------------------------------
# Test 5: Message ordering preserved
# ---------------------------------------------------------------------------

class TestMessageOrderingPreserved:
    """Messages must be injected in the same order they were added to the
    ConversationStore, preserving the conversational flow."""

    def test_get_realtime_items_preserves_order(self):
        """Items from get_realtime_items must match insertion order."""
        store = ConversationStore()
        thread_id = "ordering"
        contents = [
            ("user", "Message 1"),
            ("assistant", "Message 2"),
            ("user", "Message 3"),
            ("assistant", "Message 4"),
            ("user", "Message 5"),
        ]
        for role, content in contents:
            store.add_message(
                thread_id, UnifiedMessage(role=role, content=content)
            )

        items = store.get_realtime_items(thread_id)

        assert len(items) == 5
        for idx, item in enumerate(items):
            expected_role, expected_content = contents[idx]
            assert item["item"]["role"] == expected_role
            assert item["item"]["content"][0]["text"] == expected_content

    @pytest.mark.asyncio
    async def test_injection_preserves_order(self):
        """Events sent to realtime connection must match original order."""
        store = ConversationStore()
        thread_id = "inject-order"
        contents = [
            ("user", "First question"),
            ("assistant", "First answer"),
            ("user", "Second question"),
            ("assistant", "Second answer"),
            ("user", "Third question"),
        ]
        for role, content in contents:
            store.add_message(
                thread_id, UnifiedMessage(role=role, content=content)
            )

        client, mock_rt = _make_client()
        await client.inject_conversation_history(thread_id, store=store)

        assert len(mock_rt.sent_events) == 5
        for idx, event in enumerate(mock_rt.sent_events):
            expected_role, expected_content = contents[idx]
            assert event.item.role == expected_role
            assert event.item.content[0].text == expected_content


# ---------------------------------------------------------------------------
# Test 6: Backward compatibility -- ChatSession.context and ConversationStore
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """ChatSession.context (list of strings for prompty) and the
    ConversationStore (UnifiedMessage objects) must work independently.
    Both mechanisms should be usable within the same session without
    interfering with each other."""

    @pytest.mark.asyncio
    async def test_context_and_store_independent(self):
        """Adding messages to ConversationStore should not affect
        ChatSession.context, and vice versa."""
        store = ConversationStore()
        thread_id = "compat-test"

        # Simulate what receive_chat does: store UnifiedMessages
        user_msg = user_message_to_unified("What capacitors do you have?", thread_id)
        store.add_message(thread_id, user_msg)
        assistant_msg = chat_response_to_unified(
            "We carry ceramic, electrolytic, and tantalum capacitors.",
            thread_id,
        )
        store.add_message(thread_id, assistant_msg)

        # Simulate ChatSession context accumulation (the legacy string path)
        mock_ws = MagicMock()
        mock_ws.client_state = "CONNECTED"
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()
        session = ChatSession(mock_ws, thread_id)
        session.context.append("Context string from chat response")

        # ConversationStore has 2 messages
        realtime_items = store.get_realtime_items(thread_id)
        assert len(realtime_items) == 2

        # ChatSession.context has 1 entry
        assert len(session.context) == 1
        assert session.context[0] == "Context string from chat response"

        # They are independent -- modifying one does not affect the other
        session.context.append("Another context string")
        assert len(store.get_realtime_items(thread_id)) == 2  # unchanged
        assert len(session.context) == 2

    @pytest.mark.asyncio
    async def test_voice_context_writeback_separate_from_store(self):
        """add_voice_context writes to ChatSession.context but not to
        ConversationStore, confirming the two paths are independent."""
        store = ConversationStore()
        thread_id = "voice-compat"

        # Store a chat message via ConversationStore
        store.add_message(
            thread_id,
            UnifiedMessage(role="user", content="Test message", source="chat"),
        )

        # Create a ChatSession and add voice context
        mock_ws = MagicMock()
        mock_ws.client_state = "CONNECTED"
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()
        session = ChatSession(mock_ws, thread_id)
        session.add_voice_context("Voice transcript context")

        # ConversationStore still has exactly 1 message
        assert len(store.get_messages(thread_id)) == 1

        # ChatSession.context has the voice context entry
        assert len(session.context) == 1
        assert "Voice transcript context" in session.context
