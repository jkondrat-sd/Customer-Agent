interface ExamplePromptsProps {
  onSelect: (text: string) => void;
}

const PROMPTS = [
  "How do I reset my password?",
  "What is your refund policy?",
  "Where is my order #12345?",
  "Can you write a python script for me?" // Out of scope
];

export function ExamplePrompts({ onSelect }: ExamplePromptsProps) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {PROMPTS.map((prompt, i) => (
        <button
          key={i}
          onClick={() => onSelect(prompt)}
          className="text-xs text-ink-muted bg-surface-glass border border-border-hairline px-3 py-1.5 rounded-full hover:bg-surface-base hover:text-ink transition-colors focus:outline-none focus:ring-2 focus:ring-accent-lavender/50 text-left"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
