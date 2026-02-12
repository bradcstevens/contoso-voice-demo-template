"use client";
import clsx from "clsx";
import styles from "./voice.module.css";
import { useEffect, useRef, useState } from "react";
import { FiMic, FiMicOff, FiSettings } from "react-icons/fi";
import { ContextState, useContextStore } from "@/store/context";
import usePersistStore from "@/store/usePersistStore";
import Content from "./content";
import VoiceSettings from "./voicesettings";
import { GrClose } from "react-icons/gr";
import { useLocalStorage } from "@/store/uselocalstorage";
import { defaultConfiguration, type VoiceConfiguration } from "@/store/voice";
import type { RealtimeMessage } from "@/store/voice/realtime-manager";
import type { RealtimeManager } from "@/store/voice/realtime-manager";

/** Shape of the realtime manager exposed on window by chat.tsx */
interface WindowRealtimeManager {
  send: (message: RealtimeMessage) => void;
  startAudio: (deviceId?: string | null) => Promise<void>;
  stopAudio: () => Promise<void>;
  connectVoice: (deviceId?: string | null) => Promise<void>;
  disconnectVoice: () => void;
  switchModality: (modalities: string[]) => void;
  managerRef: React.MutableRefObject<RealtimeManager | null>;
  connected: boolean;
}

function getRealtimeManager(): WindowRealtimeManager | null {
  if (typeof window === "undefined") return null;
  return (
    (window as unknown as Record<string, unknown>).__realtimeManager as WindowRealtimeManager
  ) || null;
}

const Voice = () => {
  const contentRef = useRef<string[]>([]);
  const [settingsOpen, setSettingsOpen] = useState<boolean>(false);
  const [micActive, setMicActive] = useState<boolean>(false);

  const [suggestions, setSuggestions] = useState<boolean>(false);
  const suggestionsRef = useRef<boolean>(false);

  const context = usePersistStore(useContextStore, (state) => state);
  const contextRef = useRef<ContextState | undefined>();

  const settingsRef = useRef<HTMLDivElement>(null);

  const { storedValue: voiceSettings } = useLocalStorage<VoiceConfiguration>(
    "voice-settings",
    defaultConfiguration
  );

  const toggleSettings = () => {
    setSettingsOpen(!settingsOpen);
    settingsRef.current?.classList.toggle(styles.settingsOn);
  };

  const toggleMic = async () => {
    const mgr = getRealtimeManager();
    if (!mgr) {
      console.warn("Voice: realtime manager not available yet");
      return;
    }

    if (micActive) {
      // Turn off mic -- stop audio capture, disconnect voice
      console.log("Voice: stopping microphone and disconnecting voice");
      await mgr.stopAudio();
      mgr.disconnectVoice();
      setMicActive(false);
    } else {
      // Turn on mic -- connect voice on demand, then start audio capture
      console.log("Voice: connecting voice and starting microphone");
      try {
        await mgr.connectVoice(voiceSettings.inputDeviceId || null);
        setMicActive(true);
      } catch (err) {
        console.error("Voice: failed to establish voice connection:", err);
      }
    }
  };

  useEffect(() => {
    if (context) {
      contextRef.current = context;
    }
  }, [context]);

  // Show/hide the suggestions popup based on the context store's suggestion data.
  // Opens when suggestion data arrives (streamed by checkForSuggestions in chat.tsx),
  // closes when the store is cleared (e.g. new session button calls clearContext()).
  useEffect(() => {
    if (context && context.suggestion.length > 0 && !suggestionsRef.current) {
      contentRef.current = context.suggestion;
      setSuggestions(true);
      suggestionsRef.current = true;
    } else if (context && context.suggestion.length === 0 && suggestionsRef.current) {
      setSuggestions(false);
      suggestionsRef.current = false;
      contentRef.current = [];
    }
  }, [context?.suggestion]);

  // Auto-activate mic when call score threshold is reached
  useEffect(() => {
    if (contextRef.current && contextRef.current.call >= 5) {
      contextRef.current.setCallScore(0);
      // Auto-enable microphone via on-demand voice connection
      const mgr = getRealtimeManager();
      if (mgr && !micActive) {
        mgr.connectVoice(voiceSettings.inputDeviceId || null).then(() => {
          setMicActive(true);
        }).catch((err) => {
          console.error("Voice: failed to auto-connect voice:", err);
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextRef.current?.call]);

  const onCloseSuggestions = () => {
    setSuggestions(false);
    suggestionsRef.current = false;
    contentRef.current = [];
    // Clear the suggestion data in the store so a new round can trigger fresh
    if (contextRef.current) {
      contextRef.current.setSuggestion([]);
    }
  };

  return (
    <div className={clsx(styles.voice, suggestions && styles.voiceWithContent)}>
      {suggestions && (
        <Content
          suggestions={context?.suggestion ?? contentRef.current}
          onClose={onCloseSuggestions}
        />
      )}
      <div className={styles.voiceControl}>
        <div
          className={clsx(
            styles.voiceButton,
            micActive && styles.voiceOn
          )}
          onClick={toggleMic}
          title={micActive ? "Turn off microphone" : "Turn on microphone"}
        >
          {micActive ? <FiMicOff size={32} /> : <FiMic size={32} />}
        </div>
        <div
          className={styles.settingsButton}
          ref={settingsRef}
          onClick={toggleSettings}
        >
          {settingsOpen ? <GrClose size={24} /> : <FiSettings size={32} />}
        </div>
      </div>
      {settingsOpen && <VoiceSettings />}
    </div>
  );
};

export default Voice;
