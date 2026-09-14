import type { ReactNode } from "react";

export function MacLights() {
  return (
    <span className="mac-lights">
      <span />
      <span />
      <span />
    </span>
  );
}

// A drawn Mac window. Always decorative: its content is illustration, the page text carries the meaning.
export function MacWindow({ title, className, children }: { title: string; className: string; children: ReactNode }) {
  return (
    <div className={`mac-window ${className}`} aria-hidden="true">
      <div className="mac-titlebar">
        <MacLights />
        <span className="mac-title">{title}</span>
      </div>
      <div className="mac-body">{children}</div>
    </div>
  );
}
