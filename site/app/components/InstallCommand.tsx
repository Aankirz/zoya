"use client";

import { useRef, useState } from "react";
import { GET_ZOYA } from "../copy";
import { MacLights } from "./MacWindow";

const COPIED_RESET_MS = 2000;

// The MacWindow look, but readable: MacWindow is aria-hidden, and this command must reach screen readers.
export function InstallCommand() {
  const codeRef = useRef<HTMLElement>(null);
  const [status, setStatus] = useState("");

  function selectCommand() {
    const code = codeRef.current;
    const selection = window.getSelection();
    if (!code || !selection) return;
    const range = document.createRange();
    range.selectNodeContents(code);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(GET_ZOYA.command);
      setStatus(GET_ZOYA.copied);
      window.setTimeout(() => setStatus(""), COPIED_RESET_MS);
    } catch {
      // Clipboard blocked: select the text so ⌘C still works.
      selectCommand();
    }
  }

  return (
    <div className="mac-window install-window">
      <div className="mac-titlebar" aria-hidden="true">
        <MacLights />
        <span className="mac-title">{GET_ZOYA.windowTitle}</span>
      </div>
      <pre className="install-pre">
        <code ref={codeRef}>{GET_ZOYA.command}</code>
      </pre>
      <div className="install-actions">
        <button type="button" className="pill-glossy" aria-label={GET_ZOYA.copyLabel} onClick={copy}>
          {status || GET_ZOYA.copy}
        </button>
        <span className="sr-only" aria-live="polite">
          {status}
        </span>
      </div>
    </div>
  );
}
