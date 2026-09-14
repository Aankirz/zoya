import { MENU } from "../copy";
import { OutlineBattery, OutlineWifi } from "../icons/rune";
import { MenuClock } from "./MenuClock";

// Zoya's mark: two eyes and a sound-wave smile. It blinks and squishes like heyclicky's logo (CSS, stops for reduced motion).
export function ZoyaMark({ className }: { className?: string }) {
  return (
    <svg className={`zoya-mark ${className ?? ""}`} viewBox="0 0 40 26" aria-hidden="true" focusable="false">
      <g className="zoya-mark-eyes">
        <rect x="11" y="3" width="4" height="8" rx="2" />
        <rect x="25" y="3" width="4" height="8" rx="2" />
      </g>
      <path className="zoya-mark-smile" d="M6 15 C11 22 16 22 20 17 C24 22 29 22 34 15" />
    </svg>
  );
}

export function MenuBar({ joinHref }: { joinHref: string }) {
  return (
    <header className="menubar">
      <nav className="menubar-left" aria-label="page">
        <span className="menubar-brand" aria-hidden="true">
          {MENU.brand}
        </span>
        {MENU.links.map((link) => (
          <a key={link.href} className="menubar-link" href={link.href}>
            {link.label}
          </a>
        ))}
      </nav>
      <ZoyaMark className="menubar-mark" />
      <div className="menubar-right">
        <span className="menubar-status" aria-hidden="true">
          <OutlineWifi className="status-icon" />
          <OutlineBattery className="status-icon" />
          <MenuClock />
        </span>
        <a className="menubar-cta" href={joinHref}>
          {MENU.cta}
        </a>
      </div>
    </header>
  );
}
