"use client";

import { useEffect, useRef, useState } from "react";
import { HELLO } from "../copy";
import { GlassMicrophone, OutlinePlay, OutlineStop } from "../icons/rune";
import { MacLights } from "./Props";
import { GlossyBubble, Waveform } from "./Talk";

// Typing runs slightly ahead of the voice so the words land as she says them.
const TYPE_LEAD = 1.15;

type Phase = "idle" | "playing" | "done";

// heyclicky's big hello.mov window, as a Mac window that plays Zoya's real greeting (Polly Kajal).
export function HelloWindow() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const frameRef = useRef(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);

  useEffect(() => () => cancelAnimationFrame(frameRef.current), []);

  function tick() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.duration > 0) setProgress(Math.min(1, (audio.currentTime / audio.duration) * TYPE_LEAD));
    frameRef.current = requestAnimationFrame(tick);
  }

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }
    setProgress(0);
    try {
      await audio.play();
    } catch {
      setPhase("idle");
    }
  }

  function handlePlay() {
    setPhase("playing");
    frameRef.current = requestAnimationFrame(tick);
  }

  function handleStop() {
    cancelAnimationFrame(frameRef.current);
    setPhase((current) => (current === "playing" ? "done" : current));
  }

  function handleEnded() {
    handleStop();
    setProgress(1);
  }

  const playing = phase === "playing";
  const typedCount = Math.round(HELLO.bubble.length * progress);

  return (
    <div className="hello">
      <div className="mac-window hello-window">
        <div className="mac-titlebar" aria-hidden="true">
          <MacLights />
          <span className="mac-title">
            <GlassMicrophone className="title-glyph" />
            {HELLO.windowTitle}
          </span>
        </div>
        <div className="hello-body desktop-dots">
          <Waveform active={playing} />
          <GlossyBubble
            text={HELLO.bubble}
            typed={HELLO.bubble.slice(0, typedCount)}
            typing={playing && typedCount < HELLO.bubble.length}
            idle={phase === "idle"}
          />
          <button type="button" className="pill-glossy hello-play" onClick={toggle}>
            {playing ? <OutlineStop className="pill-icon" /> : <OutlinePlay className="pill-icon" />}
            <span>{playing ? HELLO.stopLabel : HELLO.playLabel}</span>
          </button>
          <p className="sr-only">
            {HELLO.transcriptLead} {HELLO.transcript}
          </p>
        </div>
      </div>
      <p className="window-caption" aria-hidden="true">
        {HELLO.caption}
      </p>
      <audio
        ref={audioRef}
        src={HELLO.src}
        preload="none"
        onPlay={handlePlay}
        onPause={handleStop}
        onEnded={handleEnded}
      />
    </div>
  );
}
