"""
Full round-trip integration test for Task 59: chat -> voice -> chat context persistence.

Validates the COMPLETE round-trip lifecycle of conversation context across modality
switches.  The unified ConversationStore and conversation_utils functions must
preserve all messages, metadata, ordering, and source annotations as a user
transitions from text chat to voice and back to text chat.

Covered scenarios:
1. Full round-trip: chat -> voice -> chat with content and metadata verification
2. Voice-first scenario: empty initial chat history, start directly in voice mode
3. System messages excluded from realtime items but present in chat format
4. Message ordering across multiple mode switches (chat -> voice -> chat -> voice)
5. Thread isolation: different thread_ids never leak messages across threads
"""

import os
import sys
import time
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
# ---------------------------------------------------------------------------

# Mock the 'chat' module so 'from chat import create_response' succeeds.
if "chat" not in sys.modules:
    _mock_chat = types.ModuleType("chat")
    _mock_chat.create_response = None  # type: ignore[attr-defined]
    sys.modules["chat"] = _mock_chat

# Mock the 'models' module so 'from models import ...' succeeds.
if "models" not in sys.modules:
    _mock_models = types.ModuleType("models")
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
    def _trace_decorator(fn=None, **kwargs):
        if fn is not None:
            return fn
        return lambda f: f
    _tracer_mod.trace = _trace_decorator  # type: ignore[attr-defined]

if not hasattr(_tracer_mod, "Tracer"):
    from unittest.mock import MagicMock as _MagicMock
    _tracer_cls = _MagicMock()
    _tracer_cls.SIGNATURE = "signature"
    _tracer_cls.INPUTS = "inputs"
    _tracer_cls.RESULT = "result"
    _span_cm = _MagicMock()
    _span_cm.__enter__ = _MagicMock(return_value=_MagicMock())
    _span_cm.__exit__ = _MagicMock(return_value=False)
    _tracer_cls.start.return_value = _span_cm
    _tracer_mod.Tracer = _tracer_cls  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Now safe to import project modules
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import MagicMock, AsyncMock

from conversation_store import ConversationStore, UnifiedMessage
from conversation_utils import (
    unified_to_chat_messages,
    unified_to_realtime_items,
    chat_response_to_unified,
    user_message_to_unified,
    realtime_transcript_to_unified,
)
from voice import RealtimeClient, ConversationItemCreateEvent
from session import ChatSession, SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockRealtimeConnection:
    """Mock realtime connection that records all sent events in order."""

    def __init__(self):
        self.sent_events = []

    async def send(self, event):
        self.sent_events.append(event)


class MockWebSocket:
    """Minimal mock of a FastAPI WebSocket."""

    def __init__(self):
        self.sent = []
        self.client_state = "CONNECTED"

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self):
        self.client_state = "DISCONNECTED"


def _fresh_store() -> ConversationStore:
    """Return a new, empty ConversationStore for test isolation."""
    return ConversationStore()


def _make_realtime_client(thread_id="test-thread", store=None):
    """Create a RealtimeClient backed by MockRealtimeConnection."""
    mock_rt = MockRealtimeConnection()
    mock_ws = MockWebSocket()
    client = RealtimeClient(
        realtime=mock_rt,
        client=mock_ws,
        debug=False,
        is_ga_mode=False,
        thread_id=thread_id,
    )
    if store is not None:
        client._conversation_store = store
    return client, mock_rt


# ---------------------------------------------------------------------------
# Test 1: Full round-trip -- chat -> voice -> chat
# ---------------------------------------------------------------------------

