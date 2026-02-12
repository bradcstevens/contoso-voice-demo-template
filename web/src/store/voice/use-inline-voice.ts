"use client";
// ---------------------------------------------------------------------------
// useInlineVoice - React hook wrapping InlineVoiceManager
//
// Provides a simple toggle for inline microphone capture within the chat UI.
// Delegates all audio management to RealtimeManager via InlineVoiceManager.
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useRef, useState } from "react";
import {
  InlineVoiceManager,
  InlineVoiceState,
} from "./inline-voice-manager";
import { useLocalStorage } from "@/store/uselocalstorage";
import { defaultConfiguration, VoiceConfiguration } from ".";
import type { RealtimeManager } from "./realtime-manager";

export function useInlineVoice(realtimeManager: RealtimeManager | null) {
  const { storedValue: settings } = useLocalStorage<VoiceConfiguration>(
    "voice-settings",
    defaultConfiguration
  );

  const [state, setState] = useState<InlineVoiceState>({
    isRecording: false,
    voiceMode: "idle",
  });

  const managerRef = useRef<InlineVoiceManager | null>(null);

  // Recreate the InlineVoiceManager when the realtime manager changes
  useEffect(() => {
    if (managerRef.current) {
      managerRef.current.dispose();
      managerRef.current = null;
    }

    if (realtimeManager) {
      managerRef.current = new InlineVoiceManager(
        realtimeManager,
        (newState) => setState(newState),
        settings.inputDeviceId
      );
    }

    return () => {
      if (managerRef.current) {
        managerRef.current.dispose();
        managerRef.current = null;
      }
    };
  }, [realtimeManager, settings.inputDeviceId]);

  const toggleVoice = useCallback(async () => {
    if (managerRef.current) {
      await managerRef.current.toggleVoice();
    }
  }, []);

  const stopVoiceCapture = useCallback(async () => {
    if (managerRef.current) {
      await managerRef.current.stopVoiceCapture();
    }
  }, []);

  return {
    voiceMode: state.voiceMode,
    isRecording: state.isRecording,
    toggleVoice,
    stopVoiceCapture,
  };
}
