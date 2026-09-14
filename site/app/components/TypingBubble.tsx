"use client";

import { useEffect, useRef, useState } from "react";
import { GlossyBubble } from "./Talk";

const MS_PER_CHAR = 110;
const VISIBLE_THRESHOLD = 0.6;

// Types its word once when it scrolls into view. Reduced motion shows the whole word at once.
export function TypingBubble({ text }: { text: string }) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [count, setCount] = useState(0);

  useEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    let timer = 0;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
          setCount(text.length);
          return;
        }
        let typed = 0;
        timer = window.setInterval(() => {
          typed += 1;
          setCount(typed);
          if (typed >= text.length) clearInterval(timer);
        }, MS_PER_CHAR);
      },
      { threshold: VISIBLE_THRESHOLD },
    );
    observer.observe(anchor);
    return () => {
      observer.disconnect();
      clearInterval(timer);
    };
  }, [text]);

  return (
    <span className="typing-anchor" ref={anchorRef}>
      <GlossyBubble text={text} typed={text.slice(0, count)} typing={count > 0 && count < text.length} />
    </span>
  );
}
