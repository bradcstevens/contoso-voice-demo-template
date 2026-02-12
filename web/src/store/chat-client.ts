// ---------------------------------------------------------------------------
// ChatClient - text-only WebSocket client for /api/chat
//
// This client handles text chat communication via the backend's /api/chat
// endpoint, which uses the standard prompty-based chat pipeline. No Azure
// OpenAI Realtime API connection is needed for text chat.
//
// The backend protocol for /api/chat:
//   1. Client sends: { threadId: string } (first message to identify session)
//   2. Client sends: { name: string, text: string, image?: string } (user messages)
//   3. Server sends: SocketMessage objects with type "assistant" | "context" | "action"
// ---------------------------------------------------------------------------

import { WS_ENDPOINT } from "@/store/endpoint";

/** Backend SocketMessage shape (matches api/models.py) */
export interface SocketMessage {
  type: "action" | "assistant" | "context";
  payload: AssistantPayload | ContextPayload | ActionPayload;
}

export interface AssistantPayload {
  state: "start" | "stream" | "complete" | "full";
  payload?: string;
}

export interface ContextPayload {
  type: "action" | "user" | "issue" | "article";
  payload: string;
}

export interface ActionPayload {
  name: string;
  arguments: string;
}

/** Callbacks for ChatClient events */
export interface ChatClientCallbacks {
  onAssistantStart: () => void;
  onAssistantStream: (chunk: string) => void;
  onAssistantComplete: () => void;
  onAssistantFull: (message: string) => void;
  onContext: (context: string) => void;
  onAction: (name: string, args: string) => void;
  onConnectionChange: (connected: boolean) => void;
}

export class ChatClient {
  private socket: WebSocket | null = null;
  private threadId: string;
  private callbacks: ChatClientCallbacks;
  private disposed = false;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private initialMessageSent = false;

  private static MAX_RECONNECT = 8;
  private static BASE_DELAY_MS = 1000;

  constructor(threadId: string, callbacks: ChatClientCallbacks) {
    this.threadId = threadId;
    this.callbacks = callbacks;
    this.connect();
  }

  // ---- Connection lifecycle ------------------------------------------------

  private connect() {
    if (this.disposed) return;

    const endpoint = WS_ENDPOINT.endsWith("/")
      ? WS_ENDPOINT.slice(0, -1)
      : WS_ENDPOINT;

    try {
      this.socket = new WebSocket(`${endpoint}/api/chat`);
    } catch (err) {
      console.error("ChatClient: failed to create WebSocket", err);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.initialMessageSent = false;
      // Send thread ID as first message (backend protocol requirement)
      this.sendRaw({ threadId: this.threadId });
      this.initialMessageSent = true;
      this.callbacks.onConnectionChange(true);
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const msg: SocketMessage = JSON.parse(event.data as string);
        this.handleIncomingMessage(msg);
      } catch (err) {
        console.error("ChatClient: failed to parse message", err);
      }
    };

    this.socket.onerror = () => {
      console.warn("ChatClient: WebSocket error (will retry)");
    };

    this.socket.onclose = () => {
      this.callbacks.onConnectionChange(false);
      if (!this.disposed) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect() {
    if (this.disposed) return;
    if (this.reconnectAttempt >= ChatClient.MAX_RECONNECT) {
      console.warn("ChatClient: max reconnection attempts reached");
      return;
    }

    const delay = ChatClient.BASE_DELAY_MS * Math.pow(2, this.reconnectAttempt);
    this.reconnectAttempt++;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  // ---- Incoming message routing -------------------------------------------

  private handleIncomingMessage(msg: SocketMessage) {
    switch (msg.type) {
      case "assistant": {
        const payload = msg.payload as AssistantPayload;
        switch (payload.state) {
          case "start":
            this.callbacks.onAssistantStart();
            break;
          case "stream":
            if (payload.payload) {
              this.callbacks.onAssistantStream(payload.payload);
            }
            break;
          case "complete":
            this.callbacks.onAssistantComplete();
            break;
          case "full":
            if (payload.payload) {
              this.callbacks.onAssistantFull(payload.payload);
            }
            break;
        }
        break;
      }
      case "context": {
        const payload = msg.payload as ContextPayload;
        if (payload.type === "user") {
          this.callbacks.onContext(payload.payload);
        }
        break;
      }
      case "action": {
        const payload = msg.payload as ActionPayload;
        this.callbacks.onAction(payload.name, payload.arguments);
        break;
      }
    }
  }

  // ---- Public API ----------------------------------------------------------

  get connected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN && this.initialMessageSent;
  }

  /** Send a text chat message.
   *
   * The backend ChatSession.receive_chat() expects:
   *   { name: string, text: string, image?: string }
   */
  sendMessage(name: string, text: string, image?: string | null) {
    const msg: { name: string; text: string; image?: string } = { name, text };
    if (image) {
      msg.image = image;
    }
    this.sendRaw(msg);
  }

  /** Update the thread ID (e.g., after a chat reset) */
  updateThreadId(threadId: string) {
    this.threadId = threadId;
    // Reconnect with the new thread ID
    this.reconnect();
  }

  /** Force reconnect */
  reconnect() {
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    this.reconnectAttempt = 0;
    this.connect();
  }

  /** Clean up */
  dispose() {
    this.disposed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
  }

  // ---- Internal helpers ----------------------------------------------------

  private sendRaw(message: object) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }
}
