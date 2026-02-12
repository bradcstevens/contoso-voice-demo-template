/**
 * Tests for "Call Me" trigger detection utility.
 *
 * This utility scans assistant text responses for phrases that indicate
 * the assistant wants to initiate a voice call. When detected, the UI
 * should show an incoming call overlay instead of immediately connecting.
 */
import { describe, it, expect } from "vitest";
import {
  detectCallTrigger,
  CALL_TRIGGER_PATTERNS,
} from "../call-trigger";

describe("detectCallTrigger", () => {
  // Test 1: Detects common "call me" trigger phrases in assistant text
  it("detects common call trigger phrases in assistant text", () => {
    const phrases = [
      "I think it would be easier if I call you to walk through this.",
      "Let me call you to discuss the options.",
      "I'll call you right now to help with that.",
      "Would you like me to give you a call?",
      "Let me connect you to a voice call for better assistance.",
    ];

    for (const text of phrases) {
      const result = detectCallTrigger(text);
      expect(result.detected, `Should detect trigger in: "${text}"`).toBe(true);
      expect(result.phrase).toBeTruthy();
    }
  });

  // Test 2: Does NOT trigger on normal assistant text
  it("does not trigger on normal assistant text without call phrases", () => {
    const normalTexts = [
      "Here are the resistors we have in stock.",
      "The product you're looking for is the TMP36 temperature sensor.",
      "I can help you find the right capacitor for your circuit.",
      "Let me look up the datasheet for that component.",
      "The price for this item is $4.99.",
    ];

    for (const text of normalTexts) {
      const result = detectCallTrigger(text);
      expect(result.detected, `Should NOT detect trigger in: "${text}"`).toBe(
        false
      );
      expect(result.phrase).toBeNull();
    }
  });

  // Test 3: Detection is case-insensitive
  it("detects trigger phrases regardless of case", () => {
    const result1 = detectCallTrigger("LET ME CALL YOU about this order.");
    expect(result1.detected).toBe(true);

    const result2 = detectCallTrigger("i'll Call You to discuss.");
    expect(result2.detected).toBe(true);
  });

  // Test 4: Works with partial / streamed text (detects mid-message)
  it("detects triggers in partial or longer messages", () => {
    const longMessage =
      "Based on what you've described, I think it would be most helpful " +
      "if I call you so we can troubleshoot this live. That way I can " +
      "walk you through the configuration step by step.";

    const result = detectCallTrigger(longMessage);
    expect(result.detected).toBe(true);
    expect(result.phrase).toBeTruthy();
  });

  // Test 5: Returns null phrase when no trigger detected
  it("returns a properly shaped result with null phrase when not detected", () => {
    const result = detectCallTrigger("No trigger here.");
    expect(result).toEqual({ detected: false, phrase: null });
  });

  // Test 6: CALL_TRIGGER_PATTERNS is exported and non-empty
  it("exports a non-empty list of trigger patterns", () => {
    expect(CALL_TRIGGER_PATTERNS).toBeDefined();
    expect(CALL_TRIGGER_PATTERNS.length).toBeGreaterThan(0);
  });
});
