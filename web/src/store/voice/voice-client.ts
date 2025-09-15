//import { Player, Recorder } from "./voice";
import { Player, Recorder } from ".";
import { WebSocketClient } from "./websocket-client";

export interface Message {
  type: "user" | "assistant" | "audio" | "console" | "interrupt" | "messages" | "function";
  payload: string;
}

export interface SimpleMessage {
  name: string;
  text: string;
}

class VoiceClient {
  url: string | URL;
  socket: WebSocketClient<Message, Message> | null;
  player: Player | null;
  recorder: Recorder | null;
  handleServerMessage: (message: Message) => Promise<void>;
  setTalking: (talking: boolean) => void;

  constructor(
    url: string | URL,
    handleServerMessage: (message: Message) => Promise<void>,
    setTalking: (talking: boolean) => void
  ) {
    this.url = url;
    this.handleServerMessage = handleServerMessage;
    this.setTalking = setTalking;
    this.socket = null;
    this.player = null;
    this.recorder = null;
  }

  async start(deviceId: string | null = null) {
    console.log("Starting voice client");
    
    // Only start voice client in browser environment
    if (typeof window === 'undefined') {
      console.warn('VoiceClient start skipped: not in browser environment');
      return;
    }

    this.socket = new WebSocketClient<Message, Message>(this.url);

    this.player = new Player(this.setTalking);

    await this.player.init(24000);

    /* eslint-disable @typescript-eslint/no-explicit-any */
    this.recorder = new Recorder((buffer: any) => {
      const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
      this.socket!.send({ type: "audio", payload: base64 });
    });

    let audio: object = {
      sampleRate: 24000,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    if (deviceId && deviceId !== "default") {
      console.log("Using device:", deviceId);
      audio = { ...audio, deviceId: { exact: deviceId } };
    }

    console.log(audio);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: audio,
      });
    } catch (error) {
      if (error instanceof Error && error.name === 'OverconstrainedError') {
        console.warn('Exact device constraints failed, trying with fallback audio settings');
        // Fallback to basic audio constraints without specific device
        const fallbackAudio = {
          sampleRate: 24000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        };
        stream = await navigator.mediaDevices.getUserMedia({
          audio: fallbackAudio,
        });
      } else {
        throw error;
      }
    }

    this.recorder.start(stream);
    this.startResponseListener();
  }

  async startResponseListener() {
    if (!this.socket) {
      return;
    }

    try {
      for await (const serverEvent of this.socket) {

        if (serverEvent.type === "audio") {
          // handle audio case internally
          const buffer = Uint8Array.from(atob(serverEvent.payload), (c) =>
            c.charCodeAt(0)
          ).buffer;
          this.player!.play(new Int16Array(buffer));
        } else if (serverEvent.type === "interrupt") {
          // handle interrupt case internally
          this.player!.clear();
        } else {
          this.handleServerMessage(serverEvent);
        }
      }
    } catch (error) {
      if (this.socket) {
        console.error("Response iteration error:", error);
      }
    }
  }

  async stop() {
    if (this.socket) {
      this.player?.clear();
      this.recorder?.stop();
      await this.socket.close();
    }
  }

  async send(message: Message) {
    if (this.socket) {
      this.socket.send(message);
    }
  }

  async sendUserMessage(message: string) {
    this.send({ type: "user", payload: message });
  }

  async sendCreateResponse() {
    this.send({ type: "interrupt", payload: "" });
  }
}

export default VoiceClient;
