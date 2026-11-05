export function ConfidenceRing({ confidence }: { confidence: number }) {
  const circumference = 2 * Math.PI * 18;
  const offset = circumference * (1 - confidence);
  const color = confidence > 0.7 ? "var(--accent-lavender)" : "var(--accent-clay)";
  
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="overflow-visible">
      <circle cx="22" cy="22" r="18" fill="none" stroke="var(--border-hairline)" strokeWidth="3" />
      <circle
        cx="22" cy="22" r="18" fill="none" stroke={color} strokeWidth="3"
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 22 22)"
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text x="22" y="26" textAnchor="middle" fontSize="11" fontFamily="var(--font-jetbrains-mono), monospace" fill="var(--ink)">
        {Math.round(confidence * 100)}
      </text>
    </svg>
  );
}
