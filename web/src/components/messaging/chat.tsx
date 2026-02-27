"use client";
import Message from "./message";
import styles from "./chat.module.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { GrPowerReset, GrClose, GrBeacon } from "react-icons/gr";
import { FiSettings } from "react-icons/fi";
import { HiOutlineChatBubbleLeftRight, HiOutlinePaperAirplane, HiOutlineSparkles, HiPlus } from "react-icons/hi2";
import { ChatState, useChatStore, AssistantName } from "@/store/chat";
import usePersistStore from "@/store/usePersistStore";
import FileImagePicker from "./fileimagepicker";
import { fetchCachedImage, removeCachedBlob } from "@/store/images";
import VideoImagePicker from "./videoimagepicker";
import clsx from "clsx";
import { ContextState, useContextStore } from "@/store/context";
import { ActionClient, suggestionRequested, startSuggestionTask } from "@/socket/action";
import { useUserStore } from "@/store/user";
import { ChatClient } from "@/store/chat-client";
import {
  useRealtimeManager,
  type RealtimeMessage,
  type SimpleMessage,
} from "@/store/voice/realtime-hook";
import { useInlineVoice } from "@/store/voice/use-inline-voice";
import MicrophoneButton from "./microphone-button";
import IncomingCallOverlay from "./incoming-call";
import VoiceSettings from "./voicesettings";
import { detectCallTrigger } from "@/store/call-trigger";
import Content from "./content";

interface ChatOptions {
  video?: boolean;
  file?: boolean;
}
type Props = {
  options?: ChatOptions;
};

