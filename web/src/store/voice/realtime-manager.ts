// ---------------------------------------------------------------------------
// RealtimeManager - unified WebSocket connection to /api/voice
//
// This file contains:
//   1. RealtimeManager class - pure logic, no React/Next imports, fully testable
//   2. Types/interfaces used by the manager
//
// The React hook (useRealtimeManager) lives in realtime-hook.ts and wraps
// this class for component consumption.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Messages sent/received over the realtime WebSocket */
export interface RealtimeMessage {
  type:
    | "text"
    | "user"
    | "assistant"
    | "assistant_delta"
    | "audio"
    | "console"
    | "interrupt"
    | "messages"
    | "function"
    | "modality_switch"
    | "greeting";
  payload?: string;
  content?: string;
  modalities?: string[];
}

export interface SimpleMessage {
  name: string;
  text: string;
}

/** Minimal user shape needed by the manager */
export interface RealtimeUser {
  name: string;
  email: string;
  image?: string;
}

/** Voice settings shape */
export interface RealtimeVoiceSettings {
  threshold: number;
  silence: number;
  prefix: number;
  inputDeviceId: string;
}

/** Audio player interface (so the class doesn't depend on the Player import) */
export interface AudioPlayer {
  init(sampleRate: number): Promise<void>;
  play(buffer: Int16Array): void;
  clear(): void;
}

/** Audio recorder interface */
export interface AudioRecorder {
  start(stream: MediaStream): Promise<void> | void;
  stop(): void;
}

/** Factory functions to create audio components (injected at runtime) */
export interface AudioFactory {
  createPlayer: () => AudioPlayer;
  createRecorder: (onData: (buffer: ArrayBuffer) => void) => AudioRecorder;
}

/** Options for constructing a RealtimeManager */
export interface RealtimeManagerOptions {
  endpoint: string;
  user: RealtimeUser;
  chatHistory: SimpleMessage[];
  voiceSettings: RealtimeVoiceSettings;
  onMessage: (message: RealtimeMessage) => void;
  onConnectionChange: (connected: boolean) => void;
  audioFactory?: AudioFactory;
  /** Thread ID for conversation continuity between text chat and voice.
   *  When provided, the backend uses this to look up the existing
   *  ChatSession context so the voice AI has full conversation history.
   */
  threadId?: string;
}

// ---------------------------------------------------------------------------
// RealtimeManager class -- core logic, testable without React
// ---------------------------------------------------------------------------

export class RealtimeManager {
  private endpoint: string;
  private user: RealtimeUser;
  private chatHistory: SimpleMessage[];
  private voiceSettings: RealtimeVoiceSettings;
  private onMessage: (message: RealtimeMessage) => void;
  private onConnectionChange: (connected: boolean) => void;
  private audioFactory?: AudioFactory;
  private threadId?: string;

  private socket: WebSocket | null = null;
  private disposed = false;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // Audio components (only initialised when voice modality is active)
  private player: AudioPlayer | null = null;
  private recorder: AudioRecorder | null = null;

  // Max reconnect attempts before giving up
  private static MAX_RECONNECT = 8;
  private static BASE_DELAY_MS = 1000;

  constructor(options: RealtimeManagerOptions) {
    this.endpoint = options.endpoint;
    this.user = options.user;
    this.chatHistory = options.chatHistory;
    this.voiceSettings = options.voiceSettings;
    this.onMessage = options.onMessage;
    this.onConnectionChange = options.onConnectionChange;
    this.audioFactory = options.audioFactory;
    this.threadId = options.threadId;

    // NOTE: We intentionally do NOT auto-connect here.
    // Voice connections are expensive (Azure OpenAI Realtime API) and should
    // only be established when the user explicitly requests voice interaction.
    // Call connectVoice() to establish the connection on demand.
  }

  // ---- Connection lifecycle ------------------------------------------------

