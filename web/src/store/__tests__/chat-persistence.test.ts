/**
 * Tests for chat persistence - Task 48.
 *
 * Validates that chat messages and threadId survive page reloads and
 * are only cleared when the user explicitly triggers resetChat().
 *
 * These tests exercise the Zustand store directly (no React rendering),
 * simulating localStorage round-trips to verify persistence behavior.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// localStorage mock - simulates browser storage across "page reloads"
// ---------------------------------------------------------------------------
const storageMap = new Map<string, string>();

const localStorageMock: Storage = {
  getItem: (key: string) => storageMap.get(key) ?? null,
  setItem: (key: string, value: string) => {
    storageMap.set(key, value);
  },
  removeItem: (key: string) => {
    storageMap.delete(key);
  },
  clear: () => storageMap.clear(),
  get length() {
    return storageMap.size;
  },
  key: (index: number) => Array.from(storageMap.keys())[index] ?? null,
};

// We need to install the mock before importing the store module
vi.stubGlobal("localStorage", localStorageMock);

// Mock uuid so we get predictable threadIds for testing
let uuidCounter = 0;
vi.mock("uuid", () => ({
  v4: () => `test-uuid-${++uuidCounter}`,
}));

// Mock the images module since it depends on browser APIs we don't have
vi.mock("../../store/images", () => ({
  removeCachedBlob: vi.fn(),
  fetchCachedImage: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------
describe("Chat Persistence (Zustand + localStorage)", () => {
  beforeEach(() => {
    storageMap.clear();
    uuidCounter = 0;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Helper: create a fresh store instance (simulates a new page load)
  async function createFreshStore() {
    // Clear the module cache so we get a fresh Zustand store that
    // will attempt to rehydrate from (our mocked) localStorage.
    vi.resetModules();
    // Re-stub localStorage after module reset
    vi.stubGlobal("localStorage", localStorageMock);
    const mod = await import("../../store/chat");
    return mod.useChatStore;
  }

  // Test 1: Store persists turns and threadId to localStorage
  it("persists turns and threadId to localStorage after adding messages", async () => {
    const useChatStore = await createFreshStore();
    const store = useChatStore.getState();

    // Initial threadId should be set
    expect(store.threadId).toBe("test-uuid-1");
    expect(store.turns).toEqual([]);

    // Add a user message
    store.sendFullMessage({
      name: "Brad Stevens",
      avatar: null,
      image: null,
      message: "Hello, do you have resistors?",
      status: "done",
      type: "user",
    });

    // Add an assistant message
    store.addAssistantMessage("Wiry", "Yes, we carry a wide range of resistors!");

    // Verify the store has the messages
    const updatedState = useChatStore.getState();
    expect(updatedState.turns).toHaveLength(2);
    expect(updatedState.turns[0].message).toBe("Hello, do you have resistors?");
    expect(updatedState.turns[1].message).toBe(
      "Yes, we carry a wide range of resistors!"
    );

    // Verify localStorage was written
    const stored = storageMap.get("chat-storage");
    expect(stored).toBeDefined();
    const parsed = JSON.parse(stored!);
    expect(parsed.state.threadId).toBe("test-uuid-1");
    expect(parsed.state.turns).toHaveLength(2);
  });

  // Test 2: Messages survive a simulated page reload (module re-import)
  it("restores messages from localStorage on simulated page reload", async () => {
    // First "page load" - add messages
    const useChatStore1 = await createFreshStore();
    const store1 = useChatStore1.getState();

    store1.sendFullMessage({
      name: "Brad Stevens",
      avatar: null,
      image: null,
      message: "What capacitors do you carry?",
      status: "done",
      type: "user",
    });
    store1.addAssistantMessage("Wiry", "We have ceramic, electrolytic, and film capacitors.");

    // Verify messages are in localStorage
    expect(storageMap.has("chat-storage")).toBe(true);

    // Second "page load" - fresh store should rehydrate
    const useChatStore2 = await createFreshStore();
    const store2 = useChatStore2.getState();

    // Should have restored the same turns
    expect(store2.turns).toHaveLength(2);
    expect(store2.turns[0].message).toBe("What capacitors do you carry?");
    expect(store2.turns[1].message).toBe(
      "We have ceramic, electrolytic, and film capacitors."
    );
    // threadId should be preserved across reload
    expect(store2.threadId).toBe(store1.threadId);
  });

  // Test 3: resetChat() clears turns and generates a new threadId
  it("resetChat() clears all turns and generates a new threadId", async () => {
    const useChatStore = await createFreshStore();
    const store = useChatStore.getState();

    // Record the initial threadId
    const initialThreadId = store.threadId;

    // Add messages
    store.sendFullMessage({
      name: "Brad Stevens",
      avatar: null,
      image: null,
      message: "Hello",
      status: "done",
      type: "user",
    });
    store.addAssistantMessage("Wiry", "Hi there!");
    expect(useChatStore.getState().turns).toHaveLength(2);

    // Reset the chat (this simulates the user clicking the reset button)
    useChatStore.getState().resetChat();

    const resetState = useChatStore.getState();
    expect(resetState.turns).toEqual([]);
    expect(resetState.message).toBe("");
    expect(resetState.currentImage).toBeNull();
    // threadId should be different after reset
    expect(resetState.threadId).not.toBe(initialThreadId);
  });

  // Test 4: resetChat() is the ONLY code path that clears turns
  // (This is a static analysis / code-level assertion)
  it("resetChat is the only method that clears the turns array", async () => {
    const useChatStore = await createFreshStore();
    const store = useChatStore.getState();

    // Add messages
    store.sendFullMessage({
      name: "Brad Stevens",
      avatar: null,
      image: null,
      message: "Test message",
      status: "done",
      type: "user",
    });
    expect(useChatStore.getState().turns).toHaveLength(1);

    // Exercise all non-reset methods and verify turns are not cleared
    store.setOpen(true);
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.setOpen(false);
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.setMessage("another message");
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.setCurrentImage("some-image-url");
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.setCurrentImage(null);
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.setThreadId("custom-thread-id");
    expect(useChatStore.getState().turns).toHaveLength(1);

    store.startAssistantMessage("Wiry");
    expect(useChatStore.getState().turns).toHaveLength(2);

    store.streamAssistantMessage("chunk");
    expect(useChatStore.getState().turns).toHaveLength(2);

    store.completeAssistantMessage();
    expect(useChatStore.getState().turns).toHaveLength(2);

    // Only resetChat should clear
    useChatStore.getState().resetChat();
    expect(useChatStore.getState().turns).toEqual([]);
  });

  // Test 5: Persist config uses the correct localStorage key and storage type
  it("uses 'chat-storage' as the localStorage key with JSON serialization", async () => {
    const useChatStore = await createFreshStore();

    // Trigger a state change to force persistence
    useChatStore.getState().setOpen(true);

    // The key should be "chat-storage" as configured in the persist middleware
    const stored = storageMap.get("chat-storage");
    expect(stored).toBeDefined();

    // Should be valid JSON
    const parsed = JSON.parse(stored!);
    expect(parsed).toHaveProperty("state");
    expect(parsed).toHaveProperty("version");

    // State should contain the core persisted fields
    expect(parsed.state).toHaveProperty("threadId");
    expect(parsed.state).toHaveProperty("turns");
    expect(parsed.state).toHaveProperty("open");
  });
});
