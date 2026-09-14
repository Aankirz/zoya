import type { CSSProperties } from "react";

// Waveform dots, heyclicky's voice motif: [height px, opacity] per dot. They dance when `active`.
const WAVE = [
  [6, 0.3], [10, 0.5], [22, 0.85], [10, 1], [28, 1], [10, 1], [10, 1],
  [14, 1], [34, 1], [10, 1], [24, 0.85], [12, 0.5], [6, 0.3],
] as const;

export function Waveform({ active = false }: { active?: boolean }) {
  return (
    <span className="wave" data-active={active} aria-hidden="true">
      {WAVE.map(([height, opacity], i) => (
        <span key={i} style={{ "--h": `${height}px`, "--o": opacity, "--i": i } as CSSProperties} />
      ))}
    </span>
  );
}

// Glossy speech bubble. The invisible sizer reserves the full width so typing never shifts the layout.
export function GlossyBubble({ text, typed, typing, idle = false }: { text: string; typed: string; typing: boolean; idle?: boolean }) {
  return (
    <span className="bubble-glossy" aria-hidden="true">
      <span className="bubble-sizer">{text}</span>
      <span className="bubble-typed">
        {idle ? (
          <span className="bubble-dots">
            <i />
            <i />
            <i />
          </span>
        ) : (
          typed
        )}
        {typing ? <span className="caret" /> : null}
      </span>
    </span>
  );
}