class TestFullRoundTrip:
    """Simulate the complete lifecycle: text chat messages are stored, then
    converted to realtime items for voice injection, voice transcripts are
    captured, and finally the entire history is available back in chat format
    with correct sources and ordering."""

    def test_chat_to_voice_to_chat_roundtrip(self):
        """Full round-trip: store chat messages, convert to realtime items,
        add voice transcripts, then retrieve ALL messages in chat format."""
        store = _fresh_store()
        thread_id = "roundtrip-full"

        # -- Phase 1: Text Chat --
        user1 = user_message_to_unified(
            text="I need a 10k ohm resistor for my project",
            thread_id=thread_id,
        )
        store.add_message(thread_id, user1)

        assistant1 = chat_response_to_unified(
            response_text="We have several 10k ohm resistors. Do you need through-hole or SMD?",
            thread_id=thread_id,
        )
        store.add_message(thread_id, assistant1)

        # Verify Phase 1: 2 messages in store, both with source="chat"
        phase1_msgs = store.get_messages(thread_id)
        assert len(phase1_msgs) == 2
        assert all(m.source == "chat" for m in phase1_msgs)

        # -- Phase 2: Switch to Voice (History Injection) --
        realtime_items = store.get_realtime_items(thread_id)
        assert len(realtime_items) == 2

        # User items use input_text, assistant items use text
        assert realtime_items[0]["item"]["role"] == "user"
        assert realtime_items[0]["item"]["content"][0]["type"] == "input_text"
        assert realtime_items[0]["item"]["content"][0]["text"] == user1.content

        assert realtime_items[1]["item"]["role"] == "assistant"
        assert realtime_items[1]["item"]["content"][0]["type"] == "text"
        assert realtime_items[1]["item"]["content"][0]["text"] == assistant1.content

        # Chronological order preserved
        assert realtime_items[0]["item"]["content"][0]["text"] == user1.content
        assert realtime_items[1]["item"]["content"][0]["text"] == assistant1.content

        # -- Phase 3: Voice Interaction --
        voice_user = realtime_transcript_to_unified(
            transcript="I need SMD, 0402 package please",
            role="user",
            thread_id=thread_id,
            realtime_item_id="rt-item-001",
        )
        store.add_message(thread_id, voice_user)

        voice_assistant = realtime_transcript_to_unified(
            transcript="Here are three 0402 10k ohm resistors we have in stock.",
            role="assistant",
            thread_id=thread_id,
            realtime_item_id="rt-item-002",
        )
        store.add_message(thread_id, voice_assistant)

        # Verify Phase 3: voice messages added to same thread
        phase3_msgs = store.get_messages(thread_id)
        assert len(phase3_msgs) == 4
        assert phase3_msgs[2].source == "realtime"
        assert phase3_msgs[2].metadata["audioPresent"] is True
        assert phase3_msgs[3].source == "realtime"
        assert phase3_msgs[3].metadata["audioPresent"] is True

        # -- Phase 4: Switch Back to Chat --
        chat_messages = store.get_chat_format(thread_id)
        assert len(chat_messages) == 4

        # Verify ALL messages present in chronological order
        assert chat_messages[0] == {"role": "user", "content": user1.content}
        assert chat_messages[1] == {"role": "assistant", "content": assistant1.content}
        assert chat_messages[2] == {"role": "user", "content": voice_user.content}
        assert chat_messages[3] == {"role": "assistant", "content": voice_assistant.content}

        # Verify source metadata on the raw messages
        raw_msgs = store.get_messages(thread_id)
        assert raw_msgs[0].source == "chat"
        assert raw_msgs[1].source == "chat"
        assert raw_msgs[2].source == "realtime"
        assert raw_msgs[3].source == "realtime"

        # Verify roles
        assert raw_msgs[0].role == "user"
        assert raw_msgs[1].role == "assistant"
        assert raw_msgs[2].role == "user"
        assert raw_msgs[3].role == "assistant"

    @pytest.mark.asyncio
    async def test_roundtrip_with_actual_injection(self):
        """End-to-end: store chat messages, inject into realtime client,
        capture voice transcripts, and verify full history is available."""
        store = _fresh_store()
        thread_id = "roundtrip-inject"

        # Phase 1: Text Chat
        user1 = user_message_to_unified("What microcontrollers do you carry?", thread_id)
        store.add_message(thread_id, user1)

        assistant1 = chat_response_to_unified(
            "We carry Arduino, Raspberry Pi, and ESP32 boards.",
            thread_id,
        )
        store.add_message(thread_id, assistant1)

        # Phase 2: Inject into realtime client
        client, mock_rt = _make_realtime_client(thread_id=thread_id, store=store)
        injected = await client.inject_conversation_history(thread_id, store=store)
        assert injected == 2

        # Verify injected events are typed correctly
        assert len(mock_rt.sent_events) == 2
        for event in mock_rt.sent_events:
            assert isinstance(event, ConversationItemCreateEvent)

        assert mock_rt.sent_events[0].item.role == "user"
        assert mock_rt.sent_events[0].item.content[0].type == "input_text"
        assert mock_rt.sent_events[1].item.role == "assistant"
        assert mock_rt.sent_events[1].item.content[0].type == "text"

        # Phase 3: Voice transcripts captured
        voice_user = realtime_transcript_to_unified(
            transcript="Tell me more about ESP32",
            role="user",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_user)

        voice_assistant = realtime_transcript_to_unified(
            transcript="The ESP32 is a dual-core processor with WiFi and Bluetooth.",
            role="assistant",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_assistant)

        # Phase 4: Full history in chat format
        chat_messages = store.get_chat_format(thread_id)
        assert len(chat_messages) == 4
        assert chat_messages[0]["content"] == "What microcontrollers do you carry?"
        assert chat_messages[1]["content"] == "We carry Arduino, Raspberry Pi, and ESP32 boards."
        assert chat_messages[2]["content"] == "Tell me more about ESP32"
        assert chat_messages[3]["content"] == "The ESP32 is a dual-core processor with WiFi and Bluetooth."

        # Also available via standalone utility function
        raw_msgs = store.get_messages(thread_id)
        util_chat = unified_to_chat_messages(raw_msgs)
        assert util_chat == chat_messages


