"""
Tests for Task 50: UnifiedMessage model and ConversationStore.

Validates:
1. UnifiedMessage instantiation with auto-generated defaults
2. ConversationStore add/get with thread isolation
3. get_chat_format returns Chat Completions API format
4. get_realtime_items skips system messages and uses correct content types
5. clear_thread removes messages and unknown threads return empty lists
"""

import sys
import os
import time

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conversation_store import UnifiedMessage, ConversationStore


# ---------------------------------------------------------------------------
# Test 1: UnifiedMessage default and custom instantiation
# ---------------------------------------------------------------------------

class TestUnifiedMessageInstantiation:
    """UnifiedMessage should auto-generate id and timestamp when not provided,
    and accept custom values when explicitly set."""

    def test_defaults_auto_generated(self):
        """id and timestamp should be auto-generated; other fields default to empty."""
        before = time.time()
        msg = UnifiedMessage()
        after = time.time()

        assert msg.id is not None and len(msg.id) > 0
        assert msg.role == ""
        assert msg.content == ""
        assert before <= msg.timestamp <= after
        assert msg.source == ""
        assert msg.metadata is None

    def test_custom_values(self):
        """All fields should accept explicit values."""
        msg = UnifiedMessage(
            id="custom-id",
            role="user",
            content="Hello",
            timestamp=1000.0,
            source="chat",
            metadata={"key": "value"},
        )
        assert msg.id == "custom-id"
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp == 1000.0
        assert msg.source == "chat"
        assert msg.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# Test 2: ConversationStore add_message, get_messages, and thread isolation
# ---------------------------------------------------------------------------

class TestConversationStoreThreadIsolation:
    """Messages added to one thread must not leak into another thread.
    Unknown threads should return empty lists."""

    def test_add_and_get_messages(self):
        """Messages added via add_message are retrievable via get_messages."""
        store = ConversationStore()
        msg = UnifiedMessage(role="user", content="Hi", source="chat")
        store.add_message("thread-1", msg)

        messages = store.get_messages("thread-1")
        assert len(messages) == 1
        assert messages[0].content == "Hi"

    def test_thread_isolation(self):
        """Messages in thread-A must not appear in thread-B."""
        store = ConversationStore()
        store.add_message("A", UnifiedMessage(role="user", content="A msg"))
        store.add_message("B", UnifiedMessage(role="user", content="B msg"))

        a_msgs = store.get_messages("A")
        b_msgs = store.get_messages("B")
        assert len(a_msgs) == 1
        assert a_msgs[0].content == "A msg"
        assert len(b_msgs) == 1
        assert b_msgs[0].content == "B msg"

    def test_unknown_thread_returns_empty(self):
        """get_messages for a non-existent thread returns an empty list."""
        store = ConversationStore()
        assert store.get_messages("does-not-exist") == []


# ---------------------------------------------------------------------------
# Test 3: get_chat_format returns Chat Completions API format
# ---------------------------------------------------------------------------

class TestGetChatFormat:
    """get_chat_format should return list of dicts with 'role' and 'content' keys."""

    def test_chat_format_structure(self):
        """Each entry should be {'role': ..., 'content': ...}."""
        store = ConversationStore()
        store.add_message("t1", UnifiedMessage(role="system", content="You are helpful"))
        store.add_message("t1", UnifiedMessage(role="user", content="Hi"))
        store.add_message("t1", UnifiedMessage(role="assistant", content="Hello!"))

        result = store.get_chat_format("t1")
        assert result == [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

    def test_chat_format_unknown_thread(self):
        """Unknown thread returns empty list."""
        store = ConversationStore()
        assert store.get_chat_format("nope") == []


# ---------------------------------------------------------------------------
# Test 4: get_realtime_items skips system and uses correct content types
# ---------------------------------------------------------------------------

class TestGetRealtimeItems:
    """get_realtime_items should skip system messages and use 'input_text'
    for user messages and 'text' for assistant messages."""

    def test_skips_system_messages(self):
        """System role messages should not appear in realtime items."""
        store = ConversationStore()
        store.add_message("rt", UnifiedMessage(role="system", content="instructions"))
        store.add_message("rt", UnifiedMessage(role="user", content="hi"))

        items = store.get_realtime_items("rt")
        assert len(items) == 1
        assert items[0]["item"]["role"] == "user"

    def test_content_type_mapping(self):
        """User messages use 'input_text', assistant messages use 'text'."""
        store = ConversationStore()
        store.add_message("rt", UnifiedMessage(role="user", content="question"))
        store.add_message("rt", UnifiedMessage(role="assistant", content="answer"))

        items = store.get_realtime_items("rt")
        assert len(items) == 2

        user_item = items[0]
        assert user_item["type"] == "conversation.item.create"
        assert user_item["item"]["type"] == "message"
        assert user_item["item"]["role"] == "user"
        assert user_item["item"]["content"] == [{"type": "input_text", "text": "question"}]

        assistant_item = items[1]
        assert assistant_item["item"]["role"] == "assistant"
        assert assistant_item["item"]["content"] == [{"type": "text", "text": "answer"}]

    def test_realtime_items_unknown_thread(self):
        """Unknown thread returns empty list."""
        store = ConversationStore()
        assert store.get_realtime_items("nope") == []


# ---------------------------------------------------------------------------
# Test 5: clear_thread removes all messages
# ---------------------------------------------------------------------------

class TestClearThread:
    """clear_thread should remove all messages for a given thread, and be
    safe to call on non-existent threads."""

    def test_clear_removes_messages(self):
        """After clear_thread, get_messages should return empty list."""
        store = ConversationStore()
        store.add_message("c1", UnifiedMessage(role="user", content="hello"))
        store.add_message("c1", UnifiedMessage(role="assistant", content="hi"))
        assert len(store.get_messages("c1")) == 2

        store.clear_thread("c1")
        assert store.get_messages("c1") == []

    def test_clear_nonexistent_thread_is_safe(self):
        """Clearing an unknown thread should not raise."""
        store = ConversationStore()
        store.clear_thread("ghost")  # should not raise
