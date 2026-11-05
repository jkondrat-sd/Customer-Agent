import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { SendHorizontal, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isStreaming: boolean;
}

export function ChatInput({ onSendMessage, isStreaming }: ChatInputProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (text.trim() && !isStreaming) {
      onSendMessage(text);
      setText("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  return (
    <div className="bg-surface-base rounded-2xl border border-border-hairline p-2 flex items-end gap-2 focus-within:ring-2 focus-within:ring-accent-lavender/50 transition-shadow">
      <textarea
        ref={inputRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question... (Cmd/Ctrl + Enter to send)"
        className="flex-1 bg-transparent outline-none placeholder:text-ink-muted/50 text-ink resize-none min-h-[44px] max-h-[120px] p-3 rounded-xl"
        rows={1}
        disabled={isStreaming}
      />
      <button
        onClick={handleSubmit}
        disabled={!text.trim() || isStreaming}
        className="p-3 mb-1 rounded-xl bg-ink text-surface-base hover:bg-ink/80 disabled:opacity-50 disabled:hover:bg-ink transition-colors flex-shrink-0"
      >
        {isStreaming ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <SendHorizontal className="w-5 h-5" />
        )}
      </button>
    </div>
  );
}
