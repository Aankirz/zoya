"use client";

import { useEffect, useRef, useState } from "react";
import { CLIP } from "../copy";

const LEVEL_GAIN = 4;
const FFT_SIZE = 512;

type Graph = { context: AudioContext; analyser: AnalyserNode; samples: Uint8Array<ArrayBuffer> };

// Split the transcript into word spans using the Polly speech-mark character offsets.
const WORDS = CLIP.marks.map(([ms, start], i) => ({
  ms,
  text: CLIP.text.slice(start, CLIP.marks[i + 1]?.[1] ?? CLIP.text.length),
}));

function wordAt(ms: number): number {
  let index = -1;
  WORDS.forEach((word, i) => {
    if (word.ms <= ms) index = i;
  });
  return index;
}

function setOrbLevel(level: number) {
  const root = document.documentElement;
  root.style.setProperty("--zoya-level", level.toFixed(3));
  if (level > 0) root.dataset.zoya = "speaking";
  else delete root.dataset.zoya;
}

function readLevel(graph: Graph): number {
  graph.analyser.getByteTimeDomainData(graph.samples);
  let sum = 0;
  for (const sample of graph.samples) sum += ((sample - 128) / 128) ** 2;
  return Math.min(1, Math.sqrt(sum / graph.samples.length) * LEVEL_GAIN);
}

function createGraph(audio: HTMLAudioElement): Graph | null {
  try {
    const context = new AudioContext();
    const analyser = context.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    context.createMediaElementSource(audio).connect(analyser);
    analyser.connect(context.destination);
    return { context, analyser, samples: new Uint8Array(analyser.fftSize) };
  } catch {
    return null; // ponytail: no Web Audio means no orb reaction; the clip and transcript still work
  }
}

export function HearZoya() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const frameRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [wordIndex, setWordIndex] = useState(-1);

  useEffect(() => () => cancelAnimationFrame(frameRef.current), []);

  function tick() {
    const audio = audioRef.current;
    if (!audio) return;
    if (graphRef.current) setOrbLevel(readLevel(graphRef.current));
    setWordIndex(wordAt(audio.currentTime * 1000));
    frameRef.current = requestAnimationFrame(tick);
  }

  function stopTicking() {
    cancelAnimationFrame(frameRef.current);
    setOrbLevel(0);
    setPlaying(false);
  }

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) return audio.pause();
    graphRef.current ??= createGraph(audio);
    await graphRef.current?.context.resume();
    try {
      await audio.play();
    } catch {
      stopTicking();
    }
  }

  function handlePlay() {
    setPlaying(true);
    frameRef.current = requestAnimationFrame(tick);
  }

  function handleEnded() {
    stopTicking();
    setWordIndex(-1);
  }

  return (
    <div className="clip">
      <button type="button" className="hear" onClick={toggle}>
        <span className="hear-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20">
            {playing ? (
              <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" />
            ) : (
              <path d="M8 5.2v13.6a.8.8 0 0 0 1.2.7l10.6-6.8a.8.8 0 0 0 0-1.4L9.2 4.5A.8.8 0 0 0 8 5.2z" />
            )}
          </svg>
        </span>
        <span>{playing ? CLIP.pauseLabel : CLIP.playLabel}</span>
      </button>
      <audio
        ref={audioRef}
        src={CLIP.src}
        preload="none"
        onPlay={handlePlay}
        onPause={stopTicking}
        onEnded={handleEnded}
      />
      <p className="clip-label">{CLIP.label}</p>
      <p className="transcript sr-only">“{CLIP.text}”</p>
      <p className="transcript" aria-hidden="true" data-playing={playing || wordIndex >= 0}>
        “
        {WORDS.map((word, i) => (
          <span
            key={word.ms}
            className={i < wordIndex ? "word is-said" : i === wordIndex ? "word is-current" : "word"}
          >
            {word.text}
          </span>
        ))}
        ”
      </p>
    </div>
  );
}
