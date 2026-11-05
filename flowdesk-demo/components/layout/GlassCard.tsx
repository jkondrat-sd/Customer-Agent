import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
}

export function GlassCard({ children, className = "" }: GlassCardProps) {
  return (
    <div
      className={`bg-surface-glass backdrop-blur-md border border-border-hairline rounded-2xl shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}
