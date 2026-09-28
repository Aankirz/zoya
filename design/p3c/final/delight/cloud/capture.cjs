// Captures the Hub on a fixture bridge: every page in every state, light and dark, plus videos.
//   NODE_PATH=$(npm root -g) node design/p3c/final/delight/cloud/capture.cjs <hub dir> <out dir> [shots|video|flash|all]

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const HUB = path.resolve(process.argv[2] || "zoya/hub");
const OUT = path.resolve(process.argv[3] || "design/p3c/final/delight/cloud/after");
const MODE = process.argv[4] || "all";
const ORIGIN = "http://hub.test";
const NOW = new Date("2026-09-28T22:10:00+05:30");
const ZONE = "Asia/Kolkata";
const SIZE = { width: 1280, height: 800 };
const PAGES = ["today", "history", "memory", "setup", "voice", "plan"];
const THEMES = ["light", "dark"];
const REPLY_MS = 40;
const LOADING_AT_MS = 900;
const ERROR_AT_MS = { plan: 16000, other: 9000 };
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png" };

function stamp(daysAgo, clock) {
  const [h, m] = clock.split(":").map(Number);
  const day = new Date(NOW.getTime() - daysAgo * 86400000);
  const local = new Date(day.toLocaleString("en-US", { timeZone: ZONE }));
  const pad = (n) => String(n).padStart(2, "0");
  return `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(h)}:${pad(m)}:00+05:30`;
}

function hex(n) {
  return (n.toString(16) + "0".repeat(32)).slice(0, 32);
}

const ENTRIES = [
  { at: stamp(0, "21:41"), heard: "play kesariya on spotify", said: "Playing Kesariya by Arijit Singh.", times: 1, app: "Spotify", outcome: "Played music" },
  { at: stamp(0, "20:12"), heard: "open notes", said: "", times: 1, app: "Notes", outcome: "Opened Notes" },
  { at: stamp(0, "19:30"), heard: "search amazon for wireless mice", said: "Five mice. The cheapest is ₹549.", times: 1, app: "Safari", outcome: "Searched Amazon" },
  { at: stamp(0, "18:02"), heard: "buy the boat earphones", said: "", times: 1, app: "Safari", confirm: { action: "place order", amount: "₹1,249", recipient_or_item: "amazon.in", decision: "stop" }, outcome: "Cancelled · you said stop" },
  { at: stamp(0, "16:18"), heard: "remember i like masala chai", said: "", times: 1, outcome: "Remembered" },
  { at: stamp(1, "10:05"), heard: "open safari", said: "", times: 1, app: "Safari", outcome: "Opened Safari" },
  { at: stamp(1, "09:40"), heard: "order the usb-c cable", said: "", times: 1, app: "Safari", confirm: { action: "place order", amount: "₹399", recipient_or_item: "amazon.in", decision: "confirmed" }, outcome: "Ordered · ₹399 · you said confirm" },
  { at: stamp(1, "09:12"), heard: "play lo-fi on youtube", said: "", times: 1, app: "Safari", failed: true, why: "YouTube didn't load, so I stopped." },
  { at: stamp(2, "22:30"), heard: "set a reminder to call mom at six", said: "", times: 1, app: "Reminders", outcome: "Set a reminder" },
];

const MEMORIES = [
  "Your gym is Cult on 12th Main.",
  "You prefer window seats on flights.",
  "Your sister's name is Priya.",
  "You like masala chai, not coffee.",
].map((content, i) => ({ id: hex(0xa1 + i), at: stamp(3, "12:00"), content }));

const SETUP = { permissions: { microphone: false, accessibility: true, screen: true, automation: true }, license: false, version: "0.0.1", hotkey: "fn-shift" };
const SETTINGS = { largerText: false, easierLetters: false, pillPosition: "bottom", launchAtLogin: false, hotkey: "fn-shift" };
const PLAN = { month: "2026-09", usedCents: 1240, capCents: 2000 };

function full() {
  return {
    today: { entries: ENTRIES.filter((e) => e.at.startsWith(stamp(0, "00:00").slice(0, 10))), setup: SETUP, name: "Alex", state: "idle" },
    history: { entries: ENTRIES },
    memory: { items: MEMORIES },
    plan: { plan: null },
    setup: SETUP,
    voice: SETTINGS,
  };
}

function empty() {
  const allOn = { ...SETUP, permissions: { microphone: true, accessibility: true, screen: true, automation: true }, license: true };
  return {
    today: { entries: [], setup: allOn, name: "Alex", state: "idle" },
    history: { entries: [] },
    memory: { items: [] },
    plan: { plan: null },
    setup: allOn,
    voice: SETTINGS,
  };
}

const LONG_APP = "Microsoft Remote Desktop Beta";
const LONG_MEMORY =
  "Your mother's birthday is on the fourteenth of March, she likes white lilies more than roses, prefers a phone call in the morning before nine, and has asked that nobody books a restaurant with loud music; the one she liked most was the quiet place near Lalbagh with the courtyard and the old banyan tree.";

