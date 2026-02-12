/**
 * Tests for voice speech-to-text (STT) and text-to-speech (TTS) transcript
 * display as chat messages.
 *
 * During active voice sessions:
 * - User speech transcriptions should appear as user messages
 * - AI audio transcript deltas should stream as assistant messages
 * - AI audio transcript done should complete the streaming assistant message
 * - Full voice flow: user speaks -> user message added, AI responds ->
 *   assistant message streams then completes
 *
 * These tests validate the message routing logic that lives in chat.tsx's
 * handleRealtimeMessage callback, exercised here through the RealtimeManager
 * onMessage pathway with mock chat store operations.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { RealtimeMessage } from "../realtime-manager";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CONNECTING = 0;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    mockWebSocketInstances.push(this);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose(new CloseEvent("close"));
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen(new Event("open"));
  }

  simulateMessage(data: object) {
    if (this.onmessage) {
      this.onmessage(
        new MessageEvent("message", { data: JSON.stringify(data) })
      );
    }
  }
}

let mockWebSocketInstances: MockWebSocket[] = [];

import {
  RealtimeManager,
  RealtimeManagerOptions,
} from "../realtime-manager";

/**
 * Simulates the handleRealtimeMessage logic from chat.tsx.
 *
 * This is a pure-function extraction of the switch/case routing that maps
 * RealtimeMessage types to chat store operations, so we can test it without
 * React component rendering.
 */
function createMockChatHandler() {
  const turns: Array<{
    type: "user" | "assistant";
    message: string;
    status: "waiting" | "streaming" | "done" | "voice";
    name: string;
  }> = [];

  const handler = {
    turns,

    /** Simulates ActionClient.sendVoiceUserMessage */
    sendVoiceUserMessage(message: string, userName: string) {
      turns.push({
        type: "user",
        message,
        status: "voice",
        name: userName,
      });
    },

    /** Simulates ActionClient.sendVoiceAssistantMessage */
    sendVoiceAssistantMessage(message: string) {
      turns.push({
        type: "assistant",
        message,
        status: "voice",
        name: "Wiry",
      });
    },

    /** Simulates ChatState.startAssistantMessage */
    startAssistantMessage(name: string) {
      turns.push({
        type: "assistant",
        message: "",
        status: "waiting",
        name,
      });
    },

    /** Simulates ChatState.streamAssistantMessage */
    streamAssistantMessage(chunk: string) {
      const lastTurn = turns[turns.length - 1];
      if (
        lastTurn &&
        lastTurn.type === "assistant" &&
        (lastTurn.status === "waiting" || lastTurn.status === "streaming")
      ) {
        lastTurn.message += chunk;
        lastTurn.status = "streaming";
      }
    },

    /** Simulates ChatState.completeAssistantMessage */
    completeAssistantMessage() {
      const lastTurn = turns[turns.length - 1];
      if (
        lastTurn &&
        lastTurn.type === "assistant" &&
        lastTurn.status === "streaming"
      ) {
        lastTurn.status = "done";
      }
    },

    /**
     * The message routing logic -- mirrors chat.tsx handleRealtimeMessage.
     * This is the function under test.
     */
    handleRealtimeMessage(msg: RealtimeMessage) {
      switch (msg.type) {
        case "assistant_delta":
          if (msg.payload) {
            const lastTurn = turns[turns.length - 1];
            if (
              lastTurn &&
              lastTurn.type === "assistant" &&
              (lastTurn.status === "waiting" ||
                lastTurn.status === "streaming")
            ) {
              handler.streamAssistantMessage(msg.payload);
            } else {
              handler.startAssistantMessage("Wiry");
              handler.streamAssistantMessage(msg.payload);
            }
          }
          break;

        case "assistant":
          if (msg.payload) {
            const lastTurn = turns[turns.length - 1];
            if (
              lastTurn &&
              lastTurn.type === "assistant" &&
              lastTurn.status === "streaming"
            ) {
              handler.completeAssistantMessage();
            } else {
              handler.sendVoiceAssistantMessage(msg.payload);
            }
          }
          break;

        case "user":
          if (msg.payload) {
            handler.sendVoiceUserMessage(msg.payload, "Brad Stevens");
          }
          break;

        case "audio":
        case "interrupt":
        case "console":
        case "function":
          // Not relevant for chat message display tests
          break;
      }
    },
  };

  return handler;
}

