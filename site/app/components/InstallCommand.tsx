"use client";

import { useRef, useState } from "react";
import { GET_ZOYA } from "../copy";
import { MacLights } from "./MacWindow";

const COPIED_RESET_MS = 2000;

// The MacWindow look, but readable: MacWindow is aria-hidden, and this command must reach screen readers.
export function InstallCommand() {
  const codeRef = useRef<HTMLElement>(null);
  const [status, setStatus] = useState("");
  const splitAt = GET_ZOYA.command.indexOf(GET_ZOYA.commandBreakAfter) + GET_ZOYA.commandBreakAfter.length;
  const head = GET_ZOYA.command.slice(0, splitAt);
  const tail = GET_ZOYA.command.slice(splitAt);

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
      <div className="mac-titlebar">
        <span aria-hidden="true">
          <MacLights />
        </span>
        <span className="mac-title" aria-hidden="true">
          {GET_ZOYA.windowTitle}
        </span>
        <button type="button" className="say-pill copy-pill" aria-label={GET_ZOYA.copyLabel} onClick={copy}>
          {status || GET_ZOYA.copy}
        </button>
        <span className="sr-only" aria-live="polite">
          {status}
        </span>
      </div>
      <pre className="install-pre">
        <code ref={codeRef}>
          {head}
          <wbr />
          {tail}
        </code>
      </pre>
    </div>
  );
}
