"use client";

// ---------------------------------------------------------------------------
// useRealtimeManager - React hook wrapping RealtimeManager for components
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useRef, useState } from "react";
import { WS_ENDPOINT } from "@/store/endpoint";
import { useLocalStorage } from "@/store/uselocalstorage";
import { defaultConfiguration, Player, Recorder, type VoiceConfiguration } from "@/store/voice";
import type { User } from "@/store/user";
import {
  RealtimeManager,
  type RealtimeMessage,
  type SimpleMessage,
  type AudioFactory,
} from "./realtime-manager";

// Re-export types so consumers only need one import
export type { RealtimeMessage, SimpleMessage } from "./realtime-manager";

export interface UseRealtimeManagerReturn {
  connected: boolean;
  sendTextMessage: (content: string) => void;
  switchModality: (modalities: string[]) => void;
  send: (message: RealtimeMessage) => void;
  startAudio: (deviceId?: string | null) => Promise<void>;
  stopAudio: () => Promise<void>;
  connectVoice: (deviceId?: string | null) => Promise<void>;
  disconnectVoice: () => void;
  reconnect: () => void;
  dispose: () => void;
  managerRef: React.MutableRefObject<RealtimeManager | null>;
}

/** Create the audio factory that bridges RealtimeManager to the existing Player/Recorder classes */
function createAudioFactory(): AudioFactory {
  return {
    createPlayer: () => new Player(() => {}),
    createRecorder: (onData: (buffer: ArrayBuffer) => void) => new Recorder(onData),
  };
}

export function useRealtimeManager(
  user: User | undefined,
  chatHistory: SimpleMessage[],
  onMessage: (message: RealtimeMessage) => void,
  threadId?: string,
): UseRealtimeManagerReturn {
  const { storedValue: settings } = useLocalStorage<VoiceConfiguration>(
    "voice-settings",
    defaultConfiguration,
  );

  const [connected, setConnected] = useState(false);
  const managerRef = useRef<RealtimeManager | null>(null);
  const onMessageRef = useRef(onMessage);
  const chatHistoryRef = useRef(chatHistory);
  const threadIdRef = useRef(threadId);

  // Keep refs current
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    chatHistoryRef.current = chatHistory;
    if (managerRef.current) {
      managerRef.current.updateChatHistory(chatHistory);
    }
  }, [chatHistory]);

  useEffect(() => {
    if (managerRef.current && user) {
      managerRef.current.updateUser(user);
    }
  }, [user]);

  // Keep threadId synchronized with the manager so reconnections
  // use the current thread for conversation continuity.
  useEffect(() => {
    threadIdRef.current = threadId;
    if (managerRef.current && threadId) {
      managerRef.current.updateThreadId(threadId);
    }
  }, [threadId]);

  // Create the RealtimeManager instance (but do NOT connect).
  // The voice WebSocket to /api/voice is only established when the user
  // explicitly triggers voice interaction via connectVoice().
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!user) return;

    const endpoint = WS_ENDPOINT.endsWith("/")
      ? WS_ENDPOINT.slice(0, -1)
      : WS_ENDPOINT;

    managerRef.current = new RealtimeManager({
      endpoint: `${endpoint}/api/voice`,
      user,
      chatHistory: chatHistoryRef.current,
      voiceSettings: settings,
      onMessage: (msg) => onMessageRef.current(msg),
      onConnectionChange: setConnected,
      audioFactory: createAudioFactory(),
      threadId: threadIdRef.current,
    });

    // NOTE: No this.connect() call -- voice is on-demand only.

    return () => {
      if (managerRef.current) {
        managerRef.current.dispose();
        managerRef.current = null;
      }
    };
    // Intentionally only run on mount / user change.
    // Settings and chatHistory are updated via refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.name, user?.email]);

  const sendTextMessage = useCallback((content: string) => {
    managerRef.current?.sendTextMessage(content);
  }, []);

  const switchModalityCb = useCallback((modalities: string[]) => {
    managerRef.current?.switchModality(modalities);
  }, []);

  const send = useCallback((message: RealtimeMessage) => {
    managerRef.current?.send(message);
  }, []);

  const startAudio = useCallback(async (deviceId?: string | null) => {
    await managerRef.current?.startAudio(deviceId ?? null);
  }, []);

  const stopAudio = useCallback(async () => {
    await managerRef.current?.stopAudio();
  }, []);

  const connectVoice = useCallback(async (deviceId?: string | null) => {
    await managerRef.current?.connectVoice(deviceId ?? null);
  }, []);

  const disconnectVoice = useCallback(() => {
    managerRef.current?.disconnectVoice();
  }, []);

  const reconnect = useCallback(() => {
    managerRef.current?.reconnect();
  }, []);

  const dispose = useCallback(() => {
    managerRef.current?.dispose();
    managerRef.current = null;
  }, []);

  return {
    connected,
    sendTextMessage,
    switchModality: switchModalityCb,
    send,
    startAudio,
    stopAudio,
    connectVoice,
    disconnectVoice,
    reconnect,
    dispose,
    managerRef,
  };
}
