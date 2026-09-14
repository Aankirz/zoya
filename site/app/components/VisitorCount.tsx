"use client";

import { useEffect, useState } from "react";
import { OutlineEye } from "../icons/rune";

const VISITOR_ID_KEY = "zoya-visitor-id";
const numberFormat = new Intl.NumberFormat("en");

function readStoredId(): string | null | undefined {
  try {
    return localStorage.getItem(VISITOR_ID_KEY);
  } catch {
    return undefined; // storage blocked: show the server count, don't register
  }
}

async function registerVisitor(): Promise<number | null> {
  const id = crypto.randomUUID();
  const response = await fetch("/api/visit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (!response.ok) return null;
  localStorage.setItem(VISITOR_ID_KEY, id);
  const { count } = (await response.json()) as { count: unknown };
  return typeof count === "number" ? count : null;
}

// Real unique visitors only. Hidden when there is no database (local dev). Not a live region on purpose.
export function VisitorCount({ initial }: { initial: number | null }) {
  const [count, setCount] = useState(initial);

  useEffect(() => {
    if (initial === null || readStoredId() !== null) return;
    registerVisitor()
      .then((latest) => latest !== null && setCount(latest))
      .catch(() => {}); // ponytail: a failed registration just leaves the server-rendered count
  }, [initial]);

  if (count === null) return null;

  return (
    <p className="visitors">
      <OutlineEye className="visitors-eye" />
      {numberFormat.format(count)} {count === 1 ? "person has" : "people have"} visited
    </p>
  );
}
