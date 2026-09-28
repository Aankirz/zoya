// Run: npm test. Guards the launch copy rules (COPY_DECK_P5.md) so a later edit can't quietly break them.
import assert from "node:assert/strict";
import test from "node:test";
import * as copy from "../app/copy.ts";

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === "object") return Object.values(value).flatMap(strings);
  return [];
}

const all = strings(copy);

test("copy has no banned words and no em dashes", () => {
  for (const text of all) {
    assert.doesNotMatch(text, /ai-powered|seamless|revolutionary/i, text);
    assert.doesNotMatch(text, /—/, text);
  }
});

test("the hero and meta speak to everyone and lead with fn and shift", () => {
  for (const text of [copy.HERO.subline, copy.META.title, copy.META.description, copy.WHY.title]) {
    assert.doesNotMatch(text, /can't see the screen/, text);
  }
  assert.match(copy.HERO.subline, /hold fn and shift/);
});

test("how it works is hold, say it, let go, done", () => {
  assert.deepEqual(
    copy.HOW.steps.map((step) => step.title),
    ["hold fn and shift.", "say it.", "let go.", "done."],
  );
});

test("pricing is one $20 plan and the waitlist is the only call to action", () => {
  assert.match(copy.PRICING.title, /\$20 a month/);
  assert.equal(copy.MENU.cta, copy.WAITLIST.button);
  for (const text of all) assert.doesNotMatch(text, /checkout now|buy now|subscribe|git clone/i, text);
});