const Chat = ({ options }: Props) => {
  /** STORE */
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const state = usePersistStore(useChatStore, (state) => state);
  const stateRef = useRef<ChatState | undefined>();

  const context = usePersistStore(useContextStore, (state) => state);
  const contextRef = useRef<ContextState | undefined>();

  const user = usePersistStore(useUserStore, (state) => state.user);
  const userState = usePersistStore(useUserStore, (state) => state);

  /** Text chat connection state (via /api/chat) */
  const [chatConnected, setChatConnected] = useState(false);
  const chatClientRef = useRef<ChatClient | null>(null);

  /** Voice settings panel state */
  const [voiceSettingsOpen, setVoiceSettingsOpen] = useState(false);

  /** Attach menu state (file/video pickers) */
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);

  /** Incoming call overlay state -- shown when assistant triggers a voice call */
  const [showIncomingCall, setShowIncomingCall] = useState(false);
  const checkForCallTriggerRef = useRef<() => void>(() => {});
  const checkForSuggestionsRef = useRef<() => void>(() => {});

  /** Suggestion popup state -- shown when the backend streams product suggestions */
  const [showSuggestions, setShowSuggestions] = useState(false);
  const showSuggestionsRef = useRef(false);
  const suggestionContentRef = useRef<string[]>([]);

  /** Derive chat history for the realtime manager */
  const chatHistory: SimpleMessage[] = (state?.turns ?? []).map((turn) => ({
    name: turn.type === "assistant" ? "assistant" : "user",
    text: turn.message,
  }));

  /** Track whether a suggestion check is already in-flight to avoid duplicates */
  const suggestionCheckInFlight = useRef(false);
  /** Ref to hold sendRealtimeMessage so checkForSuggestions always has the latest */
  const sendRealtimeRef = useRef<((msg: RealtimeMessage) => void) | null>(null);
  /** Ref to hold managerRef so checkForSuggestions can access it */
  const voiceManagerRef = useRef<{ current: { connected: boolean } | null }>({ current: null });

  /**
   * Voice message reordering buffer.
   *
   * The Azure OpenAI Realtime API fires transcription and response events
   * in parallel. The model often starts responding (assistant_delta) BEFORE
   * Whisper finishes transcribing the user's speech (user). This causes the
   * assistant turn to appear before the user turn in the chat.
   *
   * Fix: when we receive an assistant_delta and there's no corresponding user
   * turn yet (tracked by `pendingUserTranscription`), we buffer the deltas.
   * When the "user" transcription arrives we flush the buffer in the correct
   * order: user turn first, then replayed assistant deltas.
   */
  const pendingUserTranscription = useRef(false);
  const bufferedAssistantDeltas = useRef<string[]>([]);
  const bufferedAssistantComplete = useRef<{ type: "assistant"; payload: string } | null>(null);
  const transcriptionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** After a voice assistant message completes, check if the conversation
   *  warrants showing product suggestions on screen. If so, stream them
   *  into the context store which the Content popup renders from.
   */
  const checkForSuggestions = useCallback(
    async () => {
      if (suggestionCheckInFlight.current) return;
      suggestionCheckInFlight.current = true;

      try {
        // Read turns from useChatStore.getState() (synchronous, always current)
        // instead of from the ActionClient which uses stateRef.current that may
        // lag behind after Zustand set() calls that haven't triggered a re-render.
        const currentTurns = useChatStore.getState().turns;
        const messages: SimpleMessage[] = currentTurns.map((turn) => ({
          name: turn.type === "assistant" ? "assistant" : "user",
          text: turn.message,
        }));
        const result = await suggestionRequested(messages);
        if (result.requested) {
          // Clear old suggestions before streaming new ones
          if (contextRef.current) {
            contextRef.current.setSuggestion([]);
          }
          const userName = user?.name ?? "Brad";
          const task = await startSuggestionTask(userName, messages);
          for await (const chunk of task) {
            if (contextRef.current) {
              contextRef.current.streamSuggestion(chunk);
            }
          }
          // Notify the voice model that suggestions are ready
          if (voiceManagerRef.current?.current?.connected && sendRealtimeRef.current) {
            sendRealtimeRef.current({
              type: "text",
              payload: "The visual suggestions are ready",
            });
          }
        }
      } catch (err) {
        console.error("Failed to check/generate suggestions:", err);
      } finally {
        suggestionCheckInFlight.current = false;
      }
    },
    [user]
  );

  /** Flush buffered assistant deltas after the user transcription has been
   *  added to the chat, restoring the correct message order.
   */
  const flushBufferedAssistant = useCallback(() => {
    if (!stateRef.current || !contextRef.current) return;

    const deltas = bufferedAssistantDeltas.current;
    const complete = bufferedAssistantComplete.current;

    // Reset buffers first (avoid re-entrancy)
    bufferedAssistantDeltas.current = [];
    bufferedAssistantComplete.current = null;

    if (deltas.length > 0) {
      // Replay buffered deltas: start a new assistant turn and stream them
      stateRef.current.startAssistantMessage(AssistantName);
      for (const delta of deltas) {
        stateRef.current.streamAssistantMessage(delta);
      }
    }

    if (complete) {
      // The full assistant message arrived while we were buffering
      const turns = useChatStore.getState().turns;
      const lastTurn = turns[turns.length - 1];
      if (
        lastTurn &&
        lastTurn.type === "assistant" &&
        lastTurn.status === "streaming"
      ) {
        stateRef.current.completeAssistantMessage();
      } else if (complete.payload) {
        const client = new ActionClient(stateRef.current, contextRef.current);
        client.sendVoiceAssistantMessage(complete.payload);
      }
      // Check for suggestions now that the full exchange is in the chat
      const client = new ActionClient(stateRef.current, contextRef.current);
      checkForSuggestions();
    }
  }, [checkForSuggestions]);

  /** Handle incoming messages from the realtime voice WebSocket */
  const handleRealtimeMessage = useCallback(
    (msg: RealtimeMessage) => {
      if (!stateRef.current || !contextRef.current) return;
      const client = new ActionClient(stateRef.current, contextRef.current);

      switch (msg.type) {
        case "assistant_delta":
          // Streaming text response -- update the last assistant turn.
          if (msg.payload) {
            // If we're waiting for a user transcription, buffer the delta
            // so the user turn appears first when the transcription arrives.
            if (pendingUserTranscription.current) {
              bufferedAssistantDeltas.current.push(msg.payload);
              break;
            }

            // Use useChatStore.getState() to read the latest Zustand state
            // synchronously, avoiding stale stateRef reads when multiple
            // deltas arrive faster than React re-renders.
            const turns = useChatStore.getState().turns;
            const lastTurn = turns[turns.length - 1];
            if (
              lastTurn &&
              lastTurn.type === "assistant" &&
              (lastTurn.status === "waiting" || lastTurn.status === "streaming")
            ) {
              stateRef.current.streamAssistantMessage(msg.payload);
            } else {
              stateRef.current.startAssistantMessage(AssistantName);
              stateRef.current.streamAssistantMessage(msg.payload);
            }
          }
          break;

        case "assistant":
          // Complete text response
          if (msg.payload) {
            // If we're still waiting for user transcription, buffer the
            // complete message too so it appears after the user turn.
            if (pendingUserTranscription.current) {
              bufferedAssistantComplete.current = { type: "assistant", payload: msg.payload };
              // Safety timeout: if the user transcription never arrives
              // (e.g. Whisper failure), flush the buffer after 3 seconds
              // so the assistant message isn't lost.
              if (transcriptionTimeoutRef.current) {
                clearTimeout(transcriptionTimeoutRef.current);
              }
              transcriptionTimeoutRef.current = setTimeout(() => {
                if (pendingUserTranscription.current) {
                  pendingUserTranscription.current = false;
                  flushBufferedAssistant();
                }
              }, 3000);
              break;
            }

            const turns = useChatStore.getState().turns;
            const lastTurn = turns[turns.length - 1];
            if (
              lastTurn &&
              lastTurn.type === "assistant" &&
              lastTurn.status === "streaming"
            ) {
              stateRef.current.completeAssistantMessage();
            } else {
              // Full message received at once (non-streaming)
              client.sendVoiceAssistantMessage(msg.payload);
            }
            // Check if the voice conversation warrants showing product suggestions.
            // Runs async in the background so it doesn't block message handling.
            checkForSuggestions();
          }
          break;

        case "user":
          // User transcription from voice.
          // This may arrive AFTER assistant_delta messages due to Whisper
          // transcription latency. Clear the pending flag and flush any
          // buffered assistant content so the order is: user → assistant.
          if (msg.payload) {
            if (transcriptionTimeoutRef.current) {
              clearTimeout(transcriptionTimeoutRef.current);
              transcriptionTimeoutRef.current = null;
            }
            pendingUserTranscription.current = false;
            client.sendVoiceUserMessage(msg.payload, user ?? undefined);
            flushBufferedAssistant();
          }
          break;

        case "function":
          console.log("Function call result:", msg.payload);
          break;

        case "audio":
          // Audio data is handled internally by RealtimeManager's player
          break;

        case "interrupt":
          // User started speaking -- a transcription will follow.
          // If there's a stale buffer from a previous exchange (e.g.
          // transcription failed or was empty), flush it now so those
          // messages aren't lost.
          if (pendingUserTranscription.current && bufferedAssistantDeltas.current.length > 0) {
            pendingUserTranscription.current = false;
            flushBufferedAssistant();
          }
          if (transcriptionTimeoutRef.current) {
            clearTimeout(transcriptionTimeoutRef.current);
            transcriptionTimeoutRef.current = null;
          }
          // Mark as pending so assistant deltas are buffered until
          // the user transcription arrives and can be rendered first.
          pendingUserTranscription.current = true;
          bufferedAssistantDeltas.current = [];
          bufferedAssistantComplete.current = null;
          break;

        case "console":
          console.log("Realtime console:", msg.payload);
          break;
      }
    },
    [user, flushBufferedAssistant, checkForSuggestions]
  );

  /** Realtime manager -- does NOT auto-connect. Voice is on-demand only.
   *  We pass state.threadId so that when voice connects, the backend can
   *  look up the existing chat session and merge conversation context.
   */
  const {
    connected: voiceConnected,
    send: sendRealtimeMessage,
    startAudio,
    stopAudio,
    connectVoice,
    disconnectVoice,
    switchModality,
    managerRef,
  } = useRealtimeManager(user ?? undefined, chatHistory, handleRealtimeMessage, state?.threadId);

  // Keep refs in sync so checkForSuggestions can access the latest voice state
  sendRealtimeRef.current = sendRealtimeMessage;
  voiceManagerRef.current = managerRef;

  /** Inline voice -- microphone toggle in the chat input area.
   *  When the user clicks the mic button, we connect voice on demand.
   */
  const { toggleVoice: rawToggleVoice, stopVoiceCapture } = useInlineVoice(managerRef.current);

  /** Send a greeting prompt to the voice model so it acknowledges the switch to voice.
   *  Uses "greeting" type so the backend responds with audio (not text-only).
   */
  const sendVoiceGreeting = useCallback(() => {
    const name = user?.name?.split(" ")[0] ?? "there";
    sendRealtimeMessage({
      type: "greeting",
      payload: `The user ${name} just switched to voice mode. Greet them briefly, acknowledge the switch to voice. Resume the conversation, but keep the response concise since this is just a greeting after switching modalities.`,
    });
  }, [user, sendRealtimeMessage]);

  /** Single toggle: activates voice when off, hangs up when on */
  const toggleVoice = useCallback(async () => {
    if (voiceConnected) {
      // Already in a voice call -- hang up
      await stopVoiceCapture();
      disconnectVoice();
      if (stateRef.current) {
        stateRef.current.addAssistantMessage(
          AssistantName,
          "Voice call ended. You can continue chatting via text."
        );
      }
      return;
    }
    // Not connected -- establish voice connection
    try {
      const settings = JSON.parse(localStorage.getItem("voice-settings") || "{}");
      await connectVoice(settings.inputDeviceId || null);
      sendVoiceGreeting();
    } catch (err) {
      console.error("Failed to establish voice connection:", err);
      return;
    }
    rawToggleVoice();
  }, [voiceConnected, connectVoice, rawToggleVoice, sendVoiceGreeting, stopVoiceCapture, disconnectVoice]);

  /** Check the last assistant message for call trigger phrases and show overlay */
  const checkForCallTrigger = useCallback(() => {
    if (!stateRef.current) return;
    const turns = stateRef.current.turns;
    const lastTurn = turns[turns.length - 1];
    if (lastTurn && lastTurn.type === "assistant" && lastTurn.message) {
      const result = detectCallTrigger(lastTurn.message);
      if (result.detected) {
        setShowIncomingCall(true);
      }
    }
  }, []);

  // Keep refs current so the ChatClient effect closure can use them
  useEffect(() => {
    checkForCallTriggerRef.current = checkForCallTrigger;
  }, [checkForCallTrigger]);
  useEffect(() => {
    checkForSuggestionsRef.current = checkForSuggestions;
  }, [checkForSuggestions]);

  /** Accept the incoming call -- connect voice */
  const handleAcceptCall = useCallback(async () => {
    setShowIncomingCall(false);
    try {
      const settings = JSON.parse(
        localStorage.getItem("voice-settings") || "{}"
      );
      await connectVoice(settings.inputDeviceId || null);
      // Prompt the agent to greet the user after accepting the call
      sendVoiceGreeting();
    } catch (err) {
      console.error("Failed to establish voice connection from call accept:", err);
    }
  }, [connectVoice, sendVoiceGreeting]);

  /** Decline the incoming call -- dismiss overlay and continue text chat */
  const handleDeclineCall = useCallback(() => {
    setShowIncomingCall(false);
  }, []);


  // Expose realtime functions on the window so voice.tsx can access the shared connection
  useEffect(() => {
    if (typeof window !== "undefined") {
      (window as unknown as Record<string, unknown>).__realtimeManager = {
        send: sendRealtimeMessage,
        startAudio,
        stopAudio,
        connectVoice,
        disconnectVoice,
        switchModality,
        managerRef,
        connected: voiceConnected,
      };
    }
    return () => {
      if (typeof window !== "undefined") {
        delete (window as unknown as Record<string, unknown>).__realtimeManager;
      }
    };
  }, [
    sendRealtimeMessage,
    startAudio,
    stopAudio,
    connectVoice,
    disconnectVoice,
    switchModality,
    managerRef,
    voiceConnected,
  ]);

  /** Initialize the text chat client (connects to /api/chat) */
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!state?.threadId) return;

    const threadId = state.threadId;

    chatClientRef.current = new ChatClient(threadId, {
      onAssistantStart: () => {
        if (stateRef.current) {
          stateRef.current.startAssistantMessage(AssistantName);
        }
      },
      onAssistantStream: (chunk: string) => {
        if (stateRef.current) {
          stateRef.current.streamAssistantMessage(chunk);
        }
      },
      onAssistantComplete: () => {
        if (stateRef.current) {
          stateRef.current.completeAssistantMessage();
          // Check the completed message for call trigger phrases
          checkForCallTriggerRef.current();
          // Check if the text conversation warrants showing product suggestions
          checkForSuggestionsRef.current();
        }
      },
      onAssistantFull: (message: string) => {
        if (stateRef.current) {
          stateRef.current.addAssistantMessage(AssistantName, message);
          // Check the full message for call trigger phrases
          checkForCallTriggerRef.current();
          // Check if the text conversation warrants showing product suggestions
          checkForSuggestionsRef.current();
        }
      },
      onContext: (ctx: string) => {
        if (contextRef.current) {
          contextRef.current.addContext(ctx);
        }
      },
      onAction: (name: string, args: string) => {
        if (name === "call" && contextRef.current) {
          try {
            const parsed = JSON.parse(args);
            contextRef.current.setCallScore(parsed.score);
          } catch {
            console.error("ChatClient: failed to parse action args", args);
          }
        }
      },
      onConnectionChange: (connected: boolean) => {
        setChatConnected(connected);
      },
    });

    return () => {
      if (chatClientRef.current) {
        chatClientRef.current.dispose();
        chatClientRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.threadId]);

  /** Current State */
  useEffect(() => {
    stateRef.current = state;

    if (state && state.currentImage) {
      fetchCachedImage(state.currentImage, setCurrentImage).then(() => {
        scrollChat();
      });
    }
  }, [state]);

  /** Current Context */
  useEffect(() => {
    contextRef.current = context;
  }, [context]);

  // Show/hide the suggestions popup based on the context store's suggestion data.
  // Opens when suggestion data arrives (streamed by checkForSuggestions),
  // closes when the store is cleared (e.g. reset button calls clearContext()).
  useEffect(() => {
    if (context && context.suggestion.length > 0 && !showSuggestionsRef.current) {
      suggestionContentRef.current = context.suggestion;
      setShowSuggestions(true);
      showSuggestionsRef.current = true;
    } else if (context && context.suggestion.length === 0 && showSuggestionsRef.current) {
      setShowSuggestions(false);
      showSuggestionsRef.current = false;
      suggestionContentRef.current = [];
    }
  }, [context?.suggestion]);

  const onCloseSuggestions = useCallback(() => {
    setShowSuggestions(false);
    showSuggestionsRef.current = false;
    suggestionContentRef.current = [];
    if (contextRef.current) {
      contextRef.current.setSuggestion([]);
    }
  }, []);

  /** Send text message via /api/chat (not voice) */
  const sendMessage = async () => {
    if (stateRef.current) {
      const messageText = stateRef.current.message;
      if (!messageText || messageText.length === 0) return;

      const userName = user?.name || "Brad Stevens";
      const userImage = user?.image || "undefined";

      // Add user message to local chat store
      stateRef.current.sendMessage(userName, userImage);
      // Reset image
      setCurrentImage(null);

      // Send through the text chat WebSocket (/api/chat)
      if (chatClientRef.current?.connected) {
        chatClientRef.current.sendMessage(
          userName,
          messageText,
          stateRef.current.currentImage
        );
      }

      // Note: We do NOT start an assistant placeholder here.
      // The backend sends "start" -> "stream" -> "complete" messages
      // and our ChatClient callbacks handle that automatically.
    }
  };

  /** Connection indicator reflects the text chat connection */
  const isConnected = chatConnected;

  const manageConnection = () => {
    // Reconnect the text chat client
    chatClientRef.current?.reconnect();
  };

  const clear = () => {
    if (state) state.resetChat();
    if (context) context.clearContext();
    if (userState) userState.resetUser();
    clearImage();
    setShowIncomingCall(false);
    // Disconnect voice if active
    if (voiceConnected) {
      disconnectVoice();
    }
  };

  const clearImage = () => {
    if (state?.currentImage) {
      removeCachedBlob(state?.currentImage);
    }
    if (state) state.setCurrentImage(null);
    setCurrentImage(null);
  };

  /** Updates */
  const chatDiv = useRef<HTMLDivElement>(null);

  const scrollChat = () => {
    setTimeout(() => {
      if (chatDiv.current) {
        chatDiv.current.scrollTo({
          top: chatDiv.current.scrollHeight,
          behavior: "smooth",
        });
      }
    }, 10);
  };

  useEffect(() => {
    scrollChat();
  }, [state?.turns.length, state?.currentImage]);

  return (
    <>
      <div className={styles.chat}>
        {state && state?.open && (
          <div className={styles.chatWindow} style={{ position: "relative" }}>
            {/* Incoming call overlay */}
            {showIncomingCall && (
              <IncomingCallOverlay
                onAccept={handleAcceptCall}
                onDecline={handleDeclineCall}
              />
            )}
            <div className={styles.chatHeader}>
              <GrPowerReset
                size={18}
                className={styles.chatIcon}
                onClick={() => clear()}
              />
              <div className={"grow"} />
              <div className={styles.chatTitle}>
                <HiOutlineSparkles size={20} />
                <span>DigiKey AI Chat</span>
              </div>
              <div className={"grow"} />
              <div>
                <GrClose
                  size={18}
                  className={styles.chatIcon}
                  onClick={() => state && state.setOpen(false)}
                />
              </div>
            </div>
            {/* voice settings panel (replaces chat section when open) */}
            {voiceSettingsOpen ? (
              <div className={styles.voiceSettingsPanel}>
                <VoiceSettings />
              </div>
            ) : (
              <>
                {/* chat section */}
                <div className={styles.chatSection} ref={chatDiv}>
                  <div className={styles.chatMessages}>
                    <div className={styles.aiDisclaimer}>
                      <p>
                        Responses are generated using artificial intelligence (AI).
                        By using this chatbot, you acknowledge that recommendations
                        are AI-generated and may not fully reflect your individual
                        needs. We may maintain a transcript of chats for quality
                        assurance and to improve our AI models.
                      </p>
                    </div>
                    {state &&
                      state.turns.map((turn, index) => (
                        <Message key={index} turn={turn} notify={scrollChat} />
                      ))}
                  </div>
                </div>
                {/* image section */}
                {currentImage && (
                  <div className={styles.chatImageSection}>
                    <img
                      src={currentImage}
                      className={styles.chatImage}
                      alt="Current Image"
                      onClick={() => clearImage()}
                    />
                  </div>
                )}
              </>
            )}
            {/* chat input section */}
            <div className={styles.chatInputSection}>
              <input
                id="chat"
                name="chat"
                type="text"
                placeholder="Ask anything"
                title="Type a message"
                value={state ? state.message : ""}
                onChange={(e) => state && state.setMessage(e.target.value)}
                onKeyUp={(e) => {
                  if (e.code === "Enter") sendMessage();
                }}
                onFocus={() => setAttachMenuOpen(false)}
                className={styles.chatInput}
              />
              <div className={styles.chatInputToolbar}>
                <div className={styles.chatInputToolbarLeft}>
                  {(options?.file || options?.video) && (
                    <div className={styles.attachWrapper}>
                      <button
                        type="button"
                        title="Attach"
                        className={styles.chatToolbarButton}
                        onClick={() => setAttachMenuOpen(!attachMenuOpen)}
                      >
                        <HiPlus size={18} />
                      </button>
                      {attachMenuOpen && (
                        <div className={styles.attachMenu}>
                          {options.file && (
                            <div
                              className={styles.attachMenuItem}
                              onClick={() => setAttachMenuOpen(false)}
                            >
                              <FileImagePicker setCurrentImage={state.setCurrentImage} />
                              <span>Upload image</span>
                            </div>
                          )}
                          {options.video && (
                            <div
                              className={styles.attachMenuItem}
                              onClick={() => setAttachMenuOpen(false)}
                            >
                              <VideoImagePicker setCurrentImage={state.setCurrentImage} />
                              <span>Use camera</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className={styles.chatInputToolbarRight}>
                  <button
                    type="button"
                    title="Voice Settings"
                    className={styles.chatToolbarButton}
                    onClick={() => setVoiceSettingsOpen(!voiceSettingsOpen)}
                  >
                    {voiceSettingsOpen ? (
                      <GrClose size={18} />
                    ) : (
                      <FiSettings size={18} />
                    )}
                  </button>
                  <MicrophoneButton
                    isActive={voiceConnected}
                    disabled={false}
                    onClick={toggleVoice}
                  />
                  <button
                    type="button"
                    title="Send Message"
                    className={styles.chatSendCircle}
                    onClick={sendMessage}
                  >
                    <HiOutlinePaperAirplane size={18} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        {/* Suggestion popup -- shown when the backend streams product suggestions */}
        {state?.open && showSuggestions && (
          <Content
            suggestions={context?.suggestion ?? suggestionContentRef.current}
            onClose={onCloseSuggestions}
          />
        )}
        <div
          className={styles.chatButton}
          onClick={() => {
            if (state) state.setOpen(!state.open);
            scrollChat();
          }}
        >
          {state?.open ? (
            <GrClose size={24} />
          ) : (
            <HiOutlineChatBubbleLeftRight size={32} />
          )}
        </div>
      </div>
    </>
  );
};

export default Chat;