# ---------------------------------------------------------------------------
# Test 2: Voice-first scenario (empty initial chat history)
# ---------------------------------------------------------------------------

class TestVoiceFirstScenario:
    """When a user starts directly in voice mode with no prior text chat,
    the system should still store voice transcripts and make them available
    in chat format for a subsequent switch to text chat."""

    def test_voice_first_then_chat(self):
        """Starting with voice, then switching to chat, should work correctly."""
        store = _fresh_store()
        thread_id = "voice-first"

        # No prior chat messages -- verify empty
        assert store.get_messages(thread_id) == []
        assert store.get_chat_format(thread_id) == []
        assert store.get_realtime_items(thread_id) == []

        # Voice interaction
        voice_user = realtime_transcript_to_unified(
            transcript="Hi, I need help with my order",
            role="user",
            thread_id=thread_id,
            realtime_item_id="rt-voice-1",
        )
        store.add_message(thread_id, voice_user)

        voice_assistant = realtime_transcript_to_unified(
            transcript="Of course! What is your order number?",
            role="assistant",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_assistant)

        # Switch to chat -- voice history should be available
        chat_messages = store.get_chat_format(thread_id)
        assert len(chat_messages) == 2
        assert chat_messages[0] == {
            "role": "user",
            "content": "Hi, I need help with my order",
        }
        assert chat_messages[1] == {
            "role": "assistant",
            "content": "Of course! What is your order number?",
        }

        # Now continue with chat
        chat_user = user_message_to_unified(
            text="My order number is ORD-12345",
            thread_id=thread_id,
        )
        store.add_message(thread_id, chat_user)

        chat_assistant = chat_response_to_unified(
            response_text="Let me look up order ORD-12345 for you.",
            thread_id=thread_id,
        )
        store.add_message(thread_id, chat_assistant)

        # Full history with correct sources
        all_msgs = store.get_messages(thread_id)
        assert len(all_msgs) == 4
        assert all_msgs[0].source == "realtime"
        assert all_msgs[1].source == "realtime"
        assert all_msgs[2].source == "chat"
        assert all_msgs[3].source == "chat"

        # Chat format includes everything
        full_chat = store.get_chat_format(thread_id)
        assert len(full_chat) == 4

    @pytest.mark.asyncio
    async def test_empty_history_injection_returns_zero(self):
        """Injecting conversation history from an empty store returns 0."""
        store = _fresh_store()
        client, mock_rt = _make_realtime_client(thread_id="empty-inject")

        result = await client.inject_conversation_history(
            "empty-inject", store=store
        )

        assert result == 0
        assert len(mock_rt.sent_events) == 0


