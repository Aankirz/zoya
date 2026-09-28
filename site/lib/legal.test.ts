// Run: npm test. The legal pages render, every page's footer links to them, and no placeholder ships unlisted.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SiteFooter } from "../app/components/SiteFooter.tsx";
import * as copy from "../app/copy.ts";
import { LEGAL_COMMON, LEGAL_DOCS, OWNER_NEEDED, PLACEHOLDER_PATTERN, type LegalDoc } from "../app/legal.ts";

const DRAFT_BANNER = "// DRAFT FOR LEGAL REVIEW.";
const APP_DIR = new URL("../app/", import.meta.url);

type PageModule = { default: () => ReactElement | Promise<ReactElement>; metadata?: unknown };

const pageFile = (doc: LegalDoc) => new URL(`.${doc.path}/page.tsx`, APP_DIR);

async function render(file: URL): Promise<string> {
  const page = (await import(file.href)) as PageModule;
  return renderToStaticMarkup(await page.default()) + JSON.stringify(page.metadata ?? {});
}

function hrefs(html: string): string[] {
  return [...html.matchAll(/href="([^"]*)"/g)].map((match) => match[1]);
}

function footerOf(html: string): string {
  return html.split("<footer")[1] ?? "";
}

function placeholders(text: string): string[] {
  return [...new Set(text.match(PLACEHOLDER_PATTERN) ?? [])];
}

for (const doc of LEGAL_DOCS) {
  test(`${doc.path} renders its title, every section and the draft notice`, async () => {
    const html = await render(pageFile(doc));
    assert.match(html, new RegExp(`<h1[^>]*>${doc.title}</h1>`));
    for (const section of doc.sections) assert.ok(html.includes(`>${section.heading}</h2>`), section.heading);
    assert.ok(html.includes(LEGAL_COMMON.draft));
  });

  test(`${doc.path} carries the draft-for-legal-review banner in its source`, () => {
    assert.ok(readFileSync(pageFile(doc), "utf8").startsWith(DRAFT_BANNER));
  });
}

test("headings on the legal pages are lowercase", () => {
  for (const doc of LEGAL_DOCS) {
    for (const heading of [doc.title, ...doc.sections.map((section) => section.heading)]) {
      assert.equal(heading, heading.toLowerCase(), heading);
    }
  }
});

test("every legal page's footer links to terms, privacy and refunds", async () => {
  for (const page of LEGAL_DOCS) {
    const footer = footerOf(await render(pageFile(page)));
    for (const doc of LEGAL_DOCS) assert.ok(hrefs(footer).includes(doc.path), `${page.path} → ${doc.path}`);
  }
});

// The home page's next/image is CommonJS the test loader can't interop, so it is checked through the footer it mounts.
test("the home page mounts the shared footer, and that footer links to terms, privacy and refunds", () => {
  assert.match(readFileSync(new URL("page.tsx", APP_DIR), "utf8"), /<SiteFooter visitorCount=\{visitorCount\} \/>/);
  const footer = footerOf(renderToStaticMarkup(createElement(SiteFooter, { visitorCount: null })));
  for (const doc of LEGAL_DOCS) assert.ok(hrefs(footer).includes(doc.path), doc.path);
});

test("every placeholder on the site is listed in OWNER_NEEDED, and every listed one is still used", async () => {
  const shipped = new Set(placeholders(JSON.stringify(copy)));
  for (const doc of LEGAL_DOCS) for (const found of placeholders(await render(pageFile(doc)))) shipped.add(found);
  const listed = Object.keys(OWNER_NEEDED);
  for (const found of shipped) assert.ok(listed.includes(found), `unlisted placeholder ${found}`);
  for (const owed of listed) assert.ok(shipped.has(owed), `${owed} is listed but no page uses it`);
});

test("legal copy has no em dashes", () => {
  const text = JSON.stringify([LEGAL_DOCS, LEGAL_COMMON]);
  assert.doesNotMatch(text, /—/);
});