describe("Voice Chat Messages - STT and TTS Display", () => {
  let onConnectionChange: ReturnType<typeof vi.fn>;
  let chatHandler: ReturnType<typeof createMockChatHandler>;

  function createConnectedManagerWithHandler(): RealtimeManager {
    chatHandler = createMockChatHandler();

    const options: RealtimeManagerOptions = {
      endpoint: "ws://localhost:8000/api/voice",
      user: { name: "Brad Stevens", email: "brad@test.com" },
      chatHistory: [],
      voiceSettings: {
        threshold: 0.8,
        silence: 500,
        prefix: 300,
        inputDeviceId: "default",
      },
      onMessage: (msg) => chatHandler.handleRealtimeMessage(msg),
      onConnectionChange,
    };

    const mgr = new RealtimeManager(options);
    mgr.connect();
    mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
    return mgr;
  }

  beforeEach(() => {
    mockWebSocketInstances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    onConnectionChange = vi.fn();
    chatHandler = createMockChatHandler();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // Test 1: User speech transcription appears as a user message in chat
  // -------------------------------------------------------------------------
  it("displays user speech transcription as a user chat message", () => {
    const manager = createConnectedManagerWithHandler();
    const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];

    // Backend sends user transcription after speech-to-text completes
    ws.simulateMessage({ type: "user", payload: "What resistors do you have?" });

    expect(chatHandler.turns.length).toBe(1);
    expect(chatHandler.turns[0].type).toBe("user");
    expect(chatHandler.turns[0].message).toBe("What resistors do you have?");
    expect(chatHandler.turns[0].status).toBe("voice");
    expect(chatHandler.turns[0].name).toBe("Brad Stevens");

    manager.dispose();
  });

  // -------------------------------------------------------------------------
  // Test 2: AI audio transcript deltas stream as assistant messages
  // -------------------------------------------------------------------------
  it("streams AI audio transcript deltas as an assistant message in chat", () => {
    const manager = createConnectedManagerWithHandler();
    const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];

    // Backend sends audio transcript deltas (AI speaking, streamed)
    ws.simulateMessage({ type: "assistant_delta", payload: "We have " });
    ws.simulateMessage({ type: "assistant_delta", payload: "several " });
    ws.simulateMessage({ type: "assistant_delta", payload: "options." });

    // Should have one assistant turn being streamed
    expect(chatHandler.turns.length).toBe(1);
    expect(chatHandler.turns[0].type).toBe("assistant");
    expect(chatHandler.turns[0].message).toBe("We have several options.");
    expect(chatHandler.turns[0].status).toBe("streaming");

    manager.dispose();
  });

  // -------------------------------------------------------------------------
  // Test 3: AI audio transcript done completes the streaming message
  // -------------------------------------------------------------------------
  it("completes streaming assistant message when audio transcript done arrives", () => {
    const manager = createConnectedManagerWithHandler();
    const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];

    // Stream deltas
    ws.simulateMessage({ type: "assistant_delta", payload: "Here are the " });
    ws.simulateMessage({ type: "assistant_delta", payload: "resistors." });

    // Complete signal
    ws.simulateMessage({
      type: "assistant",
      payload: "Here are the resistors.",
    });

    expect(chatHandler.turns.length).toBe(1);
    expect(chatHandler.turns[0].type).toBe("assistant");
    expect(chatHandler.turns[0].message).toBe("Here are the resistors.");
    expect(chatHandler.turns[0].status).toBe("done");

    manager.dispose();
  });

  // -------------------------------------------------------------------------
  // Test 4: Full voice conversation flow - user speaks, AI responds with streaming
  // -------------------------------------------------------------------------
  it("handles full voice conversation: user STT then AI TTS streaming", () => {
    const manager = createConnectedManagerWithHandler();
    const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];

    // 1. User speaks and transcription completes
    ws.simulateMessage({
      type: "user",
      payload: "Do you have 10k ohm resistors?",
    });

    // 2. AI starts responding (audio transcript deltas)
    ws.simulateMessage({ type: "assistant_delta", payload: "Yes, " });
    ws.simulateMessage({ type: "assistant_delta", payload: "we carry " });
    ws.simulateMessage({
      type: "assistant_delta",
      payload: "10k ohm resistors.",
    });

    // 3. AI response complete
    ws.simulateMessage({
      type: "assistant",
      payload: "Yes, we carry 10k ohm resistors.",
    });

    // Should have 2 turns: one user, one assistant
    expect(chatHandler.turns.length).toBe(2);

    // User turn
    expect(chatHandler.turns[0].type).toBe("user");
    expect(chatHandler.turns[0].message).toBe(
      "Do you have 10k ohm resistors?"
    );

    // Assistant turn - completed after streaming
    expect(chatHandler.turns[1].type).toBe("assistant");
    expect(chatHandler.turns[1].message).toBe(
      "Yes, we carry 10k ohm resistors."
    );
    expect(chatHandler.turns[1].status).toBe("done");

    manager.dispose();
  });

  // -------------------------------------------------------------------------
  // Test 5: Non-streamed assistant message (backward compat) still works
  // -------------------------------------------------------------------------
  it("handles non-streamed assistant message when no prior delta exists", () => {
    const manager = createConnectedManagerWithHandler();
    const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];

    // Backend sends a complete assistant message without prior deltas
    // (e.g., response.audio_transcript.done without any delta events)
    ws.simulateMessage({
      type: "assistant",
      payload: "I can help you with that.",
    });

    expect(chatHandler.turns.length).toBe(1);
    expect(chatHandler.turns[0].type).toBe("assistant");
    expect(chatHandler.turns[0].message).toBe("I can help you with that.");
    expect(chatHandler.turns[0].status).toBe("voice");

    manager.dispose();
  });
});
