"""
Tests for Task 51: Format translation utility functions.

Validates:
1. unified_to_chat_messages preserves role/content and handles empty lists
2. unified_to_realtime_items filters system, maps content types, handles empty
3. chat_response_to_unified creates valid UnifiedMessage with correct defaults
4. user_message_to_unified handles name and no-name cases
5. realtime_transcript_to_unified sets source, audioPresent, and optional item id
"""

import sys
import os
import time

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conversation_store import UnifiedMessage
from conversation_utils import (
    unified_to_chat_messages,
    unified_to_realtime_items,
    chat_response_to_unified,
    user_message_to_unified,
    realtime_transcript_to_unified,
)


# ---------------------------------------------------------------------------
# Test 1: unified_to_chat_messages
# ---------------------------------------------------------------------------

class TestUnifiedToChatMessages:
    """unified_to_chat_messages should convert UnifiedMessage list to Chat
    Completions API format, preserving role and content."""

    def test_preserves_role_and_content(self):
        """Each message should map to {'role': ..., 'content': ...}."""
        messages = [
            UnifiedMessage(role="system", content="You are helpful", source="chat"),
            UnifiedMessage(role="user", content="Hello", source="chat"),
            UnifiedMessage(role="assistant", content="Hi there!", source="chat"),
        ]
        result = unified_to_chat_messages(messages)
        assert result == [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

    def test_empty_list_returns_empty(self):
        """An empty input list should return an empty output list."""
        assert unified_to_chat_messages([]) == []


# ---------------------------------------------------------------------------
# Test 2: unified_to_realtime_items
# ---------------------------------------------------------------------------

class TestUnifiedToRealtimeItems:
    """unified_to_realtime_items should skip system messages, use 'input_text'
    for user role, 'text' for assistant role, and handle empty lists."""

    def test_filters_out_system_messages(self):
        """System messages should not appear in the output."""
        messages = [
            UnifiedMessage(role="system", content="instructions", source="chat"),
            UnifiedMessage(role="user", content="hi", source="chat"),
            UnifiedMessage(role="assistant", content="hello", source="chat"),
        ]
        items = unified_to_realtime_items(messages)
        assert len(items) == 2
        roles = [item["item"]["role"] for item in items]
        assert "system" not in roles

    def test_user_gets_input_text_type(self):
        """User messages should use content type 'input_text'."""
        messages = [UnifiedMessage(role="user", content="question", source="chat")]
        items = unified_to_realtime_items(messages)
        assert len(items) == 1
        item = items[0]
        assert item["type"] == "conversation.item.create"
        assert item["item"]["type"] == "message"
        assert item["item"]["role"] == "user"
        assert item["item"]["content"] == [{"type": "input_text", "text": "question"}]

    def test_assistant_gets_text_type(self):
        """Assistant messages should use content type 'text'."""
        messages = [UnifiedMessage(role="assistant", content="answer", source="chat")]
        items = unified_to_realtime_items(messages)
        assert len(items) == 1
        assert items[0]["item"]["content"] == [{"type": "text", "text": "answer"}]

    def test_empty_list_returns_empty(self):
        """An empty input list should return an empty output list."""
        assert unified_to_realtime_items([]) == []


# ---------------------------------------------------------------------------
# Test 3: chat_response_to_unified
# ---------------------------------------------------------------------------

class TestChatResponseToUnified:
    """chat_response_to_unified should create a valid UnifiedMessage with
    source='chat' and correct defaults."""

    def test_creates_valid_message(self):
        """Should produce a UnifiedMessage with source='chat', role='assistant'."""
        before = time.time()
        msg = chat_response_to_unified("Hello!", thread_id="t1")
        after = time.time()

        assert msg.role == "assistant"
        assert msg.content == "Hello!"
        assert msg.source == "chat"
        assert msg.id is not None and len(msg.id) > 0
        assert before <= msg.timestamp <= after
        assert msg.metadata == {}

    def test_with_custom_metadata(self):
        """Custom metadata should be preserved on the message."""
        meta = {"model": "gpt-4o", "tokens": 42}
        msg = chat_response_to_unified("response", thread_id="t1", metadata=meta)
        assert msg.metadata == {"model": "gpt-4o", "tokens": 42}


# ---------------------------------------------------------------------------
# Test 4: user_message_to_unified
# ---------------------------------------------------------------------------

class TestUserMessageToUnified:
    """user_message_to_unified should create a user-role UnifiedMessage and
    handle the optional name parameter."""

    def test_with_name(self):
        """When name is provided it should appear in metadata."""
        msg = user_message_to_unified("Hello", thread_id="t1", name="Brad")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.source == "chat"
        assert msg.metadata == {"name": "Brad"}

    def test_without_name(self):
        """When name is omitted metadata should be None."""
        msg = user_message_to_unified("Hello", thread_id="t1")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.metadata is None


# ---------------------------------------------------------------------------
# Test 5: realtime_transcript_to_unified
# ---------------------------------------------------------------------------

class TestRealtimeTranscriptToUnified:
    """realtime_transcript_to_unified should create a UnifiedMessage with
    source='realtime', audioPresent=True, and optional realtime item id."""

    def test_source_and_audio_present(self):
        """source should be 'realtime' and audioPresent should be True."""
        msg = realtime_transcript_to_unified(
            "hello there", role="user", thread_id="t1"
        )
        assert msg.source == "realtime"
        assert msg.role == "user"
        assert msg.content == "hello there"
        assert msg.metadata["audioPresent"] is True

    def test_with_realtime_item_id(self):
        """When realtime_item_id is provided it should appear in metadata."""
        msg = realtime_transcript_to_unified(
            "answer", role="assistant", thread_id="t1", realtime_item_id="item-abc"
        )
        assert msg.metadata["realtimeItemId"] == "item-abc"
        assert msg.metadata["audioPresent"] is True
        assert msg.source == "realtime"
