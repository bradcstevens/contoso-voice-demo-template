/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Tests for Task 36: RealtimeManager text message routing
 *
 * Validates that the RealtimeManager sends text messages in the correct
 * format expected by the backend's receive_client handler (voice/__init__.py).
 *
 * Tests:
 * 1. sendTextMessage uses "payload" field (not "content") matching backend Message model
 * 2. switchModality wraps modalities in JSON-encoded "payload" field
 * 3. handleIncomingMessage correctly routes assistant_delta messages
 * 4. handleIncomingMessage correctly routes assistant messages
 * 5. sendTextMessage does nothing when socket is not connected
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { RealtimeManager, type RealtimeManagerOptions } from "../voice/realtime-manager";

// ---------------------------------------------------------------------------
// Mock WebSocket for testing
// ---------------------------------------------------------------------------

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  sentMessages: string[] = [];

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  // Simulate connection opening
  triggerOpen() {
    if (this.onopen) this.onopen();
  }

  // Simulate receiving a message
  triggerMessage(data: object) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }
}

// Install mock WebSocket globally
let mockSocket: MockWebSocket;

beforeEach(() => {
  mockSocket = new MockWebSocket();
  vi.stubGlobal("WebSocket", class {
    static OPEN = 1;
    static CLOSED = 3;

    readyState = MockWebSocket.OPEN;
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;

    sentMessages: string[] = [];

    constructor() {
      // Store reference for test access
      mockSocket = this as any;
      // Auto-trigger open on next tick
      setTimeout(() => {
        if (this.onopen) this.onopen();
      }, 0);
    }

    send(data: string) {
      (this as any).sentMessages = (this as any).sentMessages || [];
      (this as any).sentMessages.push(data);
      mockSocket.sentMessages.push(data);
    }

    close() {
      this.readyState = MockWebSocket.CLOSED;
    }
  });
});

function createManager(overrides?: Partial<RealtimeManagerOptions>): {
  manager: RealtimeManager;
  onMessage: ReturnType<typeof vi.fn>;
  onConnectionChange: ReturnType<typeof vi.fn>;
} {
  const onMessage = vi.fn();
  const onConnectionChange = vi.fn();

  const manager = new RealtimeManager({
    endpoint: "ws://localhost:8000/api/voice",
    user: { name: "Test User", email: "test@test.com" },
    chatHistory: [],
    voiceSettings: { threshold: 0.8, silence: 500, prefix: 300, inputDeviceId: "default" },
    onMessage,
    onConnectionChange,
    ...overrides,
  });

  return { manager, onMessage, onConnectionChange };
}

// ---------------------------------------------------------------------------
// Test 1: sendTextMessage uses "payload" field (backend compatibility)
// ---------------------------------------------------------------------------

describe("RealtimeManager.sendTextMessage", () => {
  it("sends message with type=text and payload field matching backend Message model", async () => {
    const { manager } = createManager();

    // Explicitly connect (RealtimeManager no longer auto-connects)
    manager.connect();

    // Wait for connection to open
    await new Promise((r) => setTimeout(r, 10));

    manager.sendTextMessage("What capacitors do you have?");

    // Find the text message in sent messages (skip initial config messages)
    const sentMessages = mockSocket.sentMessages.map((s: string) => JSON.parse(s));
    const textMsg = sentMessages.find(
      (m: any) => m.type === "text" && (m.payload === "What capacitors do you have?" || m.content === "What capacitors do you have?")
    );

    expect(textMsg).toBeDefined();
    // The backend expects "payload", not "content"
    expect(textMsg.payload).toBe("What capacitors do you have?");
    expect(textMsg.content).toBeUndefined();

    manager.dispose();
  });
});

// ---------------------------------------------------------------------------
// Test 2: switchModality sends correct format for backend
// ---------------------------------------------------------------------------

describe("RealtimeManager.switchModality", () => {
  it("sends modality_switch with payload as JSON-encoded string", async () => {
    const { manager } = createManager();

    // Explicitly connect (RealtimeManager no longer auto-connects)
    manager.connect();

    await new Promise((r) => setTimeout(r, 10));

    manager.switchModality(["text", "audio"]);

    const sentMessages = mockSocket.sentMessages.map((s: string) => JSON.parse(s));
    const switchMsg = sentMessages.find((m: any) => m.type === "modality_switch");

    expect(switchMsg).toBeDefined();
    // Backend expects: m.payload = JSON string, then JSON.parse(m.payload) => { modalities: [...] }
    expect(switchMsg.payload).toBeDefined();
    const parsed = JSON.parse(switchMsg.payload);
    expect(parsed.modalities).toEqual(["text", "audio"]);

    manager.dispose();
  });
});

// ---------------------------------------------------------------------------
// Test 3: Incoming assistant_delta messages routed to onMessage
// ---------------------------------------------------------------------------

describe("RealtimeManager incoming message routing", () => {
  it("routes assistant_delta messages to onMessage callback", async () => {
    const { manager, onMessage } = createManager();

    // Explicitly connect (RealtimeManager no longer auto-connects)
    manager.connect();

    await new Promise((r) => setTimeout(r, 10));

    // Simulate receiving an assistant_delta from the backend
    mockSocket.onmessage?.({ data: JSON.stringify({
      type: "assistant_delta",
      payload: "Here are some options"
    }) });

    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "assistant_delta",
        payload: "Here are some options",
      })
    );

    manager.dispose();
  });

  it("routes assistant messages to onMessage callback", async () => {
    const { manager, onMessage } = createManager();

    // Explicitly connect (RealtimeManager no longer auto-connects)
    manager.connect();

    await new Promise((r) => setTimeout(r, 10));

    mockSocket.onmessage?.({ data: JSON.stringify({
      type: "assistant",
      payload: "Full response text"
    }) });

    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "assistant",
        payload: "Full response text",
      })
    );

    manager.dispose();
  });
});

// ---------------------------------------------------------------------------
// Test 4: sendTextMessage is no-op when disconnected
// ---------------------------------------------------------------------------

describe("RealtimeManager when disconnected", () => {
  it("sendTextMessage does not throw when socket is closed", async () => {
    const { manager } = createManager();

    // Explicitly connect then dispose (RealtimeManager no longer auto-connects)
    manager.connect();

    await new Promise((r) => setTimeout(r, 10));

    // Close the socket
    manager.dispose();

    // Should not throw
    expect(() => manager.sendTextMessage("test")).not.toThrow();
  });
});
