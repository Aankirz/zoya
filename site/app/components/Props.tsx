import type { CSSProperties, ReactNode } from "react";

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

export function FolderIcon({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg className={`folder-icon ${className ?? ""}`} style={style} viewBox="0 0 64 50" focusable="false">
      <path fill="#4aa8e8" d="M4 8a4 4 0 0 1 4-4h15.5a4 4 0 0 1 2.8 1.2L31 10h25a4 4 0 0 1 4 4v28a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" />
      <path fill="#79c4f5" d="M4 17a3 3 0 0 1 3-3h50a3 3 0 0 1 3 3v25a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" />
      <path fill="#a9dcfb" d="M7 14h50a3 3 0 0 1 3 3v1.5H4V17a3 3 0 0 1 3-3z" />
    </svg>
  );
}

export function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={`trash-icon ${className ?? ""}`} viewBox="0 0 48 60" focusable="false">
      <rect x="17" y="1.5" width="14" height="6" rx="2" fill="none" stroke="#8d8d93" strokeWidth="2" />
      <rect x="3" y="7" width="42" height="7" rx="3.5" fill="#d9d9de" stroke="#8d8d93" strokeWidth="1.5" />
      <path d="M7 16h34l-3 38a5 5 0 0 1-5 4.5H15a5 5 0 0 1-5-4.5z" fill="#ececf0" stroke="#8d8d93" strokeWidth="1.5" />
      <path d="M17 22v30M24 22v30M31 22v30" stroke="#b4b4ba" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
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
      <span className="prop kaomoji p-kao-1">(^_^)</span>
      <span className="prop kaomoji p-kao-2">\(^o^)/</span>
    </div>
  );
}
