"""
Unified conversation store for text (Chat Completions) and voice (Realtime API) modes.

Provides:
- UnifiedMessage: A dataclass representing a single message from any modality.
- ConversationStore: A thread-safe, in-memory store keyed by thread_id that can
  export history in both Chat Completions and Realtime API formats.
- conversation_store: Module-level singleton instance.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class UnifiedMessage:
    """A single message that can originate from chat or realtime voice."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = ""  # "system" | "user" | "assistant"
    content: str = ""  # Text content or transcript
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # "chat" | "realtime"
    metadata: Optional[dict] = None  # realtimeItemId, audioPresent, etc.


class ConversationStore:
    """Thread-safe, in-memory conversation history keyed by thread_id."""

    def __init__(self):
        self._conversations: Dict[str, List[UnifiedMessage]] = {}
        self._lock = threading.RLock()

    def get_messages(self, thread_id: str) -> List[UnifiedMessage]:
        """Return full message history for *thread_id*."""
        with self._lock:
            return list(self._conversations.get(thread_id, []))

    def add_message(self, thread_id: str, message: UnifiedMessage) -> None:
        """Append *message* to the history for *thread_id*."""
        with self._lock:
            if thread_id not in self._conversations:
                self._conversations[thread_id] = []
            self._conversations[thread_id].append(message)

    def get_chat_format(self, thread_id: str) -> List[dict]:
        """Convert history to Chat Completions API format.

        Returns a list of ``{"role": ..., "content": ...}`` dicts.
        """
        messages = self.get_messages(thread_id)
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def get_realtime_items(self, thread_id: str) -> List[dict]:
        """Convert history to ``conversation.item.create`` event payloads.

        System messages are skipped (they are injected via ``session.update``
        instructions instead).  User messages use content type ``input_text``;
        assistant messages use ``text``.
        """
        messages = self.get_messages(thread_id)
        items: List[dict] = []
        for msg in messages:
            if msg.role == "system":
                continue
            content_type = "input_text" if msg.role == "user" else "text"
            items.append(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": msg.role,
                        "content": [{"type": content_type, "text": msg.content}],
                    },
                }
            )
        return items

    def clear_thread(self, thread_id: str) -> None:
        """Remove all messages for *thread_id*."""
        with self._lock:
            self._conversations.pop(thread_id, None)


# Module-level singleton
conversation_store = ConversationStore()
