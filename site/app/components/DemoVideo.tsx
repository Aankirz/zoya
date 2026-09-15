"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import { DEMO } from "../copy";
import { MacLights } from "./MacWindow";

// Click to load: nothing is requested from youtube until the visitor presses play.
export function DemoVideo() {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [playing, setPlaying] = useState(false);

  return (
    <div className="mac-window demo-window">
      <div className="mac-titlebar" aria-hidden="true">
        <MacLights />
        <span className="mac-title">{DEMO.windowTitle}</span>
      </div>
      <div className="demo-frame">
        {playing ? (
          <iframe
            ref={frameRef}
            src={DEMO.embedSrc}
            title={DEMO.frameTitle}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            onLoad={() => frameRef.current?.focus()}
          />
        ) : (
          <>
            <Image src={DEMO.thumbnail} alt={DEMO.thumbnailAlt} width={1280} height={720} loading="lazy" sizes="(min-width: 46rem) 46rem, 100vw" />
            <button type="button" className="pill-glossy demo-play" aria-label={DEMO.playLabel} onClick={() => setPlaying(true)}>
              {DEMO.play}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