  /** Establish the WebSocket connection to /api/voice.
   *
   * This is intentionally NOT called from the constructor. Voice connections
   * are expensive (Azure OpenAI Realtime API) and should only be created
   * when the user explicitly triggers voice interaction (e.g., clicks mic).
   */
  connect() {
    if (this.disposed) return;

    try {
      this.socket = new WebSocket(this.endpoint);
    } catch (err) {
      console.error("RealtimeManager: failed to create WebSocket", err);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.onConnectionChange(true);
      this.sendInitialConfig();
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const msg: RealtimeMessage = JSON.parse(event.data as string);
        this.handleIncomingMessage(msg);
      } catch (err) {
        console.error("RealtimeManager: failed to parse message", err);
      }
    };

    this.socket.onerror = () => {
      console.error("RealtimeManager: WebSocket error");
    };

    this.socket.onclose = () => {
      this.onConnectionChange(false);
      if (!this.disposed) {
        this.scheduleReconnect();
      }
    };
  }

  private sendInitialConfig() {
    // Send chat history so the realtime model has context
    this.sendRaw({
      type: "messages",
      payload: JSON.stringify(this.chatHistory),
    });

    // Send user configuration including threadId for conversation continuity.
    // The backend voice endpoint reads settings.get("threadId") to look up
    // the existing ChatSession context and merge it into the voice session.
    const configMessage: Record<string, unknown> = {
      user: this.user.name,
      threshold: this.voiceSettings.threshold,
      silence: this.voiceSettings.silence,
      prefix: this.voiceSettings.prefix,
    };

    if (this.threadId) {
      configMessage.threadId = this.threadId;
    }

    this.sendRaw({
      type: "user",
      payload: JSON.stringify(configMessage),
    });
  }

  private scheduleReconnect() {
    if (this.disposed) return;
    if (this.reconnectAttempt >= RealtimeManager.MAX_RECONNECT) {
      console.warn("RealtimeManager: max reconnection attempts reached");
      return;
    }

    const delay = RealtimeManager.BASE_DELAY_MS * Math.pow(2, this.reconnectAttempt);
    this.reconnectAttempt++;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  // ---- Incoming message routing -------------------------------------------

  private handleIncomingMessage(msg: RealtimeMessage) {
    if (msg.type === "audio") {
      // Route audio to the Player if active
      if (this.player && msg.payload) {
        const buffer = Uint8Array.from(atob(msg.payload), (c) =>
          c.charCodeAt(0)
        ).buffer;
        this.player.play(new Int16Array(buffer));
      }
      // Also forward to the consumer so voice.tsx can track state
      this.onMessage(msg);
      return;
    }

    if (msg.type === "interrupt") {
      if (this.player) {
        this.player.clear();
      }
      this.onMessage(msg);
      return;
    }

    // All other message types forwarded to the consumer
    this.onMessage(msg);
  }

  // ---- Public API ----------------------------------------------------------

  get connected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /** Send a text chat message through the realtime WebSocket.
   *
   * The backend Message model (voice/__init__.py) expects { type, payload }
   * and the receive_client handler's "text" case reads m.payload for the
   * user's text content.
   */
  sendTextMessage(content: string) {
    this.sendRaw({ type: "text", payload: content });
  }

  /** Send raw audio data (base64 encoded) */
  sendAudio(base64Data: string) {
    this.sendRaw({ type: "audio", payload: base64Data });
  }

  /** Switch modalities between ["text"] and ["text", "audio"].
   *
   * The backend receive_client handler parses the "modality_switch" case by
   * reading m.payload as a JSON string, then extracting the "modalities" key:
   *   switch_data = json.loads(m.payload)
   *   new_modalities = switch_data.get("modalities", ["text"])
   */
  switchModality(modalities: string[]) {
    this.sendRaw({
      type: "modality_switch",
      payload: JSON.stringify({ modalities }),
    });
  }

  /** Send an arbitrary message (used for injecting messages, e.g. suggestions ready) */
  send(message: RealtimeMessage) {
    this.sendRaw(message);
  }

  /** Update the chat history reference (called when turns change) */
  updateChatHistory(history: SimpleMessage[]) {
    this.chatHistory = history;
  }

  /** Update user reference */
  updateUser(user: RealtimeUser) {
    this.user = user;
  }

  /** Update the thread ID for conversation continuity.
   *  Called when the chat store's threadId changes (e.g., after a chat reset).
   */
  updateThreadId(threadId: string) {
    this.threadId = threadId;
  }

  /** Connect and start audio in one step.
   *
   * This is the primary entry point for on-demand voice activation.
   * It establishes the WebSocket connection if not already connected,
   * then starts audio capture.
   */
  async connectVoice(deviceId: string | null = null): Promise<void> {
    if (!this.connected) {
      this.connect();
      // Wait for connection to open before starting audio
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("Voice connection timeout"));
        }, 10000);

        const checkConnection = () => {
          if (this.connected) {
            clearTimeout(timeout);
            resolve();
          } else if (this.disposed) {
            clearTimeout(timeout);
            reject(new Error("Manager disposed"));
          } else {
            setTimeout(checkConnection, 100);
          }
        };
        checkConnection();
      });
    }
    await this.startAudio(deviceId);
  }

  /** Disconnect voice and stop audio, but keep the manager instance alive
   * so it can be reconnected later.
   */
  disconnectVoice(): void {
    // Stop audio without sending modality_switch (socket may be closing)
    if (this.recorder) {
      this.recorder.stop();
      this.recorder = null;
    }
    if (this.player) {
      this.player.clear();
      this.player = null;
    }
    if (this.socket) {
      this.socket.onclose = null; // prevent reconnect on intentional close
      this.socket.close();
      this.socket = null;
    }
    this.onConnectionChange(false);
  }

  // ---- Audio management (voice toggle) ------------------------------------

  async startAudio(deviceId: string | null = null) {
    if (typeof window === "undefined") return;
    if (!this.audioFactory) {
      console.warn("RealtimeManager: no audioFactory provided, cannot start audio");
      return;
    }

    // Initialize player
    this.player = this.audioFactory.createPlayer();
    await this.player.init(24000);

    // Initialize recorder that sends audio through the socket
    this.recorder = this.audioFactory.createRecorder((buffer: ArrayBuffer) => {
      const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
      this.sendAudio(base64);
    });

    let audio: MediaTrackConstraints = {
      sampleRate: 24000,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    if (deviceId && deviceId !== "default") {
      audio = { ...audio, deviceId: { exact: deviceId } };
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio });
    } catch (error) {
      if (error instanceof Error && error.name === "OverconstrainedError") {
        console.warn("Exact device constraints failed, using fallback");
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 24000,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } else {
        throw error;
      }
    }

    this.recorder.start(stream);

    // Tell the backend to include audio in responses
    this.switchModality(["text", "audio"]);
  }

  async stopAudio() {
    if (this.recorder) {
      this.recorder.stop();
      this.recorder = null;
    }
    if (this.player) {
      this.player.clear();
      this.player = null;
    }

    // Tell the backend to go back to text-only
    this.switchModality(["text"]);
  }

  // ---- Cleanup -------------------------------------------------------------

  dispose() {
    this.disposed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    // Stop audio without sending modality_switch (socket may already be closing)
    if (this.recorder) {
      this.recorder.stop();
      this.recorder = null;
    }
    if (this.player) {
      this.player.clear();
      this.player = null;
    }
    if (this.socket) {
      this.socket.onclose = null; // prevent reconnect on intentional close
      this.socket.close();
      this.socket = null;
    }
  }

  /** Force reconnect (e.g. user clicks beacon to reset connection) */
  reconnect() {
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    this.reconnectAttempt = 0;
    this.connect();
  }

  // ---- Internal helpers ----------------------------------------------------

  private sendRaw(message: object) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }
}
