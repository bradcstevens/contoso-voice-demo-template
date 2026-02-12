/**
 * Message Reordering Buffer Tests
 *
 * Task 62: Tests the voice message reordering buffer implemented in chat.tsx
 * (lines 70-86, 132-168). This critical production fix handles the race
 * condition where the Azure OpenAI Realtime API sends assistant response
 * deltas BEFORE Whisper finishes transcribing the user's speech.
 *
 * The buffer ensures correct turn ordering: user message -> assistant response.
 *
 * This feature is NOT documented in ARCHITECTURE.md.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * Minimal simulation of the reordering buffer logic from chat.tsx.
 * This avoids importing React hooks and instead tests the pure logic.
 */
function createReorderingBuffer() {
  let pendingUserTranscription = false;
  const bufferedAssistantDeltas: string[] = [];
  let bufferedAssistantComplete: { type: "assistant"; payload: string } | null = null;
  let transcriptionTimeoutId: ReturnType<typeof setTimeout> | null = null;

  // Track what gets written to the "chat store"
  const chatLog: Array<{ role: string; content: string; event: string }> = [];

  function startAssistantMessage() {
    chatLog.push({ role: "assistant", content: "", event: "start" });
  }

  function streamAssistantMessage(delta: string) {
    const last = chatLog[chatLog.length - 1];
    if (last && last.role === "assistant" && (last.event === "start" || last.event === "stream")) {
      last.content += delta;
      last.event = "stream";
    }
  }

  function completeAssistantMessage() {
    const last = chatLog[chatLog.length - 1];
    if (last && last.role === "assistant") {
      last.event = "complete";
    }
  }

  function addUserMessage(text: string) {
    chatLog.push({ role: "user", content: text, event: "full" });
  }

  function addFullAssistantMessage(text: string) {
    chatLog.push({ role: "assistant", content: text, event: "full" });
  }

  function flushBufferedAssistant() {
    const deltas = [...bufferedAssistantDeltas];
    const complete = bufferedAssistantComplete;

    bufferedAssistantDeltas.length = 0;
    bufferedAssistantComplete = null;

    if (deltas.length > 0) {
      startAssistantMessage();
      for (const delta of deltas) {
        streamAssistantMessage(delta);
      }
    }

    if (complete) {
      const last = chatLog[chatLog.length - 1];
      if (last && last.role === "assistant" && last.event === "stream") {
        completeAssistantMessage();
      } else if (complete.payload) {
        addFullAssistantMessage(complete.payload);
      }
    }
  }

  function handleMessage(msg: { type: string; payload: string }) {
    switch (msg.type) {
      case "interrupt":
        // Flush stale buffer if exists
        if (pendingUserTranscription && bufferedAssistantDeltas.length > 0) {
          pendingUserTranscription = false;
          flushBufferedAssistant();
        }
        if (transcriptionTimeoutId) {
          clearTimeout(transcriptionTimeoutId);
          transcriptionTimeoutId = null;
        }
        pendingUserTranscription = true;
        bufferedAssistantDeltas.length = 0;
        bufferedAssistantComplete = null;
        break;

      case "assistant_delta":
        if (msg.payload) {
          if (pendingUserTranscription) {
            bufferedAssistantDeltas.push(msg.payload);
          } else {
            const last = chatLog[chatLog.length - 1];
            if (last && last.role === "assistant" && (last.event === "start" || last.event === "stream")) {
              streamAssistantMessage(msg.payload);
            } else {
              startAssistantMessage();
              streamAssistantMessage(msg.payload);
            }
          }
        }
        break;

      case "assistant":
        if (msg.payload) {
          if (pendingUserTranscription) {
            bufferedAssistantComplete = { type: "assistant", payload: msg.payload };
            // Safety timeout
            transcriptionTimeoutId = setTimeout(() => {
              if (pendingUserTranscription) {
                pendingUserTranscription = false;
                flushBufferedAssistant();
              }
            }, 3000);
          } else {
            const last = chatLog[chatLog.length - 1];
            if (last && last.role === "assistant" && last.event === "stream") {
              completeAssistantMessage();
            } else {
              addFullAssistantMessage(msg.payload);
            }
          }
        }
        break;

      case "user":
        if (msg.payload) {
          if (transcriptionTimeoutId) {
            clearTimeout(transcriptionTimeoutId);
            transcriptionTimeoutId = null;
          }
          pendingUserTranscription = false;
          addUserMessage(msg.payload);
          flushBufferedAssistant();
        }
        break;
    }
  }

  return {
    handleMessage,
    chatLog,
    getPendingState: () => ({
      pending: pendingUserTranscription,
      bufferedDeltas: [...bufferedAssistantDeltas],
      bufferedComplete: bufferedAssistantComplete,
    }),
  };
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

describe("Voice message reordering buffer", () => {
  it("correctly orders user->assistant when transcription arrives first", () => {
    const buffer = createReorderingBuffer();

    // Normal order: user speaks, transcription arrives, then assistant responds
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "user", payload: "Show me oscilloscopes" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Sure! " });
    buffer.handleMessage({ type: "assistant_delta", payload: "Here are some options." });
    buffer.handleMessage({ type: "assistant", payload: "Sure! Here are some options." });

    expect(buffer.chatLog).toHaveLength(2);
    expect(buffer.chatLog[0].role).toBe("user");
    expect(buffer.chatLog[0].content).toBe("Show me oscilloscopes");
    expect(buffer.chatLog[1].role).toBe("assistant");
  });

  it("buffers assistant deltas when transcription is still pending", () => {
    const buffer = createReorderingBuffer();

    // Race condition: assistant delta arrives BEFORE user transcription
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Here " });
    buffer.handleMessage({ type: "assistant_delta", payload: "you go!" });

    // Deltas should be buffered, not in chat log yet
    expect(buffer.chatLog).toHaveLength(0);
    const state = buffer.getPendingState();
    expect(state.pending).toBe(true);
    expect(state.bufferedDeltas).toEqual(["Here ", "you go!"]);
  });

  it("flushes buffer in correct order when user transcription arrives", () => {
    const buffer = createReorderingBuffer();

    // Race condition: assistant deltas arrive before user transcription
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Sure! " });
    buffer.handleMessage({ type: "assistant_delta", payload: "Let me help." });
    buffer.handleMessage({ type: "assistant", payload: "Sure! Let me help." });

    // Now user transcription arrives
    buffer.handleMessage({ type: "user", payload: "I need a multimeter" });

    // Order should be: user first, then assistant
    expect(buffer.chatLog).toHaveLength(2);
    expect(buffer.chatLog[0].role).toBe("user");
    expect(buffer.chatLog[0].content).toBe("I need a multimeter");
    expect(buffer.chatLog[1].role).toBe("assistant");
    expect(buffer.chatLog[1].content).toBe("Sure! Let me help.");
  });

  it("handles complete assistant message buffering during pending transcription", () => {
    const buffer = createReorderingBuffer();

    buffer.handleMessage({ type: "interrupt", payload: "" });
    // Full assistant message arrives before transcription
    buffer.handleMessage({ type: "assistant", payload: "I can help with that!" });

    expect(buffer.chatLog).toHaveLength(0);
    const state = buffer.getPendingState();
    expect(state.bufferedComplete).toEqual({
      type: "assistant",
      payload: "I can help with that!",
    });

    // User transcription arrives
    buffer.handleMessage({ type: "user", payload: "What resistors do you have?" });

    expect(buffer.chatLog).toHaveLength(2);
    expect(buffer.chatLog[0].role).toBe("user");
    expect(buffer.chatLog[1].role).toBe("assistant");
    expect(buffer.chatLog[1].content).toBe("I can help with that!");
  });

  it("safety timeout flushes buffer if transcription never arrives", async () => {
    vi.useFakeTimers();
    const buffer = createReorderingBuffer();

    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Hello " });
    buffer.handleMessage({ type: "assistant", payload: "Hello there" });

    // Nothing flushed yet
    expect(buffer.chatLog).toHaveLength(0);

    // Advance past the 3-second safety timeout
    vi.advanceTimersByTime(3100);

    // Buffer should have been flushed
    expect(buffer.chatLog.length).toBeGreaterThan(0);
    expect(buffer.chatLog[0].role).toBe("assistant");

    vi.useRealTimers();
  });

  it("clears timeout when user transcription arrives before timeout", () => {
    vi.useFakeTimers();
    const buffer = createReorderingBuffer();

    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant", payload: "Got it" });

    // User transcription arrives before timeout
    buffer.handleMessage({ type: "user", payload: "Show me options" });

    expect(buffer.chatLog).toHaveLength(2);
    expect(buffer.chatLog[0].role).toBe("user");
    expect(buffer.chatLog[1].role).toBe("assistant");

    // Advance time -- should not cause any additional flush
    vi.advanceTimersByTime(5000);

    // No additional entries
    expect(buffer.chatLog).toHaveLength(2);

    vi.useRealTimers();
  });

  it("new interrupt flushes stale buffer from previous exchange", () => {
    const buffer = createReorderingBuffer();

    // First exchange: interrupt + buffered deltas (no transcription arrives)
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Stale content" });

    // New interrupt arrives before old transcription
    buffer.handleMessage({ type: "interrupt", payload: "" });

    // Stale content should be flushed
    expect(buffer.chatLog).toHaveLength(1);
    expect(buffer.chatLog[0].role).toBe("assistant");
    expect(buffer.chatLog[0].content).toBe("Stale content");
  });

  it("handles multiple exchanges in sequence correctly", () => {
    const buffer = createReorderingBuffer();

    // Exchange 1: normal order
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "user", payload: "Hello" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Hi!" });
    buffer.handleMessage({ type: "assistant", payload: "Hi!" });

    // Exchange 2: race condition
    buffer.handleMessage({ type: "interrupt", payload: "" });
    buffer.handleMessage({ type: "assistant_delta", payload: "Sure" });
    buffer.handleMessage({ type: "assistant", payload: "Sure thing" });
    buffer.handleMessage({ type: "user", payload: "Show me products" });

    expect(buffer.chatLog).toHaveLength(4);
    expect(buffer.chatLog[0]).toMatchObject({ role: "user", content: "Hello" });
    expect(buffer.chatLog[1]).toMatchObject({ role: "assistant" });
    expect(buffer.chatLog[2]).toMatchObject({ role: "user", content: "Show me products" });
    expect(buffer.chatLog[3]).toMatchObject({ role: "assistant" });
  });
});
