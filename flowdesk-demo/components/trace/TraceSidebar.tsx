import { GlassCard } from "@/components/layout/GlassCard";
import { ConfidenceRing } from "@/components/trace/ConfidenceRing";
import { IntentBadge } from "@/components/trace/IntentBadge";
import { RetrievedChunks } from "@/components/trace/RetrievedChunks";
import { TurnMetadata } from "@/lib/types";

interface TraceSidebarProps {
  currentMetadata: TurnMetadata | null;
}

export function TraceSidebar({ currentMetadata }: TraceSidebarProps) {
  return (
    <GlassCard className="hidden lg:flex flex-col h-[75vh]">
      <div className="p-4 border-b border-border-hairline">
        <h2 className="font-serif text-xl font-semibold text-ink">Trace & Metadata</h2>
      </div>
      <div className="flex-1 p-6 overflow-y-auto">
        {currentMetadata ? (
          <div className="flex flex-col gap-8">
            <div className="flex flex-col gap-2">
              <span className="text-xs uppercase tracking-wider text-ink-muted font-bold">Intent</span>
              <IntentBadge intent={currentMetadata.intent} />
            </div>
            
            <div className="flex flex-col gap-2">
              <span className="text-xs uppercase tracking-wider text-ink-muted font-bold">Confidence</span>
              <div className="flex items-center gap-4">
                <ConfidenceRing confidence={currentMetadata.confidence} />
                <span className="text-sm text-ink-muted">
                  {currentMetadata.confidence > 0.7 ? "High certainty" : "Low certainty / Fallback"}
                </span>
              </div>
            </div>

            <RetrievedChunks chunks={currentMetadata.retrieved_chunks} />

            <div className="flex flex-col gap-2">
              <span className="text-xs uppercase tracking-wider text-ink-muted font-bold">Retries</span>
              {currentMetadata.retries > 0 ? (
                <div className="text-sm text-accent-clay font-medium flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-clay" />
                  {currentMetadata.retries} {currentMetadata.retries === 1 ? "attempt" : "attempts"} to recover
                </div>
              ) : (
                <div className="text-sm text-ink-muted italic">
                  0 retries (first attempt)
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-ink-muted text-sm text-center mt-10">
            No trace data available yet. Send a message to see the agent&apos;s reasoning.
          </div>
        )}
      </div>
    </GlassCard>
  );
}
