import { MENU } from "../copy";
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

function WifiIcon() {
  return (
    <svg viewBox="0 0 20 16" width="17" height="14">
      <path d="M1.5 5.5a12 12 0 0 1 17 0M4.5 8.5a7.5 7.5 0 0 1 11 0M7.5 11.5a3 3 0 0 1 5 0" />
      <circle cx="10" cy="14" r="1.2" />
    </svg>
  );
}

function BatteryIcon() {
  return (
    <svg viewBox="0 0 28 14" width="25" height="13">
      <rect x="1" y="1.5" width="22" height="11" rx="3" />
      <rect className="battery-level" x="3" y="3.5" width="14" height="7" rx="1.5" />
      <path d="M25.5 5.5v3" />
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
          <WifiIcon />
          <BatteryIcon />
          <MenuClock />
        </span>
        <a className="menubar-cta" href={joinHref}>
          {MENU.cta}
        </a>
      </div>
    </header>
  );
}
