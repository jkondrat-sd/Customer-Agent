"use client";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { TraceSidebar } from "@/components/trace/TraceSidebar";
import { useStreamedChat } from "@/lib/useStreamedChat";
import { useEffect, useRef } from "react";
export default function Home() {
  const { messages, sendMessage, isStreaming, currentMetadata, sessionId } = useStreamedChat();
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <main className="min-h-screen p-4 md:p-8 flex flex-col gap-6 animate-fade-in-up">
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">
            FlowDesk
          </h1>
          <div className="h-6 w-px bg-border-hairline hidden md:block" />
          <span className="text-ink-muted text-sm font-medium hidden md:block">Demo Workspace</span>
        </div>
        
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-ink-muted/70 font-mono bg-surface-glass px-3 py-1.5 rounded-full border border-border-hairline">
          <span>LangGraph</span>
          <span className="text-accent-clay">→</span>
          <span>Pinecone</span>
          <span className="text-accent-clay">→</span>
          <span>Groq/Gemini</span>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChatPanel 
          messages={messages} 
          sessionId={sessionId} 
          isStreaming={isStreaming} 
          onSendMessage={sendMessage} 
          chatEndRef={chatEndRef} 
        />
        <TraceSidebar currentMetadata={currentMetadata} />
      </div>
    </main>
  );
}
