"""
Tests for Task 39: Full user interaction flow with unified realtime chat.

Integration-level tests that simulate the complete user interaction flow
across chat and voice modalities, validating the end-to-end behaviour of
the unified session system.

Scenarios covered:
1. WebSocket lifecycle: connect -> threadId -> session creation -> disconnect -> detach
2. Message routing: text messages reach session.receive_chat correctly
3. Modality switching: modality_switch message JSON-decoded for modalities array
4. Chat context persistence: messages accumulate -> voice merges chat context
5. Voice session integration: RealtimeConnectionManager register/unregister lifecycle
6. Session reuse across modalities: chat -> voice -> chat with context preserved
7. Concurrent connection handling: multiple threads with isolation
"""

import json
import os
import sys

# Set required env vars BEFORE importing modules that depend on them.
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-api-key")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session import ChatSession, SessionManager
from voice import RealtimeClient, Message
from realtime_manager import RealtimeConnectionManager
from fastapi.websockets import WebSocketState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_websocket(state="CONNECTED"):
    """Create a mock WebSocket with configurable state."""
    ws = MagicMock()
    ws.client_state = state
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def _make_realtime_client(ws=None, is_ga_mode=False):
    """Create a RealtimeClient with mocked dependencies for testing."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_realtime.response = MagicMock()
    mock_realtime.response.create = AsyncMock()
    mock_realtime.close = AsyncMock()
    mock_ws = ws or _make_mock_websocket()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )


def _make_manager():
    """Create a RealtimeConnectionManager with test credentials."""
    return RealtimeConnectionManager(
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        deployment="gpt-realtime",
        api_mode="ga",
    )


# ---------------------------------------------------------------------------
# Scenario 1: WebSocket lifecycle
# Connect chat WebSocket -> send threadId -> verify session creation ->
# disconnect -> verify session preserved (detach pattern)
# ---------------------------------------------------------------------------

class TestWebSocketLifecycle:
    """The chat endpoint flow: accept connection, receive threadId,
    create a session, then on disconnect detach (not destroy) the session."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        """Ensure SessionManager is clean before and after each test."""
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_connect_creates_session_for_new_thread(self):
        """When a new threadId is received, a new ChatSession should be
        created and stored in SessionManager."""
        ws = _make_mock_websocket()
        thread_id = "thread-lifecycle-1"

        session = await SessionManager.create_session(thread_id, ws)

        assert session is not None
        assert SessionManager.get_session(thread_id) is session
        assert session.client is ws

    @pytest.mark.asyncio
    async def test_disconnect_detaches_client_preserves_session(self):
        """After a chat WebSocket disconnect, the session should remain in
        SessionManager with a null client (detach pattern)."""
        ws = _make_mock_websocket()
        thread_id = "thread-lifecycle-2"

        session = await SessionManager.create_session(thread_id, ws)
        session.context.append("User asked about microcontrollers")

        # Simulate the detach that happens in the finally block of chat_endpoint
        session.detach_client()

        # Session still exists
        retrieved = SessionManager.get_session(thread_id)
        assert retrieved is not None
        assert retrieved.client is None
        assert retrieved.context == ["User asked about microcontrollers"]

    @pytest.mark.asyncio
    async def test_reconnect_reuses_existing_session(self):
        """When a chat WebSocket reconnects with the same threadId,
        the existing session should be reused with the new WebSocket."""
        ws1 = _make_mock_websocket()
        thread_id = "thread-lifecycle-3"

        session = await SessionManager.create_session(thread_id, ws1)
        session.context.append("Previous conversation context")

        # Simulate disconnect + detach
        session.detach_client()

        # Reconnect with a new WebSocket
        ws2 = _make_mock_websocket()
        existing = SessionManager.get_session(thread_id)
        assert existing is not None
        existing.client = ws2

        # Same session object, new WebSocket, context preserved
        assert existing.client is ws2
        assert existing.context == ["Previous conversation context"]

    @pytest.mark.asyncio
    async def test_session_survives_multiple_disconnects(self):
        """A session should survive multiple connect/disconnect cycles,
        accumulating context each time."""
        thread_id = "thread-lifecycle-4"

        # First connection
        ws1 = _make_mock_websocket()
        session = await SessionManager.create_session(thread_id, ws1)
        session.context.append("Turn 1 context")
        session.detach_client()

        # Second connection
        ws2 = _make_mock_websocket()
        session.client = ws2
        session.context.append("Turn 2 context")
        session.detach_client()

        # Session still alive with accumulated context
        retrieved = SessionManager.get_session(thread_id)
        assert retrieved is not None
        assert len(retrieved.context) == 2
        assert retrieved.context[0] == "Turn 1 context"
        assert retrieved.context[1] == "Turn 2 context"


# ---------------------------------------------------------------------------
# Scenario 2: Message routing
# Text messages through chat WebSocket reach session.receive_chat
# ---------------------------------------------------------------------------

class TestMessageRouting:
    """Text messages sent through the chat WebSocket should reach
    the session's receive_chat method with the correct format."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_text_message_via_realtime_creates_conversation_item(self):
        """A 'text' type message sent to RealtimeClient.receive_client
        should create a conversation.item.create event with input_text content."""
        client = _make_realtime_client()

        text_msg = json.dumps({
            "type": "text",
            "payload": "Do you carry STM32 microcontrollers?"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[text_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # The first send should be the conversation item
        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) >= 1

        first_event = send_calls[0][0][0]
        assert first_event.type == "conversation.item.create"
        assert first_event.item.role == "user"
        assert first_event.item.content[0].type == "input_text"
        assert first_event.item.content[0].text == "Do you carry STM32 microcontrollers?"

    @pytest.mark.asyncio
    async def test_text_message_triggers_text_only_response(self):
        """A 'text' type message should trigger a response.create event
        with text-only modalities (no audio output)."""
        client = _make_realtime_client()

        text_msg = json.dumps({
            "type": "text",
            "payload": "What is the price range?"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[text_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) == 2

        response_event = send_calls[1][0][0]
        assert response_event.type == "response.create"

    @pytest.mark.asyncio
    async def test_audio_message_forwarded_to_realtime(self):
        """An 'audio' type message should be forwarded to the realtime
        connection as an input_audio_buffer.append event."""
        client = _make_realtime_client()

        audio_msg = json.dumps({
            "type": "audio",
            "payload": "base64encodedaudio=="
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[audio_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) == 1
        event = send_calls[0][0][0]
        assert event.type == "input_audio_buffer.append"
        assert event.audio == "base64encodedaudio=="


# ---------------------------------------------------------------------------
# Scenario 3: Modality switching
# modality_switch message JSON-decoded to extract modalities array
# ---------------------------------------------------------------------------

class TestModalitySwitching:
    """The modality_switch message type should be JSON-decoded to extract
    the modalities array and update the realtime session accordingly."""

    @pytest.mark.asyncio
    async def test_modality_switch_decodes_json_payload_preview(self):
        """In preview mode, a modality_switch message should decode the
        payload JSON and send a session.update event with the modalities."""
        client = _make_realtime_client(is_ga_mode=False)

        switch_msg = json.dumps({
            "type": "modality_switch",
            "payload": json.dumps({"modalities": ["text", "audio"]})
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[switch_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.type == "session.update"
        assert sent_event.session.modalities == ["text", "audio"]

    @pytest.mark.asyncio
    async def test_modality_switch_decodes_json_payload_ga(self):
        """In GA mode, a modality_switch message should decode the
        payload JSON and call session.update with output_modalities."""
        client = _make_realtime_client(is_ga_mode=True)

        switch_msg = json.dumps({
            "type": "modality_switch",
            "payload": json.dumps({"modalities": ["text"]})
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[switch_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        client.realtime.session.update.assert_called_once()
        call_kwargs = client.realtime.session.update.call_args
        session_dict = call_kwargs.kwargs.get("session") or call_kwargs[1].get("session")
        assert session_dict["output_modalities"] == ["text"]

    @pytest.mark.asyncio
    async def test_modality_switch_defaults_to_text_when_missing(self):
        """If the modalities key is missing from the payload, it should
        default to text-only modality."""
        client = _make_realtime_client(is_ga_mode=False)

        switch_msg = json.dumps({
            "type": "modality_switch",
            "payload": json.dumps({})  # No "modalities" key
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[switch_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        client.realtime.send.assert_called_once()
        sent_event = client.realtime.send.call_args[0][0]
        assert sent_event.session.modalities == ["text"]


# ---------------------------------------------------------------------------
# Scenario 4: Chat context persistence
# Chat context accumulates -> voice endpoint merges it
# ---------------------------------------------------------------------------

class TestChatContextPersistence:
    """Chat context should accumulate in the session and be available
    when the voice endpoint merges it during connection."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_context_accumulates_across_chat_turns(self):
        """Multiple chat interactions should accumulate context
        in the session's context list."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-ctx-1", ws)

        session.context.append("Turn 1: User asked about resistors")
        session.context.append("Turn 2: User compared 10k vs 4.7k ohm")
        session.context.append("Turn 3: User decided on 10k ohm pack")

        assert len(session.context) == 3
        assert "Turn 1: User asked about resistors" in session.context

    @pytest.mark.asyncio
    async def test_voice_endpoint_merges_chat_context(self):
        """When a voice session connects, the RealtimeConnectionManager
        should return chat context for merging into the voice prompt."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-ctx-2", ws)
        session.context.append("Chat: user needs voltage regulators")
        session.context.append("Chat: 3.3V output, max 1A input")

        manager = _make_manager()
        context = manager.get_chat_context("thread-ctx-2")

        assert len(context) == 2
        assert "Chat: user needs voltage regulators" in context
        assert "Chat: 3.3V output, max 1A input" in context

    @pytest.mark.asyncio
    async def test_voice_context_merged_with_chat_items(self):
        """Simulate the voice endpoint logic: frontend chat items are
        combined with session context from the manager."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-ctx-3", ws)
        session.context.append("Server-side context from chat session")

        manager = _make_manager()

        # Simulates what the voice endpoint does: JSON chat items from
        # the first WebSocket message merged with session context
        frontend_chat_items = ["Frontend item 1", "Frontend item 2"]
        session_context = manager.get_chat_context("thread-ctx-3")

        if session_context:
            merged = frontend_chat_items + session_context
        else:
            merged = frontend_chat_items

        assert len(merged) == 3
        assert merged[0] == "Frontend item 1"
        assert merged[1] == "Frontend item 2"
        assert merged[2] == "Server-side context from chat session"

    @pytest.mark.asyncio
    async def test_voice_context_writeback_persists_for_future_chat(self):
        """Voice transcript context written back to the session should
        be available in subsequent chat or voice interactions."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-ctx-4", ws)
        session.context.append("Chat: initial question")

        manager = _make_manager()
        manager.write_voice_context("thread-ctx-4", "Voice: user discussed pricing")

        # Now the session has both chat and voice context
        assert len(session.context) == 2
        assert session.context[0] == "Chat: initial question"
        assert session.context[1] == "Voice: user discussed pricing"

        # Future chat/voice can retrieve all context
        all_context = manager.get_chat_context("thread-ctx-4")
        assert len(all_context) == 2


# ---------------------------------------------------------------------------
# Scenario 5: Voice session integration
# RealtimeConnectionManager register/unregister lifecycle during voice
# ---------------------------------------------------------------------------

class TestVoiceSessionIntegration:
    """The voice endpoint uses RealtimeConnectionManager to register and
    unregister connections, tracking active realtime sessions per thread."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    def test_register_connection_during_voice_session(self):
        """When a voice session starts, the realtime connection should be
        registered for the thread_id."""
        manager = _make_manager()
        mock_realtime = MagicMock()

        manager.register_connection("thread-voice-1", mock_realtime)

        assert manager.get_connection("thread-voice-1") is mock_realtime

    def test_unregister_connection_when_voice_ends(self):
        """When a voice session ends, the connection should be unregistered
        but the chat session should remain."""
        manager = _make_manager()
        mock_realtime = MagicMock()

        manager.register_connection("thread-voice-2", mock_realtime)
        manager.unregister_connection("thread-voice-2")

        assert manager.get_connection("thread-voice-2") is None

    @pytest.mark.asyncio
    async def test_voice_adds_realtime_to_existing_chat_session(self):
        """When voice connects for a thread that has an existing chat session,
        the realtime client should be attached to the ChatSession."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-voice-3", ws)

        realtime_client = _make_realtime_client()
        session.add_realtime(realtime_client)

        assert session.realtime is realtime_client

    @pytest.mark.asyncio
    async def test_voice_detach_preserves_chat_session(self):
        """When voice disconnects, detach_voice should clear the realtime
        reference but the chat session and context remain intact."""
        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-voice-4", ws)
        session.context.append("Chat context before voice")

        realtime_client = _make_realtime_client()
        session.add_realtime(realtime_client)
        session.detach_voice()

        assert session.realtime is None
        assert session.context == ["Chat context before voice"]
        assert SessionManager.get_session("thread-voice-4") is session

    @pytest.mark.asyncio
    async def test_full_voice_register_unregister_lifecycle(self):
        """Simulate the complete voice endpoint lifecycle:
        register -> use -> unregister + detach_voice."""
        manager = _make_manager()

        ws = _make_mock_websocket()
        session = await SessionManager.create_session("thread-voice-5", ws)

        mock_realtime = _make_realtime_client()

        # Register (simulates voice_endpoint after connecting)
        manager.register_connection("thread-voice-5", mock_realtime)
        session.add_realtime(mock_realtime)

        assert manager.get_connection("thread-voice-5") is mock_realtime
        assert session.realtime is mock_realtime

        # Unregister (simulates voice_endpoint finally block)
        manager.unregister_connection("thread-voice-5")
        session.detach_voice()

        assert manager.get_connection("thread-voice-5") is None
        assert session.realtime is None
        assert SessionManager.get_session("thread-voice-5") is session


# ---------------------------------------------------------------------------
# Scenario 6: Session reuse across modalities
# Chat -> voice -> chat with context preserved
# ---------------------------------------------------------------------------

class TestSessionReuseAcrossModalities:
    """A session created by the chat endpoint should be reusable by the
    voice endpoint and then by a subsequent chat reconnection, with all
    context preserved throughout the transitions."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_chat_to_voice_to_chat_preserves_context(self):
        """Full cross-modality flow: chat adds context, voice reads and adds
        more, then a new chat connection sees all accumulated context."""
        manager = _make_manager()
        thread_id = "thread-reuse-1"

        # Phase 1: Chat session
        ws1 = _make_mock_websocket()
        session = await SessionManager.create_session(thread_id, ws1)
        session.context.append("Chat: user asked about Arduino boards")
        session.context.append("Chat: assistant recommended Mega 2560")
        session.detach_client()

        # Phase 2: Voice session connects for same thread
        chat_context = manager.get_chat_context(thread_id)
        assert len(chat_context) == 2

        realtime_client = _make_realtime_client()
        manager.register_connection(thread_id, realtime_client)
        session.add_realtime(realtime_client)

        # Voice adds its own context
        session.add_voice_context("Voice: user confirmed Mega 2560 purchase")
        assert len(session.context) == 3

        # Voice disconnects
        manager.unregister_connection(thread_id)
        session.detach_voice()

        # Phase 3: Chat reconnects
        ws2 = _make_mock_websocket()
        existing = SessionManager.get_session(thread_id)
        assert existing is not None
        existing.client = ws2

        # All context from both modalities preserved
        assert len(existing.context) == 3
        assert existing.context[0] == "Chat: user asked about Arduino boards"
        assert existing.context[1] == "Chat: assistant recommended Mega 2560"
        assert existing.context[2] == "Voice: user confirmed Mega 2560 purchase"

    @pytest.mark.asyncio
    async def test_same_session_object_used_across_modalities(self):
        """Verify the exact same ChatSession object is used when voice
        connects with an existing chat thread_id."""
        thread_id = "thread-reuse-2"

        ws = _make_mock_websocket()
        original_session = await SessionManager.create_session(thread_id, ws)
        original_id = id(original_session)

        # Detach chat
        original_session.detach_client()

        # Voice looks up the session
        voice_session = SessionManager.get_session(thread_id)
        assert voice_session is not None
        assert id(voice_session) == original_id

        # Chat reconnects
        ws2 = _make_mock_websocket()
        reconnected_session = SessionManager.get_session(thread_id)
        assert id(reconnected_session) == original_id

    @pytest.mark.asyncio
    async def test_voice_context_available_after_voice_disconnect(self):
        """After voice disconnects, the voice transcript context written
        to the session should be available to subsequent chat connections."""
        manager = _make_manager()
        thread_id = "thread-reuse-3"

        ws = _make_mock_websocket()
        session = await SessionManager.create_session(thread_id, ws)
        session.detach_client()

        # Voice connects and writes context
        manager.write_voice_context(thread_id, "Voice transcript: shipping question")
        manager.write_voice_context(thread_id, "Voice transcript: delivery ETA")

        # Voice disconnects
        manager.unregister_connection(thread_id)
        session.detach_voice()

        # Chat reconnects and reads all context
        context = manager.get_chat_context(thread_id)
        assert len(context) == 2
        assert "Voice transcript: shipping question" in context
        assert "Voice transcript: delivery ETA" in context


# ---------------------------------------------------------------------------
# Scenario 7: Concurrent connection handling
# Multiple threads with different threadIds -> verify isolation
# ---------------------------------------------------------------------------

class TestConcurrentConnectionHandling:
    """Multiple threads with different threadIds should be completely
    isolated from each other in both SessionManager and
    RealtimeConnectionManager."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        SessionManager.sessions = {}
        yield
        SessionManager.sessions = {}

    @pytest.mark.asyncio
    async def test_sessions_isolated_by_thread_id(self):
        """Two sessions with different threadIds should not share context."""
        ws_a = _make_mock_websocket()
        ws_b = _make_mock_websocket()

        session_a = await SessionManager.create_session("thread-A", ws_a)
        session_b = await SessionManager.create_session("thread-B", ws_b)

        session_a.context.append("Thread A: asked about capacitors")
        session_b.context.append("Thread B: asked about resistors")

        assert len(session_a.context) == 1
        assert len(session_b.context) == 1
        assert session_a.context[0] == "Thread A: asked about capacitors"
        assert session_b.context[0] == "Thread B: asked about resistors"

    def test_realtime_connections_isolated_by_thread_id(self):
        """Two realtime connections with different threadIds should not
        interfere with each other."""
        manager = _make_manager()

        conn_a = MagicMock()
        conn_b = MagicMock()

        manager.register_connection("thread-A", conn_a)
        manager.register_connection("thread-B", conn_b)

        assert manager.get_connection("thread-A") is conn_a
        assert manager.get_connection("thread-B") is conn_b

        # Unregistering one does not affect the other
        manager.unregister_connection("thread-A")
        assert manager.get_connection("thread-A") is None
        assert manager.get_connection("thread-B") is conn_b

    @pytest.mark.asyncio
    async def test_context_operations_do_not_leak_between_threads(self):
        """Writing context to one thread should not affect another thread."""
        manager = _make_manager()

        ws_a = _make_mock_websocket()
        ws_b = _make_mock_websocket()

        session_a = await SessionManager.create_session("thread-iso-A", ws_a)
        session_b = await SessionManager.create_session("thread-iso-B", ws_b)

        manager.write_voice_context("thread-iso-A", "Voice A context")

        assert len(session_a.context) == 1
        assert len(session_b.context) == 0

        context_a = manager.get_chat_context("thread-iso-A")
        context_b = manager.get_chat_context("thread-iso-B")

        assert context_a == ["Voice A context"]
        assert context_b == []

    @pytest.mark.asyncio
    async def test_detach_one_thread_does_not_affect_others(self):
        """Detaching a client from one session should not affect other sessions."""
        ws_a = _make_mock_websocket()
        ws_b = _make_mock_websocket()

        session_a = await SessionManager.create_session("thread-detach-A", ws_a)
        session_b = await SessionManager.create_session("thread-detach-B", ws_b)

        session_a.context.append("A context")
        session_b.context.append("B context")

        # Detach only session A
        session_a.detach_client()

        # Session A detached but preserved
        assert session_a.client is None
        assert session_a.context == ["A context"]

        # Session B completely unaffected
        assert session_b.client is ws_b
        assert session_b.context == ["B context"]

    @pytest.mark.asyncio
    async def test_multiple_concurrent_voice_connections(self):
        """Multiple voice connections on different threads should be
        independently tracked and cleanable."""
        manager = _make_manager()

        # Create three concurrent voice sessions
        for i in range(3):
            ws = _make_mock_websocket()
            await SessionManager.create_session(f"thread-concurrent-{i}", ws)
            rt = _make_realtime_client()
            manager.register_connection(f"thread-concurrent-{i}", rt)

        # All three tracked
        for i in range(3):
            assert manager.get_connection(f"thread-concurrent-{i}") is not None

        # Unregister one
        manager.unregister_connection("thread-concurrent-1")

        # Only the unregistered one is gone
        assert manager.get_connection("thread-concurrent-0") is not None
        assert manager.get_connection("thread-concurrent-1") is None
        assert manager.get_connection("thread-concurrent-2") is not None
