import json
import asyncio
from typing import Literal, Optional, Union
from fastapi import WebSocket
from prompty.tracer import trace
from fastapi import WebSocketDisconnect
from pydantic import BaseModel
from fastapi.websockets import WebSocketState

from conversation_store import ConversationStore, conversation_store as _default_store
from conversation_utils import realtime_transcript_to_unified

# ---------------------------------------------------------------------------
# Preview (beta) imports -- used when AZURE_VOICE_API_MODE="preview"
# These remain the primary types for backward compatibility.
# ---------------------------------------------------------------------------
from openai.resources.beta.realtime.realtime import (
    AsyncRealtimeConnection,
)
from openai.types.beta.realtime.session_update_event import (
    Session,
    SessionTurnDetection,
    SessionInputAudioTranscription,
    # SessionTool,
)
from openai.types.beta.realtime import (
    ErrorEvent,
    SessionCreatedEvent,
    SessionUpdatedEvent,
    ConversationCreatedEvent,
    ConversationItemCreatedEvent,
    ConversationItemInputAudioTranscriptionCompletedEvent,
    ConversationItemInputAudioTranscriptionDeltaEvent,
    ConversationItemInputAudioTranscriptionFailedEvent,
    ConversationItemTruncatedEvent,
    ConversationItemDeletedEvent,
    InputAudioBufferCommittedEvent,
    InputAudioBufferClearedEvent,
    InputAudioBufferSpeechStartedEvent,
    InputAudioBufferSpeechStoppedEvent,
    ResponseCreatedEvent,
    ResponseDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseAudioTranscriptDeltaEvent,
    ResponseAudioTranscriptDoneEvent,
    ResponseAudioDeltaEvent,
    ResponseAudioDoneEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    RateLimitsUpdatedEvent,
)

from openai.types.beta.realtime import (
    SessionUpdateEvent,
    InputAudioBufferAppendEvent,
    # InputAudioBufferCommitEvent,
    # InputAudioBufferClearEvent,
    ConversationItemCreateEvent,
    # ConversationItemTruncateEvent,
    # ConversationItemDeleteEvent,
    ResponseCreateEvent,
    # ResponseCancelEvent,
)

from openai.types.beta.realtime import (
    ConversationItem,
    ConversationItemContent,
)

# ---------------------------------------------------------------------------
# GA imports -- used when AZURE_VOICE_API_MODE="ga"
# Available in openai>=1.59.0. The GA module lives at openai.resources.realtime
# (without .beta) and types at openai.types.realtime (without .beta).
#
# Key differences in GA types vs beta:
#   - Session config uses RealtimeSessionCreateRequest with nested audio
#     structure (replaces flat Session + SessionTurnDetection)
#   - Event name strings changed (handled in Task 28):
#       response.audio.delta             -> response.output_audio.delta
#       response.text.delta              -> response.output_text.delta
#       response.audio_transcript.delta  -> response.output_audio_transcript.delta
#   - New events: conversation.item.added, conversation.item.done
#
# GA types are imported with aliased names to avoid collisions with the beta
# types used above. The try/except ensures backward compatibility with older
# SDK versions that lack the GA module.
# ---------------------------------------------------------------------------
try:
    from openai.resources.realtime.realtime import (
        AsyncRealtimeConnection as AsyncRealtimeConnectionGA,
    )
    from openai.types.realtime import (
        RealtimeSessionCreateRequest as GASessionConfig,
        RealtimeAudioConfig as GAAudioConfig,
        SessionUpdateEvent as GASessionUpdateEvent,
        InputAudioBufferAppendEvent as GAInputAudioBufferAppendEvent,
        ConversationItemCreateEvent as GAConversationItemCreateEvent,
        ResponseCreateEvent as GAResponseCreateEvent,
        ResponseDoneEvent as GAResponseDoneEvent,
        ResponseAudioDeltaEvent as GAResponseAudioDeltaEvent,
        ResponseAudioTranscriptDeltaEvent as GAResponseAudioTranscriptDeltaEvent,
        ResponseAudioTranscriptDoneEvent as GAResponseAudioTranscriptDoneEvent,
        ConversationItemCreatedEvent as GAConversationItemCreatedEvent,
        ConversationItemInputAudioTranscriptionCompletedEvent as GATranscriptionCompletedEvent,
        InputAudioBufferSpeechStartedEvent as GAInputAudioBufferSpeechStartedEvent,
        RateLimitsUpdatedEvent as GARateLimitsUpdatedEvent,
    )

    GA_AVAILABLE = True
