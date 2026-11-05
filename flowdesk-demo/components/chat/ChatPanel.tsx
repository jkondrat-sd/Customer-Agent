import { RefObject } from "react";
import { GlassCard } from "@/components/layout/GlassCard";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { ExamplePrompts } from "@/components/chat/ExamplePrompts";
import { ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  sessionId: string | null;
  isStreaming: boolean;
  onSendMessage: (text: string) => void;
  chatEndRef: RefObject<HTMLDivElement>;
}

export function ChatPanel({
  messages,
  sessionId,
  isStreaming,
  onSendMessage,
  chatEndRef
}: ChatPanelProps) {
  return (
    <GlassCard className="lg:col-span-2 flex flex-col h-[75vh]">
      <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="text-ink-muted text-center mt-auto mb-auto">
            Welcome to FlowDesk. How can I help you today?
          </div>
        ) : (
          messages.map((msg, i) => (
            <MessageBubble key={msg.id || i} message={msg} sessionId={sessionId} />
          ))
        )}
        <div ref={chatEndRef} />
      </div>
      <div className="p-4 border-t border-border-hairline">
        <ExamplePrompts onSelect={onSendMessage} />
        <ChatInput onSendMessage={onSendMessage} isStreaming={isStreaming} />
      </div>
    </GlassCard>
  );
}
