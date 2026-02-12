/**
 * Tests for RealtimeManager - the unified realtime connection manager.
 *
 * RealtimeManager handles on-demand voice connections to /api/voice via
 * WebSocket, supports text messaging, modality switching (text <-> text+audio),
 * reconnection with exponential backoff, and threadId passthrough for
 * conversation continuity between text chat and voice sessions.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks - set up before importing the module under test
// ---------------------------------------------------------------------------

// Mock WebSocket
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
    // Store the instance for test access
    mockWebSocketInstances.push(this);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent("close"));
    }
  }

  // Test helpers
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen(new Event("open"));
  }

  simulateMessage(data: object) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data: JSON.stringify(data) }));
    }
  }

  simulateError() {
    if (this.onerror) this.onerror(new Event("error"));
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose(new CloseEvent("close"));
  }
}

let mockWebSocketInstances: MockWebSocket[] = [];

// We test the RealtimeManager class directly (not the React hook) since
// the core logic lives in the class and vitest environment is Node-based.
// The React hook is a thin wrapper around this class.

import {
  RealtimeManager,
  RealtimeManagerOptions,
  RealtimeMessage,
} from "../realtime-manager";

describe("RealtimeManager", () => {
  let manager: RealtimeManager;
  let onMessage: ReturnType<typeof vi.fn>;
  let onConnectionChange: ReturnType<typeof vi.fn>;

  /** Helper: create a manager with default options, merging any overrides */
  function createManager(overrides: Partial<RealtimeManagerOptions> = {}): RealtimeManager {
    const defaults: RealtimeManagerOptions = {
      endpoint: "ws://localhost:8000/api/voice",
      user: { name: "Brad Stevens", email: "brad@test.com" },
      chatHistory: [],
      voiceSettings: { threshold: 0.8, silence: 500, prefix: 300, inputDeviceId: "default" },
      onMessage,
      onConnectionChange,
    };
    return new RealtimeManager({ ...defaults, ...overrides });
  }

  /** Helper: create, connect, and open a manager */
  function createConnectedManager(overrides: Partial<RealtimeManagerOptions> = {}): RealtimeManager {
    const mgr = createManager(overrides);
    mgr.connect();
    mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
    return mgr;
  }

  beforeEach(() => {
    mockWebSocketInstances = [];
    // Replace global WebSocket with mock
    vi.stubGlobal("WebSocket", MockWebSocket);

    onMessage = vi.fn();
    onConnectionChange = vi.fn();
  });

  afterEach(() => {
    if (manager) {
      manager.dispose();
    }
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  // -------------------------------------------------------------------------
  // Test 1: Connects on-demand and sends initial config including threadId
  // -------------------------------------------------------------------------
  it("connects to the voice endpoint and sends initial config with threadId on open", () => {
    manager = createManager({
      chatHistory: [{ name: "user", text: "hello" }],
      threadId: "abc-123-thread",
    });

    // Constructor does NOT auto-connect (voice is on-demand)
    expect(mockWebSocketInstances.length).toBe(0);

    // Explicitly connect
    manager.connect();
    expect(mockWebSocketInstances.length).toBe(1);
    expect(mockWebSocketInstances[0].url).toBe("ws://localhost:8000/api/voice");

    // Simulate the connection opening
    mockWebSocketInstances[0].simulateOpen();

    // Should report connected
    expect(onConnectionChange).toHaveBeenCalledWith(true);

    // Should have sent initial config messages (messages + user config)
    const sent = mockWebSocketInstances[0].sentMessages;
    expect(sent.length).toBeGreaterThanOrEqual(2);

    // First message should be chat history
    const firstMsg = JSON.parse(sent[0]);
    expect(firstMsg.type).toBe("messages");

    // Second message should be user config WITH threadId
    const userConfig = JSON.parse(sent[1]);
    expect(userConfig.type).toBe("user");
    const configPayload = JSON.parse(userConfig.payload);
    expect(configPayload.threadId).toBe("abc-123-thread");
    expect(configPayload.user).toBe("Brad Stevens");
  });

  // -------------------------------------------------------------------------
  // Test 2: threadId is included in the user config payload sent to backend
  // -------------------------------------------------------------------------
  it("includes threadId in the user config payload when provided", () => {
    const threadId = "thread-uuid-456";
    manager = createConnectedManager({ threadId });

    // Find the user config message (second sent message)
    const sent = mockWebSocketInstances[0].sentMessages;
    const userConfigMsg = JSON.parse(sent[1]);
    expect(userConfigMsg.type).toBe("user");

    const payload = JSON.parse(userConfigMsg.payload);
    expect(payload.threadId).toBe(threadId);
  });

  // -------------------------------------------------------------------------
  // Test 3: sendTextMessage sends correctly formatted text message
  // -------------------------------------------------------------------------
  it("sends text messages with correct format through the WebSocket", () => {
    manager = createConnectedManager();

    // Clear sent messages from init
    mockWebSocketInstances[0].sentMessages = [];

    manager.sendTextMessage("What resistors do you have?");

    const sent = mockWebSocketInstances[0].sentMessages;
    expect(sent.length).toBe(1);

    const parsed = JSON.parse(sent[0]);
    expect(parsed.type).toBe("text");
    // Backend Message model expects "payload" field (not "content")
    expect(parsed.payload).toBe("What resistors do you have?");
  });

  // -------------------------------------------------------------------------
  // Test 4: updateThreadId changes the threadId for subsequent connections
  // -------------------------------------------------------------------------
  it("updates threadId and includes new value on reconnection", () => {
    manager = createConnectedManager({ threadId: "original-thread" });

    // Verify original threadId was sent
    const firstSent = mockWebSocketInstances[0].sentMessages;
    const firstConfig = JSON.parse(JSON.parse(firstSent[1]).payload);
    expect(firstConfig.threadId).toBe("original-thread");

    // Update threadId
    manager.updateThreadId("new-thread-789");

    // Disconnect and reconnect
    manager.reconnect();
    mockWebSocketInstances[1].simulateOpen();

    // Verify the new threadId is sent in the reconnection config
    const reconnectSent = mockWebSocketInstances[1].sentMessages;
    const reconnectConfig = JSON.parse(JSON.parse(reconnectSent[1]).payload);
    expect(reconnectConfig.threadId).toBe("new-thread-789");
  });

  // -------------------------------------------------------------------------
  // Test 5: Reconnects with exponential backoff on unexpected disconnect
  // -------------------------------------------------------------------------
  it("reconnects with exponential backoff on disconnect", () => {
    vi.useFakeTimers();

    manager = createManager();
    manager.connect();

    // First connection opens
    mockWebSocketInstances[0].simulateOpen();
    expect(onConnectionChange).toHaveBeenCalledWith(true);

    // Simulate unexpected disconnect
    mockWebSocketInstances[0].simulateClose();
    expect(onConnectionChange).toHaveBeenCalledWith(false);

    // Should not have reconnected immediately
    expect(mockWebSocketInstances.length).toBe(1);

    // Advance timer past first backoff (1000ms base)
    vi.advanceTimersByTime(1100);

    // Should have created a new WebSocket for reconnection
    expect(mockWebSocketInstances.length).toBe(2);
    expect(mockWebSocketInstances[1].url).toBe("ws://localhost:8000/api/voice");
  });

  // -------------------------------------------------------------------------
  // Test 6: send() routes arbitrary messages (used for suggestions-ready)
  // -------------------------------------------------------------------------
  it("send() routes arbitrary RealtimeMessage through the WebSocket (Task 67)", () => {
    // chat.tsx uses sendRealtimeRef.current(msg) which calls the hook's send()
    // function, which calls manager.send(message). This verifies that the
    // generic send() method correctly serializes and sends the suggestions-ready
    // notification with the exact format the backend expects.
    manager = createConnectedManager();

    // Clear sent messages from init
    mockWebSocketInstances[0].sentMessages = [];

    // This is the exact message chat.tsx:114-117 sends after suggestions stream
    manager.send({
      type: "text",
      payload: "The visual suggestions are ready",
    });

    const sent = mockWebSocketInstances[0].sentMessages;
    expect(sent.length).toBe(1);

    const parsed = JSON.parse(sent[0]);
    // Backend voice/__init__.py Message model requires "type" and "payload"
    expect(parsed.type).toBe("text");
    expect(parsed.payload).toBe("The visual suggestions are ready");
    // Must NOT include extra fields that would confuse the backend
    expect(Object.keys(parsed)).toEqual(["type", "payload"]);
  });

  // -------------------------------------------------------------------------
  // Test 7: send() silently drops messages when not connected
  // -------------------------------------------------------------------------
  it("send() silently drops messages when WebSocket is not open", () => {
    // When voice is disconnected, send() should not throw.
    // This covers the edge case where suggestions finish streaming
    // but the voice connection was lost during that time.
    manager = createManager();

    // Not connected -- no WebSocket created yet
    expect(() => {
      manager.send({
        type: "text",
        payload: "The visual suggestions are ready",
      });
    }).not.toThrow();

    // No messages should have been sent (no socket exists)
    expect(mockWebSocketInstances.length).toBe(0);
  });
});
