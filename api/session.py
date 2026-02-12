import json
from typing import Dict, List, Union
from fastapi import WebSocket
from prompty.tracer import trace
from prompty.tracer import Tracer
from fastapi.websockets import WebSocketState
from chat import create_response
from models import (
    ClientMessage,
    send_action,
    send_context,
    start_assistant,
    stop_assistant,
    stream_assistant,
)

from voice import RealtimeClient, Message
from conversation_store import conversation_store
from conversation_utils import user_message_to_unified, chat_response_to_unified


class ChatSession:
    def __init__(self, client: WebSocket, thread_id: str):
        self.client = client
        self.thread_id = thread_id
        self.realtime: Union[RealtimeClient, None] = None
        self.context: List[str] = []  # Keep for prompty compatibility

    async def send_message(self, message: Message):
        if (
            self.client is not None
            and self.client.client_state != WebSocketState.DISCONNECTED
        ):
            await self.client.send_json(message.model_dump())

    def add_realtime(self, realtime: RealtimeClient):
        self.realtime = realtime

    def detach_client(self):
        """Disconnect the chat WebSocket without destroying the session.

        This allows the session (and its accumulated context) to survive
        a chat WebSocket disconnect so that a subsequent voice or chat
        reconnection can reuse the context.
        """
        self.client = None

    def detach_voice(self):
        """Disconnect the realtime voice client without destroying the session.

        Called when a voice session ends so the underlying chat session
        remains available for continued text interaction.
        """
        self.realtime = None

    def get_chat_messages(self) -> List[dict]:
        """Get messages in Chat Completions API format."""
        return conversation_store.get_chat_format(self.thread_id)

    def get_unified_messages(self):
        """Get full UnifiedMessage history."""
        return conversation_store.get_messages(self.thread_id)

    def add_voice_context(self, context: str):
        """Append voice transcript context to the shared session context.

        This ensures that voice conversation history is available to
        subsequent chat or voice interactions within the same session.
        """
        self.context.append(context)

    def is_closed(self):
        client_closed = (
            self.client is None
            or self.client.client_state == WebSocketState.DISCONNECTED
        )
        realtime_closed = (
            self.realtime is None
            or self.realtime is None
            or self.realtime.closed
        )
        return client_closed and realtime_closed

    @trace
    async def receive_chat(self):
        while (
            self.client is not None
            and self.client.client_state != WebSocketState.DISCONNECTED
        ):
            with Tracer.start("chat_turn") as t:
                t(Tracer.SIGNATURE, "api.session.ChatSession.start_chat")
                message = await self.client.receive_json()
                msg = ClientMessage(**message)

                # Store user message as UnifiedMessage
                user_msg = user_message_to_unified(
                    text=msg.text,
                    thread_id=self.thread_id,
                    name=msg.name
                )
                conversation_store.add_message(self.thread_id, user_msg)

                t(
                    Tracer.INPUTS,
                    {
                        "request": msg.text,
                        "image": msg.image is not None,
                    },
                )

                # start assistant
                if self.client.client_state != WebSocketState.DISCONNECTED:
                    await self.client.send_json(start_assistant())

                # create response
                response = await create_response(
                    msg.name, msg.text, self.context, msg.image
                )

                # unpack response
                text = response["response"]
                context = response["context"]
                call = response["call"]

                # Store assistant response as UnifiedMessage
                assistant_msg = chat_response_to_unified(
                    response_text=text,
                    thread_id=self.thread_id,
                    metadata={"context": context}
                )
                conversation_store.add_message(self.thread_id, assistant_msg)

                # send response
                if self.client.client_state != WebSocketState.DISCONNECTED:
                    await self.client.send_json(stream_assistant(text))
                    await self.client.send_json(stop_assistant())

                    # send context
                    await self.client.send_json(send_context(context))
                    await self.client.send_json(
                        send_action("call", json.dumps({"score": call}))
                    )
                self.context.append(response["context"])
                t(
                    Tracer.RESULT,
                    {
                        "response": text,
                        "context": context,
                        "call": call,
                    },
                )

    async def close(self):
        if self.client is not None:
            try:
                await self.client.close()
            except Exception:
                pass
        if self.realtime:
            await self.realtime.close()


class SessionManager:
    sessions: Dict[str, ChatSession] = {}

    @classmethod
    async def create_session(cls, thread_id: str, socket: WebSocket) -> ChatSession:
        session = ChatSession(socket, thread_id)
        cls.sessions[thread_id] = session
        return session

    @classmethod
    def get_session(cls, thread_id: str):
        if thread_id in cls.sessions:
            return cls.sessions[thread_id]
        return None

    @classmethod
    async def close_session(cls, thread_id: str):
        if thread_id in cls.sessions:
            await cls.sessions[thread_id].close()
            del cls.sessions[thread_id]

    @classmethod
    async def clear_sessions(cls):
        for thread_id in cls.sessions:
            try:
                await cls.sessions[thread_id].close()
            except Exception as e:
                print(f"Error closing session ({thread_id})", e)
        cls.sessions = {}

    @classmethod
    async def clear_closed_sessions(cls):
        threads = cls.sessions.keys()
        for thread_id in threads:
            if cls.sessions[thread_id].is_closed():
                try:
                    del cls.sessions[thread_id]
                except Exception as e:
                    print(f"Error closing session ({thread_id})", e)