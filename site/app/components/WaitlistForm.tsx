"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { normalizeEmail } from "@/lib/validate";
import { WAITLIST } from "../copy";

type Status = "idle" | "sending" | "joined";

// Re-announce an identical error: the live region must change to be spoken again.
const REANNOUNCE_DELAY_MS = 60;

function errorFor(status: number): string {
  if (status === 400) return WAITLIST.errors.invalid;
  if (status === 429) return WAITLIST.errors.rateLimited;
  return WAITLIST.errors.network;
}

export function WaitlistForm({ idPrefix }: { idPrefix: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const successRef = useRef<HTMLParagraphElement>(null);
  const ids = { email: `${idPrefix}-email`, hint: `${idPrefix}-hint`, error: `${idPrefix}-error` };

  useEffect(() => {
    if (status === "joined") successRef.current?.focus();
  }, [status]);

  function announceError(message: string) {
    setError("");
    setTimeout(() => setError(message), REANNOUNCE_DELAY_MS);
    if (document.activeElement !== inputRef.current) inputRef.current?.focus();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "sending") return;
    const data = new FormData(event.currentTarget);
    const raw = String(data.get("email") ?? "").trim();
    if (!raw) return announceError(WAITLIST.errors.empty);
    const email = normalizeEmail(raw);
    if (!email) return announceError(WAITLIST.errors.invalid);

    setStatus("sending");
    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, website: data.get("website") }),
      });
      if (response.ok) return setStatus("joined");
      setStatus("idle");
      announceError(errorFor(response.status));
    } catch {
      setStatus("idle");
      announceError(WAITLIST.errors.network);
    }
  }

  if (status === "joined") {
    return (
      <p className="waitlist-success" ref={successRef} tabIndex={-1}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="28" height="28">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
        {WAITLIST.success}
      </p>
    );
  }

  return (
    <form className="waitlist" onSubmit={submit} noValidate>
      <label className="field-label" htmlFor={ids.email}>
        {WAITLIST.label}
      </label>
      <div className="field-row">
        <input
          ref={inputRef}
          className="field-input"
          id={ids.email}
          name="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${ids.error} ${ids.hint}` : ids.hint}
        />
        <button className="button-primary" type="submit" aria-disabled={status === "sending"}>
          {status === "sending" ? WAITLIST.sending : WAITLIST.button}
        </button>
      </div>
      {/* Honeypot: people never see or reach it; bots fill it in. */}
      <div className="honeypot" aria-hidden="true">
        <label htmlFor={`${idPrefix}-website`}>Website</label>
        <input id={`${idPrefix}-website`} name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>
      <p className="field-error" id={ids.error} role="alert">
        {error}
      </p>
      <p className="field-hint" id={ids.hint}>
        {WAITLIST.hint}
      </p>
    </form>
  );
}