function long() {
  const verbs = [
    ["play kesariya on spotify", "Spotify", "Played music", "Playing Kesariya by Arijit Singh."],
    [`open ${LONG_APP.toLowerCase()}`, LONG_APP, `Opened ${LONG_APP}`, ""],
    ["search amazon for a standing desk under twenty thousand rupees with a memory preset", "Safari", "Searched Amazon", "Twelve desks. The cheapest with presets is ₹18,990, from a seller in Pune with four and a half stars."],
    ["set a reminder to call the plumber about the kitchen tap tomorrow morning", "Reminders", "Set a reminder", ""],
    ["remember my passport expires in june", undefined, "Remembered", ""],
    ["play lo-fi on youtube", "Safari", null, ""],
  ];
  const entries = [];
  for (let i = 0; i < 200; i++) {
    const [heard, app, outcome, said] = verbs[i % verbs.length];
    const minutes = 23 * 60 - (i % 8) * 67;
    const clock = `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
    const entry = { at: stamp(Math.floor(i / 8), clock), heard, said, times: i % 11 === 3 ? 4 : 1 };
    if (app) entry.app = app;
    if (outcome === null) Object.assign(entry, { failed: true, why: "YouTube didn't load, so I stopped." });
    else entry.outcome = outcome;
    entries.push(entry);
  }
  const items = [{ id: hex(0xf00), at: stamp(0, "09:00"), content: LONG_MEMORY }];
  for (let i = 0; i < 59; i++) items.push({ id: hex(0x100 + i), at: stamp(1 + i * 2, "12:00"), content: `${MEMORIES[i % 4].content.replace(/\.$/, "")}, note ${i + 1}.` });
  const setup = { ...SETUP, permissions: { microphone: false, accessibility: false, screen: true, automation: false }, version: "0.0.1-beta.20260928+build.4471" };
  return {
    today: { entries: entries.filter((e) => e.at.startsWith(stamp(0, "00:00").slice(0, 10))), setup, name: "Maximiliana-Alexandrina", state: "acting" },
    history: { entries },
    memory: { items },
    plan: { plan: { month: "2026-09", usedCents: 1920, capCents: 2000 } },
    setup,
    voice: { ...SETTINGS, largerText: true, pillPosition: "notch" },
  };
}

const SCENARIOS = { full, empty, long };

function scenario(state, page) {
  if (state === "loading" || state === "error") return { data: full(), hang: [page], delay: REPLY_MS };
  return { data: SCENARIOS[state](), hang: [], delay: REPLY_MS };
}

function stub(sc) {
  window.__asks = [];
  window.__scenario = sc;
  const reply = (cmd, args) => {
    const data = window.__scenario.data;
    if (cmd === "getPage") return data[args.page];
    if (cmd === "setSetting") return { ...data.voice, [args.key]: args.value };
    if (cmd === "prepareClearHistory") return { token: "0".repeat(32), count: data.history.entries.length };
    if (cmd === "clearHistory") return { cleared: data.history.entries.length };
    return true;
  };
  window.webkit = {
    messageHandlers: {
      zoya: {
        postMessage(body) {
          const { cmd, id, args } = JSON.parse(body);
          window.__asks.push(cmd === "getPage" ? `getPage:${args.page}` : cmd);
          if (cmd === "getPage" && window.__scenario.hang.includes(args.page)) return;
          const result = reply(cmd, args);
          setTimeout(() => window.zoyaReceive({ id, result }), window.__scenario.delay);
        },
      },
    },
  };
}

async function serve(context) {
  await context.route(`${ORIGIN}/**`, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/appicon/")) return route.fulfill({ status: 404, body: "" });
    const file = path.join(HUB, decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html");
    if (!file.startsWith(HUB) || !fs.existsSync(file) || !TYPES[path.extname(file)]) return route.fulfill({ status: 404, body: "" });
    return route.fulfill({ status: 200, body: fs.readFileSync(file), contentType: TYPES[path.extname(file)] });
  });
}

async function open(browser, theme, sc, extra = {}) {
  const context = await browser.newContext({ viewport: SIZE, colorScheme: theme, timezoneId: ZONE, locale: "en-US", ...extra });
  await serve(context);
  const page = await context.newPage();
  await page.clock.setFixedTime(NOW);
  await page.addInitScript(stub, sc);
  return { context, page };
}

async function shots(browser) {
  const jobs = [];
  for (const theme of THEMES)
    for (const name of PAGES)
      for (const state of ["full", "empty", "loading", "error", "long"]) jobs.push({ theme, name, state });
  const run = async ({ theme, name, state }) => {
    const { context, page } = await open(browser, theme, scenario(state, name));
    await page.goto(`${ORIGIN}/index.html#${name}`);
    await page.evaluate(() => document.fonts.ready);
    const wait = state === "loading" ? LOADING_AT_MS : state === "error" ? ERROR_AT_MS[name] || ERROR_AT_MS.other : 1200;
    await page.waitForTimeout(wait);
    const file = path.join(OUT, `${name}-${state}-${theme}.png`);
    await page.screenshot({ path: file, fullPage: state === "long" && name !== "today" });
    await context.close();
    return file;
  };
  fs.mkdirSync(OUT, { recursive: true });
  for (let i = 0; i < jobs.length; i += 8) await Promise.all(jobs.slice(i, i + 8).map(run));
  console.log(`shots: ${jobs.length} in ${OUT}`);
}

function frameProbe() {
  window.__frames = [];
  const tick = () => {
    const column = document.getElementById("column");
    const parts = column ? [...column.children].slice(0, 4) : [];
    window.__frames.push({
      t: Math.round(performance.now()),
      hash: location.hash,
      bg: getComputedStyle(document.body).backgroundColor,
      card: document.querySelector(".card") ? getComputedStyle(document.querySelector(".card")).backgroundColor : "",
      parts: parts.map((p) => `${p.tagName}.${p.className}:${Math.round(p.offsetTop)}:${getComputedStyle(p).opacity}`).join("|"),
      toast: document.querySelector(".toast") ? getComputedStyle(document.querySelector(".toast")).opacity : "-",
    });
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function video(browser) {
  const dir = path.join(OUT, "video");
  fs.mkdirSync(dir, { recursive: true });
  const record = async (name, theme, body, extra = {}) => {
    const { context, page } = await open(browser, theme, scenario("full"), { recordVideo: { dir, size: SIZE }, ...extra });
    await page.addInitScript(frameProbe);
    await page.goto(`${ORIGIN}/index.html#today`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(900);
    await body(page);
    const frames = await page.evaluate(() => window.__frames);
    const saved = await page.video().path();
    await context.close();
    fs.renameSync(saved, path.join(dir, `${name}-${theme}.webm`));
    fs.writeFileSync(path.join(dir, `${name}-${theme}.frames.json`), JSON.stringify(frames, null, 0));
  };
  const deleteUndo = async (page) => {
    await page.evaluate(() => (location.hash = "memory"));
    await page.waitForTimeout(500);
    const row = page.locator(".rows .row").nth(1);
    await row.hover();
    await page.waitForTimeout(250);
    await row.locator("button").click();
    await page.waitForTimeout(1200);
    await page.locator(".toast button").click();
    await page.waitForTimeout(1000);
  };
  await record("memory-delete-undo-reduced", "light", deleteUndo, { reducedMotion: "reduce" });
  await record("theme-switch", "light", async (page) => {
    for (const scheme of ["dark", "light", "dark"]) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.waitForTimeout(600);
    }
  });
  for (const theme of THEMES) {
    await record("page-switch", theme, async (page) => {
      for (const name of ["history", "memory", "setup", "voice", "plan", "today"]) {
        await page.evaluate((n) => (location.hash = n), name);
        await page.waitForTimeout(500);
      }
    });
    await record("memory-delete-undo", theme, deleteUndo);
  }
  console.log(`video: ${dir}`);
}

async function flash(browser) {
  const results = [];
  for (const start of THEMES) {
    const other = start === "light" ? "dark" : "light";
    const { context, page } = await open(browser, start, scenario("full"));
    await page.addInitScript(frameProbe);
    await page.goto(`${ORIGIN}/index.html#today`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(800);
    await page.evaluate(() => (window.__frames.length = 0));
    await page.emulateMedia({ colorScheme: other });
    await page.waitForTimeout(400);
    const frames = await page.evaluate(() => window.__frames);
    const bgs = [...new Set(frames.map((f) => `${f.bg} / ${f.card}`))];
    results.push({ switch: `${start}->${other}`, frames: frames.length, distinct: bgs });
    await context.close();
  }
  const load = [];
  for (const [theme, state] of [["light", "full"], ["dark", "full"], ["light", "long"]]) {
    const { context, page } = await open(browser, theme, scenario(state));
    await page.addInitScript(frameProbe);
    await page.goto(`${ORIGIN}/index.html#today`);
    await page.waitForTimeout(1500);
    const frames = await page.evaluate(() => window.__frames);
    const tops = [...new Set(frames.map((f) => f.parts.split("|").map((p) => p.split(":")[1]).join(",")))];
    load.push({ theme, state, firstBg: frames[0]?.bg, layouts: tops });
    await context.close();
  }
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, "flash.json"), JSON.stringify({ themeSwitch: results, load }, null, 2));
  console.log(JSON.stringify({ themeSwitch: results, load }, null, 2));
}

(async () => {
  const browser = await chromium.launch();
  if (MODE === "shots" || MODE === "all") await shots(browser);
  if (MODE === "video" || MODE === "all") await video(browser);
  if (MODE === "flash" || MODE === "all") await flash(browser);
  await browser.close();
})();
