interface IntentBadgeProps {
  intent: string;
}

export function IntentBadge({ intent }: IntentBadgeProps) {
  // Map common intents to soft colors (could expand based on the backend intent model)
  const isFallback = 
    intent.toLowerCase() === "unknown" || 
    intent.toLowerCase() === "escalate" || 
    intent.toLowerCase() === "complex" || 
    intent.toLowerCase() === "out_of_scope";
  
  return (
    <div className={`inline-flex px-3 py-1 bg-surface-base border border-border-hairline rounded-full w-fit text-sm font-medium ${isFallback ? 'text-accent-clay' : 'text-ink'}`}>
      {intent}
    </div>
  );
}
