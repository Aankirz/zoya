"use client";

import { useEffect, useState } from "react";

const TICK_MS = 30_000;

function now(): string {
  return new Date().toLocaleTimeString("en", { hour: "numeric", minute: "2-digit" }).toLowerCase();
}

// Decorative menu-bar clock showing the visitor's own time. Empty on the server to avoid a hydration mismatch.
export function MenuClock() {
  const [time, setTime] = useState("");

  useEffect(() => {
    const first = setTimeout(() => setTime(now()), 0);
    const tick = setInterval(() => setTime(now()), TICK_MS);
    return () => {
      clearTimeout(first);
      clearInterval(tick);
    };
  }, []);

  return <span className="menubar-clock">{time}</span>;
}
