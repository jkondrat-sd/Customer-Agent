export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  confidence?: number;
}

export interface TurnMetadata {
  type: "metadata";
  intent: string;
  confidence: number;
  retries: number;
  retrieved_chunks: { source: string; score: number }[];
}
export interface TokenEvent {
  type: "token";
  content: string;
}

export interface DoneEvent {
  type: "done";
}

export interface ErrorEvent {
  type: "error";
  detail: string;
}

export type StreamEvent = TokenEvent | TurnMetadata | DoneEvent | ErrorEvent;

export interface FeedbackPayload {
  message_id: string;
  session_id: string | null;
  rating: "up" | "down";
  confidence?: number;
  intent?: string;
}
