"""
Format translation utilities for converting between UnifiedMessage and
API-specific message formats (Chat Completions, Realtime API).

Provides standalone functions that operate on UnifiedMessage lists without
requiring a ConversationStore instance, enabling use in request/response
pipelines and middleware.
"""

import time
import uuid
from typing import List, Optional

from conversation_store import UnifiedMessage


def unified_to_chat_messages(messages: List[UnifiedMessage]) -> List[dict]:
    """Convert a list of UnifiedMessage objects to Chat Completions API format.

    Returns a list of ``{"role": ..., "content": ...}`` dicts suitable for
    passing directly to the Chat Completions API ``messages`` parameter.
    """
    return [{"role": msg.role, "content": msg.content} for msg in messages]


def unified_to_realtime_items(messages: List[UnifiedMessage]) -> List[dict]:
    """Convert a list of UnifiedMessage objects to ``conversation.item.create``
    event payloads for the Realtime API.

    System messages are skipped because they are injected via
    ``session.update`` instructions instead.  User messages use content type
    ``input_text``; assistant messages use ``text``.
    """
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


def chat_response_to_unified(
    response_text: str,
    thread_id: str,
    role: str = "assistant",
    metadata: Optional[dict] = None,
) -> UnifiedMessage:
    """Convert a chat API response string to a UnifiedMessage.

    Parameters
    ----------
    response_text:
        The text content returned by the Chat Completions API.
    thread_id:
        The conversation thread this message belongs to.
    role:
        The role for the message (defaults to ``"assistant"``).
    metadata:
        Optional dictionary of extra metadata to attach.

    Returns
    -------
    UnifiedMessage with ``source="chat"``.
    """
    return UnifiedMessage(
        id=str(uuid.uuid4()),
        role=role,
        content=response_text,
        timestamp=time.time(),
        source="chat",
        metadata=metadata or {},
    )


def user_message_to_unified(
    text: str,
    thread_id: str,
    name: Optional[str] = None,
) -> UnifiedMessage:
    """Convert user text input to a UnifiedMessage.

    Parameters
    ----------
    text:
        The user's message content.
    thread_id:
        The conversation thread this message belongs to.
    name:
        Optional display name for the user.  When provided it is stored
        in ``metadata["name"]``.

    Returns
    -------
    UnifiedMessage with ``role="user"`` and ``source="chat"``.
    """
    metadata = {"name": name} if name else None
    return UnifiedMessage(
        id=str(uuid.uuid4()),
        role="user",
        content=text,
        timestamp=time.time(),
        source="chat",
        metadata=metadata,
    )


def realtime_transcript_to_unified(
    transcript: str,
    role: str,
    thread_id: str,
    realtime_item_id: Optional[str] = None,
) -> UnifiedMessage:
    """Convert a Realtime API transcript to a UnifiedMessage.

    Parameters
    ----------
    transcript:
        The transcribed text from the Realtime API.
    role:
        ``"user"`` or ``"assistant"``.
    thread_id:
        The conversation thread this message belongs to.
    realtime_item_id:
        Optional Realtime API item identifier.

    Returns
    -------
    UnifiedMessage with ``source="realtime"`` and ``metadata["audioPresent"]=True``.
    """
    metadata: dict = {}
    if realtime_item_id:
        metadata["realtimeItemId"] = realtime_item_id
    metadata["audioPresent"] = True
    return UnifiedMessage(
        id=str(uuid.uuid4()),
        role=role,
        content=transcript,
        timestamp=time.time(),
        source="realtime",
        metadata=metadata,
    )
