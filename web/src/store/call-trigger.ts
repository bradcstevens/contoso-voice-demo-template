// ---------------------------------------------------------------------------
// Call Trigger Detection Utility
//
// Scans assistant text responses for phrases indicating the assistant wants
// to initiate a voice call. When detected, the chat UI should display an
// incoming call overlay with accept/decline buttons.
//
// This is a pure utility module with no React or DOM dependencies, making
// it fully testable in a Node environment.
// ---------------------------------------------------------------------------

/** Result of scanning text for a call trigger phrase */
export interface CallTriggerResult {
  /** Whether a call trigger phrase was detected */
  detected: boolean;
  /** The matched trigger phrase, or null if not detected */
  phrase: string | null;
}

/**
 * Regex patterns that match assistant phrases indicating a desire to call.
 *
 * Each pattern is case-insensitive and matches common variations of:
 * - "call me" / "call you"
 * - "let me call"
 * - "I'll call"
 * - "give you a call"
 * - "connect you to a voice call"
 * - "incoming call"
 */
export const CALL_TRIGGER_PATTERNS: RegExp[] = [
  /\bi(?:'ll|'ll| will) call you\b/i,
  /\blet me call you\b/i,
  /\bif i call you\b/i,
  /\bgive you a call\b/i,
  /\bconnect you to a (?:voice )?call\b/i,
  /\bincoming call\b/i,
  /\blet me call\b/i,
  /\bi(?:'ll|'ll| will) give you a call\b/i,
];

/**
 * Scan assistant text for call trigger phrases.
 *
 * This function is designed to be lightweight and non-blocking. It runs
 * a small set of regex patterns against the provided text and returns
 * immediately.
 *
 * @param text - The assistant's message text to scan
 * @returns A CallTriggerResult indicating whether a trigger was found
 */
export function detectCallTrigger(text: string): CallTriggerResult {
  if (!text || text.length === 0) {
    return { detected: false, phrase: null };
  }

  for (const pattern of CALL_TRIGGER_PATTERNS) {
    const match = text.match(pattern);
    if (match) {
      return { detected: true, phrase: match[0] };
    }
  }

  return { detected: false, phrase: null };
}
