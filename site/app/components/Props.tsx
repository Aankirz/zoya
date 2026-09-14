import type { ReactNode } from "react";
import { GlassFileText, GlassFolder, GlassTrash, PixelEar, PixelMessage } from "../icons/rune";

// Drawn "desktop" props in heyclicky's spirit. All decorative: the wrapper is aria-hidden.

export function MacLights() {
  return (
    <span className="mac-lights">
      <span />
      <span />
      <span />
    </span>
  );
}

function MacWindow({ title, className, children }: { title: string; className: string; children: ReactNode }) {
  return (
    <div className={`mac-window prop ${className}`}>
      <div className="mac-titlebar">
        <MacLights />
        <span className="mac-title">{title}</span>
      </div>
      <div className="mac-body">{children}</div>
    </div>
  );
}

// Rune Icons glass style for the desktop props (BRIEF-v3 addendum).
export function FolderIcon({ className }: { className?: string }) {
  return <GlassFolder className={`folder-icon ${className ?? ""}`} />;
}

export function TrashIcon({ className }: { className?: string }) {
  return <GlassTrash className={`trash-icon ${className ?? ""}`} />;
}

function HelloSticker({ className }: { className: string }) {
  return (
    <div className={`sticker prop ${className}`}>
      <p className="sticker-hello">hello</p>
      <p className="sticker-small">my name is</p>
      <p className="sticker-name">zoya</p>
    </div>
  );
}

function NotesWindow() {
  return (
    <MacWindow title="notes" className="p-notes">
      <GlassFileText className="note-glyph" />
      <span className="note-line" style={{ width: "88%" }} />
      <span className="note-line" style={{ width: "72%" }} />
      <span className="note-line note-highlight" style={{ width: "64%" }} />
      <span className="note-line" style={{ width: "80%" }} />
      <span className="note-line" style={{ width: "46%" }} />
    </MacWindow>
  );
}

function FinderWindow() {
  return (
    <MacWindow title="zoya" className="p-finder">
      <span className="finder-grid">
        {["music", "notes", "photos", "slides", "mail", "notes 2"].map((label) => (
          <span className="finder-item" key={label}>
            <FolderIcon />
            <span className="finder-label">{label}</span>
          </span>
        ))}
      </span>
    </MacWindow>
  );
}

export function HeroProps() {
  return (
    <div className="hero-props" aria-hidden="true">
      <NotesWindow />
      <FinderWindow />
      <HelloSticker className="p-sticker" />
      <FolderIcon className="prop p-folder-1" />
      <FolderIcon className="prop p-folder-2" />
      <FolderIcon className="prop p-folder-3" />
      <TrashIcon className="prop p-trash" />
      <PixelEar className="prop pixel-accent p-pix-1" />
      <PixelMessage className="prop pixel-accent p-pix-2" />
      <span className="prop kaomoji p-kao-1">(^_^)</span>
      <span className="prop kaomoji p-kao-2">\(^o^)/</span>
    </div>
  );
}
