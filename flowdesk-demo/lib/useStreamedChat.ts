import { useState, useRef, useEffect } from "react";
import { ChatMessage, TurnMetadata, StreamEvent } from "./types";

export function useStreamedChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentMetadata, setCurrentMetadata] = useState<TurnMetadata | null>(null);
  
  // Use a ref to persist session_id across streams per the Phase 2 requirements
  const sessionIdRef = useRef<string | null>(null);

  async function sendMessage(text: string) {
    if (!text.trim() || isStreaming) return;
    
    setIsStreaming(true);
    setCurrentMetadata(null);
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: text }]);
    
    const assistantIndex = messages.length + 1; // It will be inserted right after the user message
    const assistantMsgId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: assistantMsgId, role: "assistant", content: "" }]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        body: JSON.stringify({ 
          message: text,
          session_id: sessionIdRef.current
        }),
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        throw new Error("Failed to connect to chat API");
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Split by the double newline boundary for SSE events
        const chunks = buffer.split("\n\n");
        
        // Keep the last partial chunk in the buffer if it didn't end with \n\n
        buffer = chunks.pop() || "";
        
        for (const chunk of chunks) {
          const trimmed = chunk.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          
          const jsonStr = trimmed.substring(6); // remove "data: "
          if (jsonStr === "[DONE]") continue; // standard SSE end marker if any
          
          try {
            const event: StreamEvent = JSON.parse(jsonStr);
            if (event.type === "token") {
              setMessages((prev) => {
                const next = [...prev];
                // Ensure we don't index out of bounds in case of race conditions
                if (next[assistantIndex]) {
                  next[assistantIndex] = {
                    ...next[assistantIndex],
                    content: next[assistantIndex].content + event.content,
                  };
                }
                return next;
              });
            } else if (event.type === "metadata") {
              setCurrentMetadata(event as TurnMetadata);
              setMessages((prev) => {
                const next = [...prev];
                if (next[assistantIndex]) {
                  next[assistantIndex] = {
                    ...next[assistantIndex],
                    intent: event.intent,
                    confidence: event.confidence
                  };
                }
                return next;
              });
            } else if (event.type === "done") {
              setIsStreaming(false);
            } else if (event.type === "error") {
              console.error("Backend returned an error during stream:", event.detail);
              setIsStreaming(false);
            }
          } catch (e) {
            console.error("Failed to parse SSE event", e, jsonStr);
          }
        }
      }
    } catch (error) {
      console.error("Chat streaming error:", error);
      setIsStreaming(false);
    }
  }

  return { messages, sendMessage, isStreaming, currentMetadata, sessionId: sessionIdRef.current };
}