except ImportError:
    GA_AVAILABLE = False

# Union type for accepting both beta (preview) and GA connection objects.
# main.py passes the connection returned by client.beta.realtime.connect()
# (preview) or client.realtime.connect() (GA) into RealtimeClient.
if GA_AVAILABLE:
    RealtimeConnectionType = Union[AsyncRealtimeConnection, AsyncRealtimeConnectionGA]  # type: ignore[name-defined]
else:
    RealtimeConnectionType = AsyncRealtimeConnection  # type: ignore[misc]


class Message(BaseModel):
    type: Literal[
        "user", "assistant", "assistant_delta", "audio", "console", "interrupt",
        "messages", "function", "text", "voice_start", "voice_stop",
        "modality_switch", "greeting"
    ]
    payload: str


class RealtimeClient:
    """
    Realtime client for handling websocket connections and messages.
    """

    def __init__(
        self,
        realtime: "RealtimeConnectionType",
        client: WebSocket,
        debug: bool = False,
        is_ga_mode: bool = False,
        thread_id: Optional[str] = None,
    ):
        self.realtime: Union["RealtimeConnectionType", None] = realtime
        self.client: Union[WebSocket, None] = client
        self.response_queue: list[ConversationItemCreateEvent] = []
        self.active = True
        self.debug = debug
        self.thread_id = thread_id
        self.microphone_active = False  # Track microphone state for modality switching
        # Conversation store for persisting voice transcripts as UnifiedMessages.
        # Defaults to the module-level singleton; tests can override via
        # _conversation_store attribute injection.
        self._conversation_store: ConversationStore = _default_store
        # Auto-detect GA mode from connection type, or accept explicit override.
        # When GA_AVAILABLE and the connection is an instance of the GA class,
        # the client operates in GA mode (different event names, session format).
        if is_ga_mode:
            self.is_ga_mode = True
        elif GA_AVAILABLE:
            self.is_ga_mode = isinstance(realtime, AsyncRealtimeConnectionGA)  # type: ignore[name-defined]
        else:
            self.is_ga_mode = False

    async def send_message(self, message: Message):
        if self.client is not None:
            await self.client.send_json(message.model_dump())

    async def send_audio(self, audio: Message):
        # send audio to client, format into bytes
        if (
            self.client is not None
            and self.client.client_state != WebSocketState.DISCONNECTED
        ):
            await self.client.send_json(audio.model_dump())

    async def send_console(self, message: Message):
        if self.client is not None:
            await self.client.send_json(message.model_dump())

    async def update_realtime_session(
        self,
        instructions: str,
        threshold: float = 0.8,
        silence_duration_ms: int = 500,
        prefix_padding_ms: int = 300,
    ):
        if self.realtime is None:
            return

        if self.is_ga_mode:
            # GA session format: nested audio configuration structure.
            # See Azure OpenAI GA Realtime API migration guide for nested audio config format.
            ga_session: dict = {
                "type": "realtime",
                "instructions": instructions,
                "output_modalities": ["text"],
                "audio": {
                    "input": {
                        "transcription": {
                            "model": "whisper-1",
                        },
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": threshold,
                            "prefix_padding_ms": prefix_padding_ms,
                            "silence_duration_ms": silence_duration_ms,
                            "create_response": True,
                        },
                    },
                    "output": {
                        "voice": "sage",
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                    },
                },
                "temperature": 0.8,
            }
            await self.realtime.session.update(session=ga_session)
        else:
            # Preview session format: typed Session object via SessionUpdateEvent.
            session: Session = Session(
                input_audio_format="pcm16",
                turn_detection=SessionTurnDetection(
                    prefix_padding_ms=prefix_padding_ms,
                    silence_duration_ms=silence_duration_ms,
                    threshold=threshold,
                    type="server_vad",
                ),
                input_audio_transcription=SessionInputAudioTranscription(
                    model="whisper-1",
                ),
                voice="sage",
                instructions=instructions,
                modalities=["text"],
            )
            await self.realtime.send(
                SessionUpdateEvent(
                    type="session.update",
                    session=session,
                )
            )

    async def update_modalities(self, modalities: list[str]):
        """Update the session output modalities dynamically.

        Called when the frontend sends a modality_switch message to toggle
        between text-only and text+audio response modes.
        """
        if self.realtime is None:
            return

        if self.is_ga_mode:
            ga_update: dict = {
                "output_modalities": modalities,
            }
            await self.realtime.session.update(session=ga_update)
        else:
            session_update = Session(modalities=modalities)
            await self.realtime.send(
                SessionUpdateEvent(
                    type="session.update",
                    session=session_update,
                )
            )

    async def inject_conversation_history(
        self,
        thread_id: str,
        store: Optional[ConversationStore] = None,
    ) -> int:
        """Inject prior conversation messages via conversation.item.create events.

        Must be called after update_realtime_session() completes.
        Returns the number of items injected.

        Parameters
        ----------
        thread_id:
            The conversation thread whose history should be injected.
        store:
            Optional ConversationStore instance. Defaults to the module-level
            singleton. Accepting this parameter enables unit testing with
            isolated stores.
        """
        if self.realtime is None:
            return 0

        if store is None:
            store = _default_store

        items = store.get_realtime_items(thread_id)
        if not items:
            print(f"No conversation history to inject for thread {thread_id}")
            return 0

        print(f"Injecting {len(items)} conversation items into realtime session")

        injected = 0
        for idx, item_event in enumerate(items):
            try:
                # Build a typed ConversationItemCreateEvent from the dict payload
                # returned by ConversationStore.get_realtime_items().
                event = ConversationItemCreateEvent(
                    type="conversation.item.create",
                    item=ConversationItem(
                        role=item_event["item"]["role"],
                        type="message",
                        content=[
                            ConversationItemContent(
                                type=item_event["item"]["content"][0]["type"],
                                text=item_event["item"]["content"][0]["text"],
                            )
                        ],
                    ),
                )
                await self.realtime.send(event)
                injected += 1
                if self.debug:
                    print(f"Injected item {idx+1}/{len(items)}: role={item_event['item']['role']}")
                # Small delay between injections to avoid overwhelming the API
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"Error injecting conversation item {idx}: {e}")

        print(f"Conversation history injection complete ({injected}/{len(items)} items)")
        return injected

    @trace
    async def receive_realtime(self):
        # signature = "api.session.RealtimeSession.receive_realtime"
        if self.realtime is None:
            pass

        while self.realtime is not None:
            async for event in self.realtime:
                if "delta" not in event.type and self.debug:
                    print(event.type)
                self.active = True
                match event.type:
                    case "error":
                        await self._handle_error(event)
                    case "session.created":
                        await self._session_created(event)
                    case "session.updated":
                        await self._session_updated(event)
                    case "conversation.created":
                        await self._conversation_created(event)
                    case "conversation.item.created":
                        await self._conversation_item_created(event)
                    case "conversation.item.input_audio_transcription.completed":
                        await self._conversation_item_input_audio_transcription_completed(
                            event
                        )
                    case "conversation.item.input_audio_transcription.delta":
                        await self._conversation_item_input_audio_transcription_delta(
                            event
                        )
                    case "conversation.item.input_audio_transcription.failed":
                        await self._conversation_item_input_audio_transcription_failed(
                            event
                        )
                    case "conversation.item.truncated":
                        await self._conversation_item_truncated(event)
                    case "conversation.item.deleted":
                        await self._conversation_item_deleted(event)
                    case "input_audio_buffer.committed":
                        await self._input_audio_buffer_committed(event)
                    case "input_audio_buffer.cleared":
                        await self._input_audio_buffer_cleared(event)
                    case "input_audio_buffer.speech_started":
                        await self._input_audio_buffer_speech_started(event)
                    case "input_audio_buffer.speech_stopped":
                        await self._input_audio_buffer_speech_stopped(event)
                    case "response.created":
                        await self._response_created(event)
                    case "response.done":
                        await self._response_done(event)
                    case "response.output_item.added":
                        await self._response_output_item_added(event)
                    case "response.output_item.done":
                        await self._response_output_item_done(event)
                    case "response.content_part.added":
                        await self._response_content_part_added(event)
                    case "response.content_part.done":
                        await self._response_content_part_done(event)
                    case "response.text.delta":
                        await self._response_text_delta(event)
                    case "response.output_text.delta":
                        # GA event name for response.text.delta
                        await self._response_text_delta(event)
                    case "response.text.done":
                        await self._response_text_done(event)
                    case "response.output_text.done":
                        # GA event name for response.text.done
                        await self._response_text_done(event)
                    case "response.audio_transcript.delta":
                        await self._response_audio_transcript_delta(event)
                    case "response.output_audio_transcript.delta":
                        # GA event name for response.audio_transcript.delta
                        await self._response_audio_transcript_delta(event)
                    case "response.audio_transcript.done":
                        await self._response_audio_transcript_done(event)
                    case "response.output_audio_transcript.done":
                        # GA event name for response.audio_transcript.done
                        await self._response_audio_transcript_done(event)
                    case "response.audio.delta":
                        await self._response_audio_delta(event)
                    case "response.output_audio.delta":
                        # GA event name for response.audio.delta
                        await self._response_audio_delta(event)
                    case "response.audio.done":
                        await self._response_audio_done(event)
                    case "response.output_audio.done":
                        # GA event name for response.audio.done
                        await self._response_audio_done(event)
                    case "response.function_call_arguments.delta":
                        await self._response_function_call_arguments_delta(event)
                    case "response.function_call_arguments.done":
                        await self._response_function_call_arguments_done(event)
                    case "rate_limits.updated":
                        await self._rate_limits_updated(event)
                    case "conversation.item.added":
                        await self._conversation_item_added(event)
                    case "conversation.item.done":
                        await self._conversation_item_done(event)
                    case _:
                        print(
                            f"Unhandled event type {event.type}",
                        )

        self.realtime = None

    @trace(name="error")
    async def _handle_error(self, event: ErrorEvent):
        pass

    @trace(name="session.created")
    async def _session_created(self, event: SessionCreatedEvent):
        await self.send_console(Message(type="console", payload=event.to_json()))

    @trace(name="session.updated")
    async def _session_updated(self, event: SessionUpdatedEvent):
        pass

    @trace(name="conversation.created")
    async def _conversation_created(self, event: ConversationCreatedEvent):
        pass

    @trace(name="conversation.item.created")
    async def _conversation_item_created(self, event: ConversationItemCreatedEvent):
        pass

    @trace(name="conversation.item.input_audio_transcription.completed")
    async def _conversation_item_input_audio_transcription_completed(
        self, event: ConversationItemInputAudioTranscriptionCompletedEvent
    ):
        if event.transcript is not None and len(event.transcript) > 0:
            # Store user transcript as UnifiedMessage (Task 54)
            if self.thread_id:
                user_msg = realtime_transcript_to_unified(
                    transcript=event.transcript,
                    role="user",
                    thread_id=self.thread_id,
                    realtime_item_id=getattr(event, "item_id", None),
                )
                self._conversation_store.add_message(self.thread_id, user_msg)

            await self.send_message(Message(type="user", payload=event.transcript))

    @trace(name="conversation.item.input_audio_transcription.delta")
    async def _conversation_item_input_audio_transcription_delta(
        self, event: ConversationItemInputAudioTranscriptionDeltaEvent
    ):
        pass

    @trace(name="conversation.item.input_audio_transcription.failed")
    async def _conversation_item_input_audio_transcription_failed(
        self, event: ConversationItemInputAudioTranscriptionFailedEvent
    ):
        pass

    @trace(name="conversation.item.truncated")
    async def _conversation_item_truncated(self, event: ConversationItemTruncatedEvent):
        pass

    @trace(name="conversation.item.deleted")
    async def _conversation_item_deleted(self, event: ConversationItemDeletedEvent):
        pass

    @trace(name="conversation.item.added")
    async def _conversation_item_added(self, event):
        """Handle GA-only conversation.item.added event.

        Signals that a new item has been added to the conversation.
        Logged for debugging; no client-side action required.
        """
        if self.debug:
            print(f"conversation.item.added: {getattr(event, 'item', None)}")

    @trace(name="conversation.item.done")
    async def _conversation_item_done(self, event):
        """Handle GA-only conversation.item.done event.

        Signals that a conversation item is completely finished.
        Logged for debugging; no client-side action required.
        """
        if self.debug:
            print(f"conversation.item.done: {getattr(event, 'item', None)}")

    @trace(name="input_audio_buffer.committed")
    async def _input_audio_buffer_committed(
        self, event: InputAudioBufferCommittedEvent
    ):
        pass

    @trace(name="input_audio_buffer.cleared")
    async def _input_audio_buffer_cleared(self, event: InputAudioBufferClearedEvent):
        pass

    @trace(name="input_audio_buffer.speech_started")
    async def _input_audio_buffer_speech_started(
        self, event: InputAudioBufferSpeechStartedEvent
    ):
        await self.send_console(Message(type="interrupt", payload=""))

    @trace(name="input_audio_buffer.speech_stopped")
    async def _input_audio_buffer_speech_stopped(
        self, event: InputAudioBufferSpeechStoppedEvent
    ):
        pass

    @trace(name="response.created")
    async def _response_created(self, event: ResponseCreatedEvent):
        pass

    @trace(name="response.done")
    async def _response_done(self, event: ResponseDoneEvent):
        if event.response.output is not None and len(event.response.output) > 0:
            output = event.response.output[0]
            match output.type:
                case "message":
                    await self.send_console(
                        Message(
                            type="console",
                            payload=json.dumps(
                                {
                                    "id": output.id,
                                    "role": output.role,
                                    "content": (
                                        output.content[0].transcript
                                        if output.content
                                        else None
                                    ),
                                }
                            ),
                        )
                    )
                case "function_call":
                    await self.send_console(
                        Message(
                            type="function",
                            payload=json.dumps(
                                {
                                    "name": output.name,
                                    "arguments": json.loads(output.arguments or "{}"),
                                    "call_id": output.call_id,
                                    "id": output.id,
                                }
                            ),
                        )
                    )

                case "function_call_output":
                    await self.send_console(
                        Message(type="console", payload=output.model_dump_json())
                    )

        if len(self.response_queue) > 0 and self.realtime is not None:
            for item in self.response_queue:
                await self.realtime.send(item)
            self.response_queue.clear()
            await self.realtime.response.create()

        self.active = False

    @trace(name="response.output_item.added")
    async def _response_output_item_added(self, event: ResponseOutputItemAddedEvent):
        pass

    @trace(name="response.output_item.done")
    async def _response_output_item_done(self, event: ResponseOutputItemDoneEvent):
        pass

    @trace(name="response.content_part.added")
    async def _response_content_part_added(self, event: ResponseContentPartAddedEvent):
        pass

    @trace(name="response.content_part.done")
    async def _response_content_part_done(self, event: ResponseContentPartDoneEvent):
        pass

    @trace(name="response.text.delta")
    async def _response_text_delta(self, event: ResponseTextDeltaEvent):
        # Forward text deltas to the frontend for text-only response mode.
        # Uses "assistant_delta" type so the frontend can distinguish streaming
        # chunks from completed messages ("assistant").
        if event.delta is not None and len(event.delta) > 0:
            await self.send_message(Message(type="assistant_delta", payload=event.delta))

    @trace(name="response.text.done")
    async def _response_text_done(self, event: ResponseTextDoneEvent):
        # Forward the completed text response to the frontend as an "assistant" message.
        if event.text is not None and len(event.text) > 0:
            # Store assistant text response as UnifiedMessage (Task 55)
            if self.thread_id:
                assistant_msg = realtime_transcript_to_unified(
                    transcript=event.text,
                    role="assistant",
                    thread_id=self.thread_id,
                )
                self._conversation_store.add_message(self.thread_id, assistant_msg)

            await self.send_message(Message(type="assistant", payload=event.text))

    @trace(name="response.audio.transcript.delta")
    async def _response_audio_transcript_delta(
        self, event: ResponseAudioTranscriptDeltaEvent
    ):
        # Forward audio transcript deltas to the frontend as assistant_delta
        # messages so the AI's spoken response text streams into the chat
        # window in real time (rather than waiting for the full transcript).
        if event.delta is not None and len(event.delta) > 0:
            await self.send_message(Message(type="assistant_delta", payload=event.delta))

    @trace(name="response.audio_transcript.done")
    async def _response_audio_transcript_done(
        self, event: ResponseAudioTranscriptDoneEvent
    ):
        if event.transcript is not None and len(event.transcript) > 0:
            # Store assistant audio transcript as UnifiedMessage (Task 55)
            if self.thread_id:
                assistant_msg = realtime_transcript_to_unified(
                    transcript=event.transcript,
                    role="assistant",
                    thread_id=self.thread_id,
                )
                self._conversation_store.add_message(self.thread_id, assistant_msg)

            await self.send_message(Message(type="assistant", payload=event.transcript))

    @trace(name="response.audio.delta")
    async def _response_audio_delta(self, event: ResponseAudioDeltaEvent):
        await self.send_audio(Message(type="audio", payload=event.delta))

    @trace(name="response.audio.done")
    async def _response_audio_done(self, event: ResponseAudioDoneEvent):
        pass

    @trace(name="response.function_call_arguments.delta")
    async def _response_function_call_arguments_delta(
        self, event: ResponseFunctionCallArgumentsDeltaEvent
    ):
        pass

    @trace(name="response.function_call_arguments.done")
    async def _response_function_call_arguments_done(
        self, event: ResponseFunctionCallArgumentsDoneEvent
    ):
        pass

    @trace(name="rate_limits.updated")
    async def _rate_limits_updated(self, event: RateLimitsUpdatedEvent):
        pass

    @trace
    async def receive_client(self):
        if self.client is None or self.realtime is None:
            return
        try:
            while self.client.client_state != WebSocketState.DISCONNECTED:
                message = await self.client.receive_text()

                message_json = json.loads(message)
                m = Message(**message_json)
                # print("received message", m.type)
                match m.type:
                    case "audio":
                        # Audio streaming from microphone -- mark as active
                        self.microphone_active = True
                        await self.realtime.send(
                            InputAudioBufferAppendEvent(
                                type="input_audio_buffer.append", audio=m.payload
                            )
                        )
                    case "user":
                        await self.realtime.send(
                            ConversationItemCreateEvent(
                                type="conversation.item.create",
                                item=ConversationItem(
                                    role="user",
                                    type="message",
                                    content=[
                                        ConversationItemContent(
                                            type="input_text",
                                            text=m.payload,
                                        )
                                    ],
                                ),
                            )
                        )
                    case "text":
                        # Text-only message when microphone is not active.
                        # Create a conversation item and request a text-only
                        # response (no audio output).
                        self.microphone_active = False
                        await self.realtime.send(
                            ConversationItemCreateEvent(
                                type="conversation.item.create",
                                item=ConversationItem(
                                    role="user",
                                    type="message",
                                    content=[
                                        ConversationItemContent(
                                            type="input_text",
                                            text=m.payload,
                                        )
                                    ],
                                ),
                            )
                        )
                        # Request text-only response (no audio output)
                        await self.realtime.send(
                            ResponseCreateEvent(
                                type="response.create",
                                response={"modalities": ["text"]},
                            )
                        )
                    case "voice_start":
                        # Signal that the microphone is now active
                        self.microphone_active = True
                    case "voice_stop":
                        # Signal that the microphone is now inactive
                        self.microphone_active = False
                    case "greeting":
                        # Greeting when voice mode starts. Create a conversation
                        # item and request a response using the session's current
                        # modalities (includes audio after modality_switch), so
                        # the greeting is spoken aloud.
                        self.microphone_active = True
                        await self.realtime.send(
                            ConversationItemCreateEvent(
                                type="conversation.item.create",
                                item=ConversationItem(
                                    role="user",
                                    type="message",
                                    content=[
                                        ConversationItemContent(
                                            type="input_text",
                                            text=m.payload,
                                        )
                                    ],
                                ),
                            )
                        )
                        # No modalities override -- uses session default (text+audio)
                        await self.realtime.response.create()
                    case "modality_switch":
                        # Dynamic modality switching: update session to use
                        # the requested output modalities (e.g. ["text"] or
                        # ["text", "audio"]).
                        switch_data = json.loads(m.payload)
                        new_modalities = switch_data.get("modalities", ["text"])
                        await self.update_modalities(new_modalities)
                    case "interrupt":
                        await self.realtime.send(
                            ResponseCreateEvent(type="response.create")
                        )
                    case "function":
                        function_message = json.loads(m.payload)

                        await self.realtime.send(
                            ConversationItemCreateEvent(
                                type="conversation.item.create",
                                item=ConversationItem(
                                    call_id=function_message["call_id"],
                                    type="function_call_output",
                                    output=function_message["output"],
                                ),
                            )
                        )

                        # Use appropriate modalities based on microphone state
                        if self.microphone_active:
                            await self.realtime.response.create()
                        else:
                            await self.realtime.send(
                                ResponseCreateEvent(
                                    type="response.create",
                                    response={"modalities": ["text"]},
                                )
                            )

                    case _:
                        await self.send_console(
                            Message(type="console", payload="Unhandled message")
                        )

        except WebSocketDisconnect:
            print("Realtime Socket Disconnected")

    async def close(self):
        if self.client is None or self.realtime is None:
            return
        try:
            await self.client.close()
            await self.realtime.close()
        except Exception as e:
            print("Error closing session", e)
            self.client = None
            self.realtime = None

    @property
    def closed(self):
        if self.client is None:
            return True
        return self.client.client_state == WebSocketState.DISCONNECTED
