import type { CSSProperties } from "react";
import { APP_WINDOWS } from "../copy";
import { GlassLock, GlassMicrophone, GlassPause, OutlineHand } from "../icons/rune";
import { MacWindow } from "./MacWindow";
import { Waveform } from "./Talk";

// Illustrated windows for Zoya's real abilities (amazon.in shopping, Spotify, presentations) and her two
// safety habits (spoken confirm, password hand-off). Text names only: no logos, brand colours, prices,
// products or songs. Sized in em so one drawing serves the small hero prop and the larger feature row.

export type AppKind = "amazon" | "spotify" | "slides" | "confirm" | "password";

function Bar({ width, strong = false }: { width: string; strong?: boolean }) {
  return <span className={strong ? "bar bar-strong" : "bar"} style={{ width } as CSSProperties} />;
}

function CartGlyph() {
  return (
    <svg className="glyph cart-glyph" viewBox="0 0 24 24">
      <path d="M2.5 4h2.2l2.4 11h10.4l2.2-7.5H6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="9.5" cy="19" r="1.6" fill="currentColor" />
      <circle cx="16.5" cy="19" r="1.6" fill="currentColor" />
    </svg>
  );
}

function CartItems() {
  return (
    <>
      <div className="cart-item">
        <span className="product-thumb" />
        <span className="item-lines">
          <Bar width="82%" />
          <Bar width="46%" />
        </span>
      </div>
      <div className="cart-item">
        <span className="product-thumb product-thumb-2" />
        <span className="item-lines">
          <Bar width="70%" />
          <Bar width="38%" />
        </span>
      </div>
    </>
  );
}

function AmazonBody() {
  return (
    <div className="cart">
      <div className="cart-head">
        <CartGlyph />
        <Bar width="38%" strong />
      </div>
      <CartItems />
      <div className="cart-actions">
        <span className="fake-button">{APP_WINDOWS.amazon.placeOrder}</span>
        <span className="say-pill">{APP_WINDOWS.amazon.sayConfirm}</span>
      </div>
    </div>
  );
}

function SpotifyBody() {
  return (
    <div className="player">
      <span className="cover" />
      <span className="track-lines">
        <Bar width="80%" strong />
        <Bar width="52%" />
      </span>
      <span className="progress">
        <span className="progress-fill" />
      </span>
      <span className="player-foot">
        <Waveform active />
        <span className="player-controls">
          <svg className="glyph" viewBox="0 0 24 24">
            <rect x="5" y="6" width="2.2" height="12" rx="1" fill="currentColor" />
            <path d="M19 6.5v11L9.5 12z" fill="currentColor" />
          </svg>
          <svg className="glyph glyph-main" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="11" fill="currentColor" />
            <rect className="glyph-knockout" x="8.2" y="7.5" width="2.6" height="9" rx="1" />
            <rect className="glyph-knockout" x="13.2" y="7.5" width="2.6" height="9" rx="1" />
          </svg>
          <svg className="glyph" viewBox="0 0 24 24">
            <rect x="16.8" y="6" width="2.2" height="12" rx="1" fill="currentColor" />
            <path d="M5 6.5v11L14.5 12z" fill="currentColor" />
          </svg>
        </span>
      </span>
    </div>
  );
}

const THUMBS = 4;

function SlidesBody() {
  return (
    <div className="deck">
      <div className="slide-main">
        <span className="bar slide-title" style={{ width: "56%" }} />
        <Bar width="78%" />
        <Bar width="64%" />
        <Bar width="42%" />
        <span className="slide-chart">
          <i style={{ height: "45%" }} />
          <i style={{ height: "72%" }} />
          <i style={{ height: "100%" }} />
        </span>
      </div>
      <div className="slide-strip">
        {Array.from({ length: THUMBS }, (_, i) => (
          <span key={i} className={`thumb-slide${i === 0 ? " is-current" : ""}${i === THUMBS - 1 ? " is-drawing" : ""}`}>
            <i />
            <i />
            <i />
          </span>
        ))}
      </div>
    </div>
  );
}

// A macOS-style confirmation sheet over a faded cart, answered by voice.
function ConfirmBody() {
  return (
    <div className="sheet-scene">
      <div className="sheet-backdrop">
        <CartItems />
      </div>
      <div className="sheet">
        <Bar width="62%" strong />
        <Bar width="86%" />
        <Bar width="54%" />
        <div className="sheet-actions">
          <span className="sheet-button">{APP_WINDOWS.confirm.cancel}</span>
          <span className="sheet-voice">
            <GlassMicrophone className="sheet-mic" />
            <Waveform active />
          </span>
          <span className="sheet-button sheet-confirm">{APP_WINDOWS.confirm.confirm}</span>
        </div>
      </div>
    </div>
  );
}

const MASKED_DOTS = "••••••••";

// A sign-in window: Zoya waits while the person types their own password.
function PasswordBody() {
  return (
    <div className="signin">
      <GlassLock className="signin-lock" />
      <Bar width="44%" strong />
      <span className="signin-field">
        <Bar width="58%" />
      </span>
      <span className="signin-field">
        <span className="masked">{MASKED_DOTS}</span>
        <span className="caret" />
        <OutlineHand className="typing-hand" />
      </span>
      <span className="waiting-pill">
        <GlassPause className="waiting-glyph" />
        {APP_WINDOWS.password.waiting}
      </span>
    </div>
  );
}

function Body({ kind }: { kind: AppKind }) {
  switch (kind) {
    case "amazon":
      return <AmazonBody />;
    case "spotify":
      return <SpotifyBody />;
    case "slides":
      return <SlidesBody />;
    case "confirm":
      return <ConfirmBody />;
    case "password":
      return <PasswordBody />;
  }
}

export function AppWindow({ kind, className }: { kind: AppKind; className: string }) {
  return (
    <MacWindow title={APP_WINDOWS[kind].title} className={`app-window app-${kind} ${className}`}>
      <Body kind={kind} />
    </MacWindow>
  );
}
