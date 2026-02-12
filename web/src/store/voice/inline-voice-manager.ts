// ---------------------------------------------------------------------------
// InlineVoiceManager - manages inline microphone toggle for the chat UI
//
// This is a thin orchestrator around RealtimeManager's startAudio/stopAudio.
// It tracks the voice recording state and notifies consumers of changes.
//
// The React hook (useInlineVoice) wraps this class for component consumption.
// ---------------------------------------------------------------------------

import type { RealtimeManager } from "./realtime-manager";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type VoiceMode = "idle" | "recording";

export interface InlineVoiceState {
  isRecording: boolean;
  voiceMode: VoiceMode;
}

export type StateChangeCallback = (state: InlineVoiceState) => void;

// ---------------------------------------------------------------------------
// InlineVoiceManager class
// ---------------------------------------------------------------------------

export class InlineVoiceManager {
  private realtimeManager: RealtimeManager;
  private onStateChange: StateChangeCallback;
  private state: InlineVoiceState;
  private deviceId: string | null = null;

  constructor(
    realtimeManager: RealtimeManager,
    onStateChange: StateChangeCallback,
    deviceId?: string
  ) {
    this.realtimeManager = realtimeManager;
    this.onStateChange = onStateChange;
    this.deviceId = deviceId ?? null;
    this.state = {
      isRecording: false,
      voiceMode: "idle",
    };
  }

  getState(): InlineVoiceState {
    return { ...this.state };
  }

  async toggleVoice(): Promise<void> {
    if (this.state.isRecording) {
      await this.stopVoiceCapture();
    } else {
      await this.startVoiceCapture();
    }
  }

  async stopVoiceCapture(): Promise<void> {
    await this.realtimeManager.stopAudio();
    this.state = {
      isRecording: false,
      voiceMode: "idle",
    };
    this.onStateChange(this.getState());
  }

  dispose(): void {
    if (this.state.isRecording) {
      // Fire-and-forget cleanup
      this.realtimeManager.stopAudio().catch(() => {});
      this.state = { isRecording: false, voiceMode: "idle" };
    }
  }

  // ---- Private -----------------------------------------------------------

  private async startVoiceCapture(): Promise<void> {
    // If the voice connection is not established yet, connect on demand.
    // This supports the on-demand voice pattern where RealtimeManager
    // does not auto-connect.
    if (!this.realtimeManager.connected) {
      try {
        await this.realtimeManager.connectVoice(this.deviceId);
      } catch (err) {
        console.error("InlineVoiceManager: failed to connect voice", err);
        return;
      }
    } else {
      await this.realtimeManager.startAudio(this.deviceId);
    }

    this.state = {
      isRecording: true,
      voiceMode: "recording",
    };
    this.onStateChange(this.getState());
  }
}
