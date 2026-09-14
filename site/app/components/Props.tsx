import { GlassFolder, GlassTrash, PixelEar, PixelMessage } from "../icons/rune";
import { AppWindow } from "./AppWindows";

// Drawn "desktop" props in heyclicky's spirit. All decorative: the wrapper is aria-hidden.

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

// The three windows show Zoya's real abilities; folders, trash, sticker and a kaomoji support them.
export function HeroProps() {
  return (
    <div className="hero-props" aria-hidden="true">
      <AppWindow kind="amazon" className="prop p-amazon" />
      <AppWindow kind="spotify" className="prop p-spotify" />
      <AppWindow kind="slides" className="prop p-slides" />
      <HelloSticker className="p-sticker" />
      <FolderIcon className="prop p-folder-1" />
      <FolderIcon className="prop p-folder-3" />
      <TrashIcon className="prop p-trash" />
      <PixelEar className="prop pixel-accent p-pix-1" />
      <PixelMessage className="prop pixel-accent p-pix-2" />
      <span className="prop kaomoji p-kao-1">(^_^)</span>
    </div>
  );
}