# ---------------------------------------------------------------------------
# Test 3: System messages excluded from realtime but present in chat format
# ---------------------------------------------------------------------------

class TestSystemMessageHandling:
    """System messages should be excluded from realtime items (they are
    injected via session.update instructions) but should remain in the
    chat format output."""

    def test_system_message_excluded_from_realtime_present_in_chat(self):
        """System messages should appear in get_chat_format but not in
        get_realtime_items."""
        store = _fresh_store()
        thread_id = "sys-msg-handling"

        # Add system message
        system_msg = UnifiedMessage(
            role="system",
            content="You are a helpful electronics parts assistant.",
            source="chat",
        )
        store.add_message(thread_id, system_msg)

        # Add user and assistant messages
        user_msg = user_message_to_unified("What is an FPGA?", thread_id)
        store.add_message(thread_id, user_msg)

        assistant_msg = chat_response_to_unified(
            "An FPGA is a Field-Programmable Gate Array.",
            thread_id,
        )
        store.add_message(thread_id, assistant_msg)

        # Chat format includes system message
        chat_format = store.get_chat_format(thread_id)
        assert len(chat_format) == 3
        assert chat_format[0]["role"] == "system"
        assert chat_format[0]["content"] == "You are a helpful electronics parts assistant."

        # Realtime items exclude system message
        realtime_items = store.get_realtime_items(thread_id)
        assert len(realtime_items) == 2
        roles = [item["item"]["role"] for item in realtime_items]
        assert "system" not in roles
        assert roles == ["user", "assistant"]

    @pytest.mark.asyncio
    async def test_system_message_excluded_from_injection(self):
        """When injecting conversation history, system messages should be skipped."""
        store = _fresh_store()
        thread_id = "sys-inject-roundtrip"

        store.add_message(thread_id, UnifiedMessage(
            role="system",
            content="System instructions here",
            source="chat",
        ))
        store.add_message(thread_id, UnifiedMessage(
            role="user",
            content="Hello",
            source="chat",
        ))
        store.add_message(thread_id, UnifiedMessage(
            role="assistant",
            content="Hi there!",
            source="chat",
        ))

        client, mock_rt = _make_realtime_client(thread_id=thread_id)
        injected = await client.inject_conversation_history(thread_id, store=store)

        assert injected == 2
        assert len(mock_rt.sent_events) == 2
        injected_roles = [evt.item.role for evt in mock_rt.sent_events]
        assert "system" not in injected_roles

        # But after voice interaction and switch back to chat, system message is still there
        voice_user = realtime_transcript_to_unified(
            transcript="Can you elaborate?",
            role="user",
            thread_id=thread_id,
        )
        store.add_message(thread_id, voice_user)

        full_chat = store.get_chat_format(thread_id)
        assert len(full_chat) == 4
        assert full_chat[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Test 4: Message ordering across multiple mode switches
# ---------------------------------------------------------------------------

class TestMultipleModeSwitches:
    """Conversation context must maintain strict chronological ordering
    even across multiple chat -> voice -> chat -> voice transitions."""

    def test_four_phase_ordering(self):
        """chat -> voice -> chat -> voice: all messages in correct order."""
        store = _fresh_store()
        thread_id = "multi-switch"

        # Phase 1: Chat
        m1 = user_message_to_unified("Phase 1 chat user", thread_id)
        store.add_message(thread_id, m1)
        m2 = chat_response_to_unified("Phase 1 chat assistant", thread_id)
        store.add_message(thread_id, m2)

        # Phase 2: Voice
        m3 = realtime_transcript_to_unified(
            "Phase 2 voice user", "user", thread_id
        )
        store.add_message(thread_id, m3)
        m4 = realtime_transcript_to_unified(
            "Phase 2 voice assistant", "assistant", thread_id
        )
        store.add_message(thread_id, m4)

        # Phase 3: Chat again
        m5 = user_message_to_unified("Phase 3 chat user", thread_id)
        store.add_message(thread_id, m5)
        m6 = chat_response_to_unified("Phase 3 chat assistant", thread_id)
        store.add_message(thread_id, m6)

        # Phase 4: Voice again
        m7 = realtime_transcript_to_unified(
            "Phase 4 voice user", "user", thread_id
        )
        store.add_message(thread_id, m7)
        m8 = realtime_transcript_to_unified(
            "Phase 4 voice assistant", "assistant", thread_id
        )
        store.add_message(thread_id, m8)

        # Verify all 8 messages in order
        all_msgs = store.get_messages(thread_id)
        assert len(all_msgs) == 8

        expected_contents = [
            "Phase 1 chat user",
            "Phase 1 chat assistant",
            "Phase 2 voice user",
            "Phase 2 voice assistant",
            "Phase 3 chat user",
            "Phase 3 chat assistant",
            "Phase 4 voice user",
            "Phase 4 voice assistant",
        ]
        for i, msg in enumerate(all_msgs):
            assert msg.content == expected_contents[i], (
                f"Message {i} content mismatch: expected '{expected_contents[i]}', "
                f"got '{msg.content}'"
            )

        # Verify sources alternate correctly
        expected_sources = [
            "chat", "chat",
            "realtime", "realtime",
            "chat", "chat",
            "realtime", "realtime",
        ]
        for i, msg in enumerate(all_msgs):
            assert msg.source == expected_sources[i], (
                f"Message {i} source mismatch: expected '{expected_sources[i]}', "
                f"got '{msg.source}'"
            )

        # Chat format preserves full ordering
        chat_format = store.get_chat_format(thread_id)
        assert len(chat_format) == 8
        for i, entry in enumerate(chat_format):
            assert entry["content"] == expected_contents[i]

        # Realtime items also preserve ordering
        realtime_items = store.get_realtime_items(thread_id)
        assert len(realtime_items) == 8
        for i, item in enumerate(realtime_items):
            assert item["item"]["content"][0]["text"] == expected_contents[i]

    def test_realtime_items_at_midpoint_only_include_prior_messages(self):
        """When switching to voice mid-conversation, only messages added
        BEFORE the switch should appear in realtime items."""
        store = _fresh_store()
        thread_id = "midpoint-check"

        # Chat phase
        store.add_message(thread_id, user_message_to_unified("Chat msg 1", thread_id))
        store.add_message(thread_id, chat_response_to_unified("Chat reply 1", thread_id))

        # Snapshot realtime items at this point (simulating voice switch)
        items_at_switch = store.get_realtime_items(thread_id)
        assert len(items_at_switch) == 2

        # Voice phase adds more messages
        store.add_message(thread_id, realtime_transcript_to_unified(
            "Voice msg 1", "user", thread_id
        ))

        # Now realtime items include the voice message too
        items_after_voice = store.get_realtime_items(thread_id)
        assert len(items_after_voice) == 3

        # The snapshot taken at switch time still had only 2
        assert len(items_at_switch) == 2


# ---------------------------------------------------------------------------
# Test 5: Thread isolation
# ---------------------------------------------------------------------------

class TestThreadIsolation:
    """Messages stored in one thread_id must never appear in queries
    for a different thread_id."""

    def test_threads_do_not_leak(self):
        """Two concurrent threads should maintain completely separate histories."""
        store = _fresh_store()
        thread_a = "thread-alpha"
        thread_b = "thread-beta"

        # Thread A: chat messages
        store.add_message(thread_a, user_message_to_unified(
            "Alpha user message", thread_a
        ))
        store.add_message(thread_a, chat_response_to_unified(
            "Alpha assistant response", thread_a
        ))

        # Thread B: voice messages
        store.add_message(thread_b, realtime_transcript_to_unified(
            "Beta voice user", "user", thread_b
        ))
        store.add_message(thread_b, realtime_transcript_to_unified(
            "Beta voice assistant", "assistant", thread_b
        ))

        # Thread A has only its messages
        a_msgs = store.get_messages(thread_a)
        assert len(a_msgs) == 2
        assert all(m.source == "chat" for m in a_msgs)
        assert a_msgs[0].content == "Alpha user message"
        assert a_msgs[1].content == "Alpha assistant response"

        # Thread B has only its messages
        b_msgs = store.get_messages(thread_b)
        assert len(b_msgs) == 2
        assert all(m.source == "realtime" for m in b_msgs)
        assert b_msgs[0].content == "Beta voice user"
        assert b_msgs[1].content == "Beta voice assistant"

        # Chat format also isolated
        a_chat = store.get_chat_format(thread_a)
        b_chat = store.get_chat_format(thread_b)
        assert len(a_chat) == 2
        assert len(b_chat) == 2
        assert a_chat[0]["content"] == "Alpha user message"
        assert b_chat[0]["content"] == "Beta voice user"

        # Realtime items also isolated
        a_rt = store.get_realtime_items(thread_a)
        b_rt = store.get_realtime_items(thread_b)
        assert len(a_rt) == 2
        assert len(b_rt) == 2

    def test_clearing_one_thread_does_not_affect_other(self):
        """Clearing one thread should leave other threads untouched."""
        store = _fresh_store()
        thread_a = "iso-clear-a"
        thread_b = "iso-clear-b"

        store.add_message(thread_a, UnifiedMessage(
            role="user", content="Thread A message", source="chat"
        ))
        store.add_message(thread_b, UnifiedMessage(
            role="user", content="Thread B message", source="realtime"
        ))

        store.clear_thread(thread_a)

        assert store.get_messages(thread_a) == []
        assert len(store.get_messages(thread_b)) == 1
        assert store.get_messages(thread_b)[0].content == "Thread B message"

    @pytest.mark.asyncio
    async def test_injection_only_affects_target_thread(self):
        """inject_conversation_history for thread A should not inject
        messages from thread B."""
        store = _fresh_store()
        thread_a = "inject-iso-a"
        thread_b = "inject-iso-b"

        store.add_message(thread_a, UnifiedMessage(
            role="user", content="Thread A question", source="chat"
        ))
        store.add_message(thread_b, UnifiedMessage(
            role="user", content="Thread B question", source="chat"
        ))

        client, mock_rt = _make_realtime_client(thread_id=thread_a)
        injected = await client.inject_conversation_history(thread_a, store=store)

        assert injected == 1
        assert len(mock_rt.sent_events) == 1
        assert mock_rt.sent_events[0].item.content[0].text == "Thread A question"


# ---------------------------------------------------------------------------
# Test: Utility functions produce equivalent output to store methods
# ---------------------------------------------------------------------------

class TestUtilityFunctionEquivalence:
    """The standalone utility functions in conversation_utils should produce
    the same output as the ConversationStore methods."""

    def test_unified_to_chat_messages_matches_get_chat_format(self):
        """unified_to_chat_messages() and store.get_chat_format() should
        return identical results for the same message set."""
        store = _fresh_store()
        thread_id = "util-equiv"

        store.add_message(thread_id, user_message_to_unified("Q1", thread_id))
        store.add_message(thread_id, chat_response_to_unified("A1", thread_id))
        store.add_message(thread_id, realtime_transcript_to_unified(
            "Q2 voice", "user", thread_id
        ))
        store.add_message(thread_id, realtime_transcript_to_unified(
            "A2 voice", "assistant", thread_id
        ))

        raw_msgs = store.get_messages(thread_id)
        from_util = unified_to_chat_messages(raw_msgs)
        from_store = store.get_chat_format(thread_id)

        assert from_util == from_store

    def test_unified_to_realtime_items_matches_get_realtime_items(self):
        """unified_to_realtime_items() and store.get_realtime_items() should
        return identical results."""
        store = _fresh_store()
        thread_id = "util-rt-equiv"

        store.add_message(thread_id, user_message_to_unified("Hello", thread_id))
        store.add_message(thread_id, chat_response_to_unified("Hi!", thread_id))

        raw_msgs = store.get_messages(thread_id)
        from_util = unified_to_realtime_items(raw_msgs)
        from_store = store.get_realtime_items(thread_id)

        assert from_util == from_store
