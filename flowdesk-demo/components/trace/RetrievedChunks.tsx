interface RetrievedChunksProps {
  chunks: { source: string; score: number }[];
}

export function RetrievedChunks({ chunks }: RetrievedChunksProps) {
  if (!chunks || chunks.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <span className="text-xs uppercase tracking-wider text-ink-muted font-bold">Retrieved Context</span>
        <div className="text-sm text-ink-muted italic">
          No retrieval context required.
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs uppercase tracking-wider text-ink-muted font-bold">Retrieved Context</span>
      <div className="flex flex-col gap-2">
        {chunks.map((chunk, i) => (
          <div key={i} className="flex flex-col p-3 rounded-xl bg-surface-glass backdrop-blur-md border border-border-hairline shadow-sm gap-2 relative overflow-hidden">
            <div className="flex items-center justify-between z-10">
              <span className="text-sm font-medium text-ink truncate mr-2" title={chunk.source}>
                {chunk.source || "Unknown Source"}
              </span>
              <span className="text-[10px] font-mono text-ink-muted bg-surface-base px-1.5 py-0.5 rounded border border-border-hairline whitespace-nowrap">
                {chunk.score.toFixed(3)}
              </span>
            </div>
            <div className="w-full bg-surface-base h-1 rounded-full overflow-hidden z-10 border border-border-hairline/50">
              <div 
                className="h-full bg-accent-lavender rounded-full transition-all duration-500 ease-out" 
                style={{ 
                  width: `${Math.max(0, Math.min(100, chunk.score * 100))}%`,
                  opacity: 0.5 + (chunk.score * 0.5)
                }} 
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
