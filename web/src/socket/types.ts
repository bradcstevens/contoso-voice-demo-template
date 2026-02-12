export interface Message {
  type: "user" | "assistant" | "assistant_delta" | "audio" | "console" | "interrupt" | "messages" | "function" | "text" | "voice_start" | "voice_stop" | "modality_switch";
  payload: string;
}


export interface SimpleMessage {
  name: string;
  text: string;
}