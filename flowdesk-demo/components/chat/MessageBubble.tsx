import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage } from "@/lib/types";
import { ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { useState } from "react";
import { GlassCard } from "@/components/layout/GlassCard";

interface MessageBubbleProps {
  message: ChatMessage;
  sessionId: string | null;
}

export function MessageBubble({ message, sessionId }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [hasRated, setHasRated] = useState(false);
  const [rating, setRating] = useState<"up" | "down" | null>(null);

  const handleFeedback = async (vote: "up" | "down") => {
    if (hasRated || !message.id) return;
    setHasRated(true);
    setRating(vote);

    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: message.id,
          session_id: sessionId,
          rating: vote,
          confidence: message.confidence,
          intent: message.intent
        })
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const Wrapper = isUser ? "div" : GlassCard;
  
  return (
    <div className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
      <Wrapper
        className={`max-w-[85%] px-5 py-3 ${
          isUser
            ? "rounded-2xl rounded-br-sm bg-ink/90 text-surface-base shadow-sm"
            : "!rounded-bl-sm text-ink"
        }`}
      >
        <div className="prose prose-sm md:prose-base prose-p:text-current prose-headings:text-current prose-strong:text-current prose-a:text-current prose-code:text-current prose-li:text-current max-w-none">
          {message.content === "" ? (
            <span className="inline-block w-2 h-4 bg-ink-muted/50 animate-pulse" />
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          )}
        </div>
      </Wrapper>
      
      {!isUser && message.content && (
        <div className="flex items-center gap-2 mt-1 ml-2">
          {hasRated ? (
            <div className="flex items-center gap-1 text-[10px] text-ink-muted/60 transition-all duration-300">
              <Check className="w-3 h-3" />
              <span>Feedback submitted</span>
            </div>
          ) : (
            <>
              <button 
                onClick={() => handleFeedback("up")}
                className="p-1 rounded text-ink-muted/40 hover:text-ink-muted hover:bg-surface-base transition-colors"
                aria-label="Helpful"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>
              <button 
                onClick={() => handleFeedback("down")}
                className="p-1 rounded text-ink-muted/40 hover:text-ink-muted hover:bg-surface-base transition-colors"
                aria-label="Not helpful"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
