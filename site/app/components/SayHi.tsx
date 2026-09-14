"use client";

import { useEffect, useRef, useState } from "react";
import { SAY_HI } from "../copy";

const PULL_RADIUS_PX = 420;
const PULL_MAX_PX = 10;

// Hand-drawn line art of Zoya in profile, eyes closed, listening, with sound lines in front of her lips.
// pathLength=1 lets CSS draw every stroke in on load with one dash rule.
const FIGURE = [
  // face profile: forehead, nose, lips, chin, neck
  "M150 92 C176 92 196 108 200 132 C202 142 201 150 204 156 C210 168 220 180 222 188 C223 193 219 196 212 197 C208 198 207 203 210 206 C213 209 212 213 207 214 C211 217 211 222 206 225 C202 228 200 232 204 240 C206 250 196 258 184 258 C172 258 164 262 160 272 L164 318",
  "M176 139 C184 134 192 134 198 138", // brow
  "M178 152 C184 157 190 157 195 152", // closed eye
  "M182 156 L180 161 M188 157 L187 162 M193 155 L194 160", // lashes
  "M142 178 C128 170 118 180 122 194 C125 206 134 211 143 206", // ear
  "M134 212 C128 216 128 226 134 229 C140 232 145 225 142 218", // earring
  "M150 92 C118 84 84 100 76 134 C68 166 78 196 96 214 C104 226 106 240 108 254 C110 280 106 300 98 320", // head and nape
  "M92 206 C68 222 60 256 68 290 C72 306 68 318 58 330", // ponytail
  "M102 220 C84 244 82 274 90 302", // ponytail inner
  "M156 98 C130 100 110 118 102 148", // crown strand
  "M166 102 C144 112 128 134 126 162", // crown strand
  "M178 110 C160 124 150 146 154 172", // wisp in front of the ear
  "M152 94 C164 104 170 118 167 132", // fringe wisp
  "M118 300 C140 318 170 322 196 312", // neckline
  "M98 320 C78 330 58 342 42 360", // shoulder
  "M164 318 C198 326 228 338 252 360", // shoulder
];

const VOICE = [
  "M236 196 C246 206 246 224 236 234",
  "M256 180 C274 198 274 232 256 250",
  "M278 164 C302 190 302 240 278 266",
];

function ZoyaLineArt() {
  return (
    <svg className="line-art" viewBox="0 0 360 360" aria-hidden="true" focusable="false">
      <g className="figure">
        {FIGURE.map((d) => (
          <path key={d} pathLength={1} d={d} />
        ))}
      </g>
      <g className="voice">
        {VOICE.map((d, i) => (
          <path key={d} className={`arc arc-${i + 1}`} pathLength={1} d={d} />
        ))}
      </g>
    </svg>
  );
}

// "Move closer": the drawing leans a few pixels toward a nearby pointer. Off for reduced motion and touch.
function usePull(target: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = target.current;
    if (!element || matchMedia("(prefers-reduced-motion: reduce), (pointer: coarse)").matches) return;
    function onMove(event: PointerEvent) {
      const box = element!.getBoundingClientRect();
      const dx = event.clientX - (box.left + box.width / 2);
      const dy = event.clientY - (box.top + box.height / 2);
      const strength = Math.max(0, 1 - Math.hypot(dx, dy) / PULL_RADIUS_PX);
      const scale = (strength * PULL_MAX_PX) / Math.max(1, Math.hypot(dx, dy));
      element!.style.setProperty("--pull-x", `${(dx * scale).toFixed(2)}px`);
      element!.style.setProperty("--pull-y", `${(dy * scale).toFixed(2)}px`);
    }
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [target]);
}

export function SayHi() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const artRef = useRef<HTMLButtonElement>(null);
  const [speaking, setSpeaking] = useState(false);
  const [greeted, setGreeted] = useState(false);
  usePull(artRef);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }
    setGreeted(true);
    try {
      await audio.play();
    } catch {
      setSpeaking(false);
    }
  }

  return (
    <div className="say-hi" data-speaking={speaking} data-greeted={greeted}>
      <div className="say-hi-stage">
        <button ref={artRef} type="button" className="say-hi-button" onClick={toggle}>
          <ZoyaLineArt />
          <span className="sr-only">{speaking ? SAY_HI.stopLabel : SAY_HI.label}</span>
        </button>
        <p className="bubble">{SAY_HI.said}</p>
      </div>
      <p className="mono say-hi-hint" aria-hidden="true">
        {SAY_HI.hint[0]} · {SAY_HI.hint[1]}
      </p>
      <audio
        ref={audioRef}
        src={SAY_HI.src}
        preload="none"
        onPlay={() => setSpeaking(true)}
        onPause={() => setSpeaking(false)}
        onEnded={() => setSpeaking(false)}
      />
    </div>
  );
}
