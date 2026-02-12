/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
/**
 * Tests for useInlineVoice hook -- inline microphone toggle for the chat UI.
 *
 * This hook manages microphone capture and streams audio through the existing
 * RealtimeManager, toggling between text-only and text+audio modalities.
 *
 * We test the underlying InlineVoiceManager class directly (not the React hook)
 * since the core logic lives in the class and vitest environment is Node-based.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  InlineVoiceManager,
  InlineVoiceState,
} from "../inline-voice-manager";
import type { RealtimeManager } from "../realtime-manager";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

function createMockRealtimeManager(): RealtimeManager {
  return {
    connected: true,
    startAudio: vi.fn().mockResolvedValue(undefined),
    stopAudio: vi.fn().mockResolvedValue(undefined),
    connectVoice: vi.fn().mockResolvedValue(undefined),
    disconnectVoice: vi.fn(),
    switchModality: vi.fn(),
    sendTextMessage: vi.fn(),
    sendAudio: vi.fn(),
    send: vi.fn(),
    updateChatHistory: vi.fn(),
    updateUser: vi.fn(),
    dispose: vi.fn(),
    reconnect: vi.fn(),
    connect: vi.fn(),
  } as unknown as RealtimeManager;
}

describe("InlineVoiceManager", () => {
  let manager: InlineVoiceManager;
  let mockRealtime: RealtimeManager;
  let onStateChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRealtime = createMockRealtimeManager();
    onStateChange = vi.fn();
  });

  afterEach(() => {
    if (manager) {
      manager.dispose();
    }
    vi.restoreAllMocks();
  });

  // Test 1: Initial state is idle with no recording
  it("starts in idle state with isRecording false", () => {
    manager = new InlineVoiceManager(mockRealtime, onStateChange);

    const state = manager.getState();
    expect(state.isRecording).toBe(false);
    expect(state.voiceMode).toBe("idle");
  });

  // Test 2: toggleVoice starts audio capture via RealtimeManager
  it("toggleVoice starts audio through the RealtimeManager and sets recording state", async () => {
    manager = new InlineVoiceManager(mockRealtime, onStateChange);

    await manager.toggleVoice();

    expect(mockRealtime.startAudio).toHaveBeenCalledTimes(1);
    expect(onStateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        isRecording: true,
        voiceMode: "recording",
      })
    );
  });

  // Test 3: toggleVoice again stops audio capture
  it("toggleVoice stops audio when already recording", async () => {
    manager = new InlineVoiceManager(mockRealtime, onStateChange);

    // Start recording
    await manager.toggleVoice();
    onStateChange.mockClear();

    // Toggle off
    await manager.toggleVoice();

    expect(mockRealtime.stopAudio).toHaveBeenCalledTimes(1);
    expect(onStateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        isRecording: false,
        voiceMode: "idle",
      })
    );
  });

  // Test 4: Connects voice on demand when RealtimeManager is not connected
  it("calls connectVoice when the realtime connection is not yet available", async () => {
    (mockRealtime as any).connected = false;
    manager = new InlineVoiceManager(mockRealtime, onStateChange);

    await manager.toggleVoice();

    // Should connect voice on demand instead of bailing out
    expect(mockRealtime.connectVoice).toHaveBeenCalledTimes(1);
    expect(onStateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        isRecording: true,
        voiceMode: "recording",
      })
    );
  });

  // Test 5: stopVoiceCapture always resets to idle regardless of current state
  it("stopVoiceCapture resets state to idle even if not currently recording", async () => {
    manager = new InlineVoiceManager(mockRealtime, onStateChange);

    // Start recording
    await manager.toggleVoice();
    onStateChange.mockClear();

    // Explicitly stop
    await manager.stopVoiceCapture();

    expect(mockRealtime.stopAudio).toHaveBeenCalled();
    expect(onStateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        isRecording: false,
        voiceMode: "idle",
      })
    );
  });
});
