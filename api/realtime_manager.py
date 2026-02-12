"""
Unified realtime connection manager for Azure OpenAI voice sessions.

Centralises the GA vs Preview client creation logic that was previously
inline in main.py, tracks active realtime connections per thread_id,
and provides helpers for reading/writing chat context through both the
legacy SessionManager and the unified ConversationStore.
"""

from typing import Any, Dict, List, Optional

from openai import AsyncAzureOpenAI

from conversation_store import conversation_store
from conversation_utils import realtime_transcript_to_unified
from session import SessionManager


class RealtimeConnectionManager:
    """Factory and lifecycle manager for Azure OpenAI realtime connections.

    Responsibilities:
      - Create AsyncAzureOpenAI clients configured for GA or Preview mode.
      - Track active realtime connections keyed by thread_id.
      - Provide helpers to read/write chat context via SessionManager.
      - Store voice transcripts in the unified ConversationStore for
        cross-mode context persistence.
      - Clean up stale (closed) connections.
    """

    # GA mode uses a placeholder api_version because we override the
    # WebSocket URL entirely via websocket_base_url.
    _GA_API_VERSION = "2024-10-01-preview"
    _PREVIEW_API_VERSION = "2025-04-01-preview"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_mode: str = "ga",
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.deployment = deployment
        self.api_mode = api_mode.lower()
        self._connections: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    @property
    def is_ga_mode(self) -> bool:
        return self.api_mode == "ga"

    @property
    def api_version(self) -> str:
        return self._GA_API_VERSION if self.is_ga_mode else self._PREVIEW_API_VERSION

    def create_client(self) -> AsyncAzureOpenAI:
        """Build an AsyncAzureOpenAI client for the configured API mode.

        GA mode:
            Sets ``websocket_base_url`` to ``wss://{host}/openai/v1`` so the
            SDK constructs ``wss://{host}/openai/v1/realtime?model={deployment}``
            (no ``api-version`` query param).

        Preview mode:
            Uses default SDK behaviour which constructs
            ``wss://{host}/openai/realtime?api-version=...&deployment=...``.

        Returns:
            An ``AsyncAzureOpenAI`` instance ready for ``.beta.realtime.connect()``
            or ``.realtime.connect()`` calls.
        """
        if self.is_ga_mode:
            ws_base = (
                self.endpoint.replace("https://", "wss://").rstrip("/")
                + "/openai/v1"
            )
            return AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
                websocket_base_url=ws_base,
            )
        else:
            return AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def register_connection(self, thread_id: str, connection: Any) -> None:
        """Register an active realtime connection for a thread."""
        self._connections[thread_id] = connection

    def unregister_connection(self, thread_id: str) -> None:
        """Remove a realtime connection from tracking.

        Safe to call with a thread_id that is not currently tracked.
        """
        self._connections.pop(thread_id, None)

    def get_connection(self, thread_id: str) -> Optional[Any]:
        """Return the active connection for *thread_id*, or ``None``."""
        return self._connections.get(thread_id)

    def cleanup_stale_connections(self) -> None:
        """Remove connections whose underlying client reports ``closed``."""
        stale_ids = [
            tid
            for tid, conn in self._connections.items()
            if getattr(conn, "closed", False)
        ]
        for tid in stale_ids:
            del self._connections[tid]

    # ------------------------------------------------------------------
    # SessionManager integration
    # ------------------------------------------------------------------

    @staticmethod
    def get_chat_context(thread_id: str) -> List[str]:
        """Retrieve accumulated chat context for *thread_id*.

        Returns an empty list when no session exists.
        """
        session = SessionManager.get_session(thread_id)
        if session and session.context:
            return list(session.context)
        return []

    @staticmethod
    def write_voice_context(thread_id: str, context: str) -> None:
        """Append a voice transcript context entry to the shared session.

        No-op if no session exists for *thread_id*.
        """
        session = SessionManager.get_session(thread_id)
        if session:
            session.add_voice_context(context)

    @staticmethod
    def store_voice_message(
        thread_id: str,
        transcript: str,
        role: str,
        realtime_item_id: Optional[str] = None,
    ) -> None:
        """Store a voice transcript as a UnifiedMessage and update legacy context.

        Writes to both the unified ConversationStore (for cross-mode context
        persistence) and the legacy session context (for prompty compatibility).

        Args:
            thread_id: Conversation thread ID.
            transcript: Transcribed text from the realtime API.
            role: ``"user"`` or ``"assistant"``.
            realtime_item_id: Optional item ID from the realtime API.
        """
        # Store in unified format
        msg = realtime_transcript_to_unified(
            transcript=transcript,
            role=role,
            thread_id=thread_id,
            realtime_item_id=realtime_item_id,
        )
        conversation_store.add_message(thread_id, msg)

        # Also write to legacy session context for backward compatibility
        session = SessionManager.get_session(thread_id)
        if session:
            context_str = f"{role}: {transcript}"
            session.add_voice_context(context_str)

    @staticmethod
    def get_unified_context(thread_id: str) -> list:
        """Retrieve structured conversation history for *thread_id*.

        Returns a list of UnifiedMessage objects from the ConversationStore,
        or an empty list when no messages exist.
        """
        return conversation_store.get_messages(thread_id)
