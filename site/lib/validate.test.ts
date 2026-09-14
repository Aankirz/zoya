// Run: npm test (node's built-in runner, no extra dependencies).
import assert from "node:assert/strict";
import test from "node:test";
import { isRateLimited } from "./rate-limit.ts";
import { isVisitorId, normalizeEmail } from "./validate.ts";

test("normalizeEmail trims and lowercases a valid address", () => {
  assert.equal(normalizeEmail("  Priya@Example.COM "), "priya@example.com");
});

test("normalizeEmail rejects malformed, oversized and non-string input", () => {
  for (const bad of ["", "priya", "priya@", "@example.com", "priya@example", "a b@c.io", 42, null]) {
    assert.equal(normalizeEmail(bad), null, String(bad));
  }
  assert.equal(normalizeEmail(`${"a".repeat(250)}@x.io`), null);
});

test("isVisitorId accepts only v4 UUIDs", () => {
  assert.equal(isVisitorId("3f2b8c4e-9a1d-4e6f-8b2a-1c3d5e7f9a0b"), true);
  assert.equal(isVisitorId("not-a-uuid"), false);
  assert.equal(isVisitorId("'; drop table visitors; --"), false);
});

test("isRateLimited blocks after the limit and frees up after the window", () => {
  const start = 1_000_000;
  assert.equal(isRateLimited("ip", 2, start), false);
  assert.equal(isRateLimited("ip", 2, start + 1), false);
  assert.equal(isRateLimited("ip", 2, start + 2), true);
  assert.equal(isRateLimited("ip", 2, start + 11 * 60 * 1000), false);
});
