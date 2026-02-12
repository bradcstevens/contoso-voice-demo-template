import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";
import { removeCachedBlob } from "./images";
import { persist, createJSONStorage } from "zustand/middleware";
import type { DigiKeyProduct } from "@/types/digikey";
import { matchProductsFromText } from "./product-detector";

export const AssistantName = "Wiry";

export interface Turn {
  name: string;
  avatar: string | null;
  image: string | null;
  message: string;
  status: "waiting" | "streaming" | "done" | "voice";
  type: "user" | "assistant";
  /** Products detected in the assistant's response, displayed as inline cards */
  products?: DigiKeyProduct[];
}

export interface ChatState {
  threadId: string;
  open: boolean;
  turns: Turn[];
  message: string;
  currentImage: string | null;
  setOpen: (open: boolean) => void;
  setMessage: (message: string) => void;
  setCurrentImage: (image: string | null) => void;
  sendFullMessage: (turn: Turn) => void;
  sendMessage: (name: string, avatar: string) => void;
  addAssistantMessage: (
    name: string,
    message: string,
    avatar?: string,
    image?: string
  ) => void;
  startAssistantMessage: (
    name: string,
    avatar?: string,
    image?: string
  ) => void;
  streamAssistantMessage: (chunk: string) => void;
  completeAssistantMessage: () => void;
  resetChat: () => void;
  setThreadId: (threadId: string) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      threadId: uuidv4(),
      open: false,
      turns: [],
      message: "",
      currentImage: null,
      setOpen: (open) => set({ open: open }),
      setMessage: (message) => set({ message: message }),
      setCurrentImage: (image) => set({ currentImage: image }),
      sendFullMessage: (turn: Turn) =>
        set((state) => {
          if (!turn.message || turn.message.length === 0) return state;
          return {
            turns: [...state.turns, turn],
            message: "",
            currentImage: null,
          };
        }),
      sendMessage: (name, avatar) =>
        set((state) => {
          if (!state.message || state.message.length === 0) return state;
          return {
            turns: [
              ...state.turns,
              {
                name: name,
                avatar: avatar,
                image: state.currentImage,
                message: state.message,
                status: "done",
                type: "user",
              },
            ],
            message: "",
            currentImage: null,
          };
        }),
      addAssistantMessage: (name, message, avatar, image) =>
        set((state) => {
          // Detect product references in the full message
          const products = matchProductsFromText(message);
          return {
            turns: [
              ...state.turns,
              {
                name: name,
                avatar: avatar || null,
                image: image || null,
                message: message,
                status: "done" as const,
                type: "assistant" as const,
                ...(products.length > 0 ? { products } : {}),
              },
            ],
          };
        }),
      startAssistantMessage: (name, avatar, image) =>
        set((state) => ({
          turns: [
            ...state.turns,
            {
              name: name,
              avatar: avatar || null,
              image: image || null,
              message: "",
              status: "waiting",
              type: "assistant",
            },
          ],
        })),
      streamAssistantMessage: (chunk) =>
        set((state) => {
          const turns = state.turns.slice(0, -1);
          const lastTurn = state.turns.slice(-1)[0];
          const updatedTurn = {
            name: lastTurn.name,
            avatar: lastTurn.avatar,
            image: lastTurn.image,
            message:
              lastTurn.type === "assistant" &&
              (lastTurn.status === "waiting" || lastTurn.status === "streaming")
                ? lastTurn.message + chunk
                : chunk,
            status: "streaming" as const,
            type: "assistant" as const,
          };
          return { turns: [...turns, updatedTurn] };
        }),
      completeAssistantMessage: () =>
        set((state) => {
          const turns = state.turns.slice(0, -1);
          const lastTurn = { ...state.turns.slice(-1)[0] };
          if (
            lastTurn.type === "assistant" &&
            lastTurn.status === "streaming"
          ) {
            lastTurn.status = "done";
            // Detect product references in the completed message
            const products = matchProductsFromText(lastTurn.message);
            if (products.length > 0) {
              lastTurn.products = products;
            }
          }
          return { turns: [...turns, lastTurn] };
        }),
      resetChat: () =>
        set((state) => {
          // clear image cache
          state.turns.forEach((turn) => {
            if (turn.image) {
              removeCachedBlob(turn.image);
            }
          });
          if (state.currentImage) {
            removeCachedBlob(state.currentImage);
          }
          return { threadId: uuidv4(), turns: [], message: "", currentImage: null };
        }),
      setThreadId: (threadId) => set({ threadId: threadId }),
    }),
    {
      name: "chat-storage",
      storage: createJSONStorage(() => localStorage),
    }
  )
);