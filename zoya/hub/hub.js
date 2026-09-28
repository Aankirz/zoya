const HOTKEYS = {
  "fn-shift": { caps: ["fn", "⇧"], names: "fn and Shift" },
  "control-option": { caps: ["⌃", "⌥"], names: "Control and Option" },
};
let currentHotkey = "fn-shift";
const hotkey = () => HOTKEYS[currentHotkey] || HOTKEYS["fn-shift"];

const COPY = {
  morning: "good morning",
  afternoon: "good afternoon",
  evening: "good evening",
  today: "today",
  yesterday: "yesterday",
  doneToday: (n) => (n === 0 ? "nothing done yet today." : n === 1 ? "1 thing done today." : `${n} things done today.`),
  needsCount: (n) => (n === 0 ? "" : n === 1 ? " one needs you." : ` ${n} need you.`),
  states: {
    idle: "ready",
    listening: "listening",
    thinking: "thinking",
    acting: "working",
    speaking: "speaking",
    waiting: "waiting for you",
    stopped: "stopped",
    error: "couldn’t finish",
  },
  liveLabel: (word) => `zoya is ${word}`,
  needsTitle: "needs you",
  permissionOff: {
    microphone: "your microphone is off.",
    accessibility: "accessibility is off.",
    screen: "screen recording is off.",
    automation: "automation is off.",
  },
  permissionWhy: {
    microphone: "i can’t hear “hey zoya” until it’s on.",
    accessibility: "i can’t feel your keys or press a button for you until it’s on.",
    screen: "i can’t read your screen until it’s on.",
    automation: "i can’t work inside your apps until it’s on.",
  },
  allowanceLow: "your allowance is almost used.",
  allowanceWhy: (left) => `${left} left this month.`,
  turnOn: "turn it on",
  openPlan: "see plan",
  doneTitle: "done today",
  get doneEmpty() {
    return `nothing yet. hold ${hotkey().caps.join(" ")} and ask me anything.`;
  },
  get ways() {
    return [
      { keys: hotkey().caps, names: hotkey().names, title: "hold and talk", hint: "let go, and i act." },
      { bubble: "hey zoya", title: "just say it", hint: "hands free, eyes free." },
      { keys: ["⌘", "K"], names: "Command K", title: "or type it", hint: "right here." },
    ];
  },
  replied: "answered you",
  failed: "couldn’t finish",
  couldnt: (heard) => `couldn’t ${heard}`,
  timesLabel: (n) => `asked ${n} times`,
  historyTitle: "history",
  historyCapsule: "on this mac",
  historySub: (n) => (n === 0 ? "what you ask stays on this mac." : `${n} ${n === 1 ? "request" : "requests"}. they stay on this mac.`),
  historyEmpty: "nothing here yet. ask me something, and it shows up here.",
  historySay: "hey zoya, open notes",
  heard: "heard",
  did: "did",
  said: "said",
  asked: "asked",
  outcome: "outcome",
  why: "why",
  clearHistory: "clear history",
  clearAsk: (n) => `clear all ${n} ${n === 1 ? "request" : "requests"}? this can’t be undone.`,
  clearNothing: "there’s nothing to clear.",
  cancel: "cancel",
  cleared: "history is cleared.",
  clearRefused: "i couldn’t clear it. try again.",
  memoryTitle: "memory",
  memoryCapsule: "only yours",
  memorySub: (n) => (n === 0 ? "i keep what you ask me to." : n === 1 ? "one thing i remember about you." : `${n} things i remember about you.`),
  memoryEmpty: "nothing yet. tell me something to remember.",
  memorySay: "remember that i’m vegetarian",
  thisMonth: "this month",
  earlier: "earlier",
  delete: "delete",
  deleted: (fact) => `deleted “${fact}”`,
  undo: "undo",
  deleteFailed: "i couldn’t delete that. try again in a moment.",
  planTitle: "plan",
  planCapsule: "this month",
  planSub: (month) => `your allowance for ${month}.`,
  planCard: "usage",
  planUsed: "used",
  planAllowance: "allowance",
  planLeft: "left",
  planMissing: "your plan isn’t here right now. with your own keys, there’s nothing to track.",
  setupTitle: "setup",
  setupCapsule: "what i need",
  setupSub: (on, all) => (on === all ? "everything is on." : `${on} of ${all} on.`),
  permissionsCard: "permissions",
  permissions: { microphone: "microphone", accessibility: "accessibility", screen: "screen recording", automation: "automation" },
  permissionUse: {
    microphone: "to hear you",
    accessibility: "for your keys and pressing buttons",
    screen: "to read the screen",
    automation: "to work inside your apps",
  },
  on: "on",
  off: "off",
  macCard: "this mac",
  keyLabel: "zoya key",
  keySaved: "saved",
  keyNone: "your own keys",
  versionLabel: "version",
  updates: "check for updates",
  checking: "checking. if there’s a new version, i’ll ask you out loud.",
  helpLabel: "help",
  report: "send a problem report",
  reportSent: "making the report now. i’ll tell you when it’s on your desktop.",
  get retro() {
    return ["your mac, by voice.", `hold ${hotkey().caps.join(" ")},`, "and just talk.", "© 2026 zoya"];
  },
  voiceTitle: "voice & keys",
  get voiceCapsule() {
    return `${hotkey().caps.join(" ")} to talk`;
  },
  voiceSub: "how you reach me, and how i look.",
  keysCard: "keys",
  holdToTalk: "hold to talk",
  holdHint: "hold both, talk, let go.",
  pillCard: "the pill",
  pillPosition: "where i sit",
  positions: { bottom: "bottom", notch: "notch", left: "left", right: "right" },
  hotkeys: { "fn-shift": "fn ⇧", "control-option": "⌃ ⌥" },
  readingCard: "reading",
  largerText: "larger captions and text",
  easierLetters: "easier-to-read letters",
  startCard: "start",
  launchAtLogin: "open zoya when you log in",
  sent: (text) => `asked: “${text}”. watch the pill.`,
  tryAgain: "try again",
  loadFailed: {
    today: "i couldn’t load today just now. nothing is lost.",
    history: "i couldn’t read your history just now. it’s still on this mac.",
    memory: "i couldn’t read my memory just now. nothing was forgotten.",
    setup: "i couldn’t check your permissions just now.",
    voice: "i couldn’t load your settings just now. they haven’t changed.",
    plan: "i couldn’t reach your plan just now. check your connection.",
  },
};

const SPECIFIC = [
  { outcomes: ["Played music", "Played a video"], pattern: /^(?:play|put on)\s+(.+?)(?:\s+on\s+(?:spotify|youtube))?[.!?]?$/i, say: (thing) => `played ${thing}` },
  { outcomes: ["Searched Amazon"], pattern: /^search\s+amazon\s+for\s+(.+?)[.!?]?$/i, say: (thing) => `searched amazon for ${thing}` },
  { outcomes: ["Searched the web"], pattern: /^(?:search(?:\s+the\s+web)?\s+for|google|look\s+up)\s+(.+?)[.!?]?$/i, say: (thing) => `searched for ${thing}` },
  { outcomes: ["Set a reminder"], pattern: /^(?:set\s+a\s+reminder|remind\s+me)\s+to\s+(.+?)[.!?]?$/i, say: (thing) => `set a reminder to ${thing}` },
  { outcomes: ["Remembered"], pattern: /^remember(?:\s+that)?\s+(.+?)[.!?]?$/i, say: (thing) => `remembered ${yours(thing)}` },
  { outcomes: ["Ordered"], pattern: /^(order|buy)\s+(.+?)[.!?]?$/i, say: (verb, thing) => `${verb.toLowerCase() === "buy" ? "bought" : "ordered"} ${thing}` },
  { outcomes: ["Cancelled"], pattern: /^(order|buy)\s+(.+?)[.!?]?$/i, say: (verb, thing) => `didn’t ${verb.toLowerCase()} ${thing}` },
];
const DOING = /^(?:play|open|search|set|order|buy|remember|send|share|write|find|remind)\b/i;
const DOING_MAX = 60;
const YOURS = { i: "you", "i’m": "you’re", "i'm": "you’re", my: "your", me: "you", mine: "yours", am: "are" };

function yours(text) {
  return text.replace(/(?<![\w’'])(i’m|i'm|i|my|me|mine|am)(?![\w’'])/gi, (word) => YOURS[word.toLowerCase()]);
}

const UNDO_MS = 8000;
const UNDO_GRACE_MS = 3000;
const ALLOWANCE_WARN = 0.9;
const TODAY_ROWS = 6;
const SKELETON_AFTER_MS = 150;
const PAGE_WAIT_MS = 8000;
const PLAN_WAIT_MS = 15000;
const PLAN_BUDGET_MS = 400;
const LATE = Symbol("late");
const pending = new Map();
let nextId = 1;
let arrived = false;
let turn = 0;
let knownPlan = null;

window.zoyaReceive = ({ id, result }) => {
  const resolve = pending.get(id);
  pending.delete(id);
  if (resolve) resolve(result);
};

function ask(cmd, args = {}, wait = 0) {
  const id = nextId++;
  return new Promise((resolve) => {
    pending.set(id, resolve);
    if (wait) setTimeout(() => pending.delete(id) && resolve(LATE), wait);
    window.webkit.messageHandlers.zoya.postMessage(JSON.stringify({ cmd, id, args }));
  });
}

function node(tag, text, attrs = {}) {
  const made = document.createElement(tag);
  if (text !== undefined) made.textContent = text;
  for (const [key, value] of Object.entries(attrs)) made.setAttribute(key, value);
  return made;
}

function icon(name) {
  return node("span", undefined, { class: "icon", "data-icon": name, "aria-hidden": "true" });
}

function button(label, onClick, kind = "button") {
  const made = node("button", label, { type: "button", class: kind });
  made.addEventListener("click", onClick);
  return made;
}

function lowerFirst(text) {
  return text ? text[0].toLowerCase() + text.slice(1) : text;
}

function eyes() {
  const pair = node("span", undefined, { class: "eyes", "aria-hidden": "true" });
  pair.append(node("b"), node("b"));
  return pair;
}

function appIcon(entry) {
  if (!entry.app) {
    const face = node("span", undefined, { class: "app is-zoya", "aria-hidden": "true" });
    face.append(eyes());
    return face;
  }
  const picture = node("img", undefined, { class: "app", src: `appicon/${encodeURIComponent(entry.app)}`, alt: "", width: "26", height: "26" });
  const letter = () => picture.replaceWith(node("span", entry.app[0], { class: "app is-letter", "aria-hidden": "true" }));
  picture.addEventListener("error", letter, { once: true });
  return picture;
}

function after(part) {
  return Promise.all(part.getAnimations().map((motion) => motion.finished.catch(() => undefined)));
}

function clock(at) {
  return new Date(at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase();
}

function time(at) {
  return node("time", clock(at), { datetime: at });
}

function shortDate(date) {
  return date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }).replace(",", "").toLowerCase();
}

function dayOf(at) {
  const day = new Date(at);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (day.toDateString() === new Date().toDateString()) return COPY.today;
  if (day.toDateString() === yesterday.toDateString()) return COPY.yesterday;
  return shortDate(day);
}

function textRow(title, detail, extra) {
  const text = node("span", undefined, { class: "row-text" });
  const bold = node("b", title, { title });
  if (extra) bold.append(extra);
  text.append(bold);
  if (detail) text.append(node("span", detail, { title: detail }));
  return text;
}

function card(title, glyph, ...content) {
  const box = node("section", undefined, { class: "card", "aria-label": title });
  const head = node("div", undefined, { class: "card-strip" });
  head.append(icon(glyph), node("h2", title, { class: "card-title" }));
  box.append(head, ...content);
  return box;
}

function rows(items) {
  const list = node("ul", undefined, { class: "rows" });
  list.append(...items);
  return list;
}

function heading(capsule, title, sub, extra) {
  const head = node("header");
  const h1 = node("h1", title, { class: "headline" });
  head.append(node("span", capsule, { class: "capsule" }), h1);
  if (sub) head.append(node("p", sub, { class: "sub" }));
  if (extra) head.append(extra);
  return [head, h1];
}

function greeting(name) {
  const hour = new Date().getHours();
  const hi = hour < 12 ? COPY.morning : hour < 17 ? COPY.afternoon : COPY.evening;
  return name ? `${hi}, ${name.toLowerCase()}.` : `${hi}.`;
}

function livePill(state) {
  const pill = node("div", undefined, { class: "live", id: "live", role: "status" });
  pill.append(eyes(), node("span", ""));
  setLive(pill, state);
  return pill;
}

function setLive(pill, state) {
  const word = COPY.states[state] || COPY.states.idle;
  pill.dataset.state = state;
  pill.lastElementChild.textContent = word;
  pill.setAttribute("aria-label", COPY.liveLabel(word));
}

window.zoyaState = (state) => {
  const pill = document.getElementById("live");
  if (pill) setLive(pill, state);
};

function doneCount(entries) {
  return entries.filter((e) => !e.failed).reduce((sum, e) => sum + (e.times || 1), 0);
}

function specific(entry) {
  const [head, ...rest] = entry.outcome.split(" · ");
  for (const { outcomes, pattern, say } of SPECIFIC) {
    const match = outcomes.includes(head) && String(entry.heard).match(pattern);
    if (match) return [say(...match.slice(1)), ...rest].join(" · ");
  }
  return entry.outcome;
}

function entryTitle(entry) {
  if (entry.failed) {
    const heard = String(entry.heard || "");
    return DOING.test(heard) && heard.length <= DOING_MAX ? COPY.couldnt(lowerFirst(heard)) : COPY.failed;
  }
  return lowerFirst(entry.outcome ? specific(entry) : COPY.replied);
}

function entryDetail(entry) {
  return entry.said && !entry.failed ? entry.said : `“${entry.heard}”`;
}

function timesMark(entry) {
  if (!(entry.times > 1)) return undefined;
  return node("span", `×${entry.times}`, { class: "times", "aria-label": COPY.timesLabel(entry.times) });
}

function entryRow(entry, tag = "li") {
  const line = node(tag, undefined, { class: "row" });
  line.append(appIcon(entry), textRow(entryTitle(entry), entryDetail(entry), timesMark(entry)), time(entry.at));
  return line;
}

function turnOn(name) {
  const made = button(COPY.turnOn, () => ask("openPermissionPane", { pane: name }), "pill-glossy");
  made.setAttribute("aria-label", `turn on ${COPY.permissions[name]}`);
  return made;
}

function needRow(title, detail, action) {
  const line = node("li", undefined, { class: "row" });
  const words = textRow(title, detail);
  words.classList.add("is-wrapping");
  line.append(node("span", undefined, { class: "dot", "aria-hidden": "true" }), words, action);
  return line;
}

function permissionNeeds(setup) {
  return Object.keys(COPY.permissions)
    .filter((name) => !setup.permissions[name])
    .map((name) => needRow(COPY.permissionOff[name], COPY.permissionWhy[name], turnOn(name)));
}

function dollars(cents) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(cents / 100);
}

function allowanceLow(plan) {
  return Boolean(plan && plan.capCents && plan.usedCents / plan.capCents >= ALLOWANCE_WARN);
}

function allowanceNeed(plan) {
  const left = dollars(Math.max(plan.capCents - plan.usedCents, 0));
  return needRow(COPY.allowanceLow, COPY.allowanceWhy(left), button(COPY.openPlan, () => (location.hash = "plan"), "pill-glossy"));
}

function waysGrid() {
  const grid = node("div", undefined, { class: "ways" });
  for (const way of COPY.ways) {
    const tile = node("div", undefined, { class: "way" });
    const keys = node("div", undefined, { class: "keys" });
    if (way.keys) {
      keys.setAttribute("role", "img");
      keys.setAttribute("aria-label", way.names);
      for (const key of way.keys) keys.append(node("kbd", key, { "aria-hidden": "true" }));
    } else {
      keys.append(node("span", way.bubble, { class: "bubble-glossy" }));
    }
    tile.append(keys, node("b", way.title), node("span", way.hint, { class: "hint" }));
    grid.append(tile);
  }
  return grid;
}

function renderToday({ entries, setup, name, state, plan }) {
  const needs = permissionNeeds(setup);
  if (allowanceLow(plan)) needs.push(allowanceNeed(plan));
  const sub = COPY.doneToday(doneCount(entries)) + COPY.needsCount(needs.length);
  const [head, title] = heading(`${COPY.today} · ${shortDate(new Date())}`, greeting(name), sub, livePill(state));
  const needList = rows(needs);
  const needCard = card(COPY.needsTitle, "circle-alert", needList);
  needCard.hidden = needs.length === 0;
  const done = entries.length
    ? rows(entries.slice(0, TODAY_ROWS).map((entry) => entryRow(entry)))
    : node("p", COPY.doneEmpty, { class: "empty" });
  return [[head, needCard, card(COPY.doneTitle, "check", done), waysGrid()], title];
}

function facts(entry) {
  const list = node("dl", undefined, { class: entry.confirm ? "facts is-confirm" : "facts" });
  const add = (key, value) => {
    if (!value) return;
    const cell = node("dd");
    cell.append(value);
    list.append(node("dt", key), cell);
  };
  add(COPY.heard, `“${entry.heard}”`);
  add(COPY.did, entryTitle(entry));
  if (entry.failed) add(COPY.why, entry.why);
  else add(COPY.said, entry.said);
  if (entry.confirm) {
    const c = entry.confirm;
    add(COPY.asked, node("span", [c.action, c.recipient_or_item, c.amount].filter(Boolean).join(", "), { class: "stake" }));
    add(COPY.outcome, lowerFirst(entry.outcome));
  }
  return list;
}

function historyEntry(entry) {
  const item = node("li");
  const details = node("details", undefined, { class: "entry" });
  details.append(entryRow(entry, "summary"), facts(entry));
  item.append(details);
  return item;
}

function renderHistory({ entries }) {
  const total = entries.reduce((sum, e) => sum + (e.times || 1), 0);
  const clear = entries.length ? button(COPY.clearHistory, confirmClear) : undefined;
  const [head, title] = heading(COPY.historyCapsule, COPY.historyTitle, COPY.historySub(total));
  const page = [head];
  if (clear) {
    clear.style.marginTop = "18px";
    head.append(node("div"), clear);
  }
  page.push(node("div", undefined, { id: "clear-slot" }));
  if (!entries.length) return [[...page, emptyCard(COPY.historyEmpty, COPY.historySay)], title];
  for (const [day, group] of Map.groupBy(entries, (e) => dayOf(e.at))) {
    page.push(node("span", day, { class: "capsule day" }));
    const box = node("section", undefined, { class: "card is-close", "aria-label": day });
    box.append(rows(group.map(historyEntry)));
    page.push(box);
  }
  return [page, title];
}

async function confirmClear() {
  const slot = document.getElementById("clear-slot");
  if (!slot) return;
  const { token, count } = await ask("prepareClearHistory");
  const box = node("div", undefined, { class: "confirm-clear", role: "alertdialog", "aria-modal": "false", "aria-labelledby": "clear-ask" });
  if (!count) {
    box.append(node("p", COPY.clearNothing, { id: "clear-ask" }));
    slot.replaceChildren(box);
    return;
  }
  const cancel = button(COPY.cancel, () => slot.replaceChildren());
  const clear = button(COPY.clearHistory, async () => {
    const { cleared } = await ask("clearHistory", { token });
    if (cleared === null) {
      slot.replaceChildren(node("p", COPY.clearRefused, { role: "status", class: "empty" }));
      return;
    }
    await show("history");
    announce(COPY.cleared);
  }, "button is-danger");
  box.append(node("p", COPY.clearAsk(count), { id: "clear-ask" }), cancel, clear);
  slot.replaceChildren(box);
  cancel.focus();
}

function dateOf(at) {
  return new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "short" }).toLowerCase();
}

function monthOf(at) {
  const day = new Date(at);
  if (!at || Number.isNaN(day.getTime())) return COPY.earlier;
  const now = new Date();
  if (day.getFullYear() === now.getFullYear() && day.getMonth() === now.getMonth()) return COPY.thisMonth;
  const year = day.getFullYear() === now.getFullYear() ? {} : { year: "numeric" };
  return day.toLocaleDateString("en-GB", { month: "long", ...year }).toLowerCase();
}

function memoryRow(item, list, group) {
  const line = node("li", undefined, { class: "row is-top" });
  const remove = button(COPY.delete, () => softDelete(line, item, list, group), "button row-action");
  remove.prepend(icon("trash-2"));
  remove.setAttribute("aria-label", `delete: ${item.content}`);
  const words = textRow(item.content);
  words.classList.add("is-wrapping");
  line.append(words, item.at ? node("span", dateOf(item.at), { class: "trail" }) : node("span"), remove);
  return line;
}

function toast(text, onUndo) {
  document.querySelector(".toast")?.remove();
  const bar = node("div", undefined, { class: "toast", role: "status" });
  bar.append(node("span", text));
  if (onUndo) {
    const undo = button(COPY.undo, onUndo);
    undo.prepend(icon("undo-2"));
    undo.setAttribute("aria-keyshortcuts", "Meta+Z");
    bar.append(undo);
  }
  document.body.append(bar);
  return bar;
}

function dismiss(bar) {
  bar.classList.add("is-leaving");
  after(bar).then(() => bar.remove());
}

function softDelete(line, item, list, group) {
  const place = line.nextSibling;
  let timer;
  line.classList.add("is-leaving");
  const gone = after(line).then(() => {
    line.remove();
    line.classList.remove("is-leaving");
    group.hidden = list.children.length === 0;
  });
  const restore = async () => {
    await gone;
    group.hidden = false;
    list.insertBefore(line, place?.parentNode === list ? place : null);
    line.classList.add("is-returning");
    after(line).then(() => line.classList.remove("is-returning"));
  };
  const undo = async () => {
    clearTimeout(timer);
    dismiss(bar);
    await restore();
    line.querySelector("button").focus();
  };
  const bar = toast(COPY.deleted(item.content), undo);
  bar.querySelector("button").focus();
  const commit = async () => {
    if (bar.contains(document.activeElement)) {
      timer = setTimeout(commit, UNDO_GRACE_MS);
      return;
    }
    dismiss(bar);
    if (!(await ask("deleteMemory", { memory: item.id }))) {
      await restore();
      toast(COPY.deleteFailed);
    }
  };
  timer = setTimeout(commit, UNDO_MS);
  bar.addEventListener("keydown", (event) => {
    if (event.metaKey && event.key === "z") undo();
  });
}

function emptyCard(text, say) {
  const box = node("section", undefined, { class: "card" });
  const body = node("div", undefined, { class: "empty" });
  body.append(node("p", text));
  if (say) body.append(node("span", say, { class: "bubble-glossy" }));
  box.append(body);
  return box;
}

function renderMemory({ items }) {
  const [head, title] = heading(COPY.memoryCapsule, COPY.memoryTitle, COPY.memorySub(items.length));
  if (!items.length) return [[head, emptyCard(COPY.memoryEmpty, COPY.memorySay)], title];
  const page = [head];
  for (const [month, group] of Map.groupBy(items, (item) => monthOf(item.at))) {
    const section = node("section", undefined, { class: "group", "aria-label": month });
    const box = node("div", undefined, { class: "card is-close" });
    const list = rows([]);
    for (const item of group) list.append(memoryRow(item, list, section));
    box.append(list);
    section.append(node("span", month, { class: "capsule day" }), box);
    page.push(section);
  }
  return [page, title];
}

function kv(lines) {
  const list = node("dl", undefined, { class: "kv" });
  for (const [key, value, action] of lines) {
    const cell = node("dd");
    if (action) cell.append(action);
    list.append(node("dt", key), node("dd", value, { class: "value" }), cell);
  }
  return list;
}

function renderPlan({ plan }) {
  if (!plan) {
    const [head, title] = heading(COPY.planCapsule, COPY.planTitle);
    return [[head, emptyCard(COPY.planMissing)], title];
  }
  const month = new Date(`${plan.month}-01T12:00:00`).toLocaleDateString("en-GB", { month: "long" }).toLowerCase();
  const [head, title] = heading(COPY.planCapsule, COPY.planTitle, COPY.planSub(month));
  const share = plan.capCents ? Math.min(plan.usedCents / plan.capCents, 1) : 0;
  const meter = node("div", undefined, { class: "meter", role: "meter", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(share * 100)), "aria-label": COPY.planUsed });
  const fill = node("i");
  fill.style.width = `${share * 100}%`;
  meter.append(fill);
  const lines = kv([
    [COPY.planUsed, dollars(plan.usedCents)],
    [COPY.planAllowance, dollars(plan.capCents)],
    [COPY.planLeft, dollars(Math.max(plan.capCents - plan.usedCents, 0))],
  ]);
  return [[head, card(COPY.planCard, "circle-dot", meter, lines)], title];
}

function permissionRow(name, on) {
  const line = node("li", undefined, { class: "row" });
  const dot = node("span", undefined, { class: on ? "dot is-on" : "dot", "aria-hidden": "true" });
  const words = textRow(COPY.permissions[name], COPY.permissionUse[name]);
  words.append(node("span", `, ${on ? COPY.on : COPY.off}`, { class: "sr-only" }));
  line.append(dot, words, on ? node("span", COPY.on, { class: "trail", "aria-hidden": "true" }) : turnOn(name));
  return line;
}

function retro(version) {
  const box = node("aside", undefined, { class: "retro", "aria-labelledby": "about" });
  box.append(node("h2", `ZOYA ${version}`, { id: "about", class: "retro-title" }));
  const body = node("div", undefined, { class: "retro-body" });
  for (const line of COPY.retro) body.append(node("p", line));
  box.append(body);
  return box;
}

function renderSetup(state) {
  const names = Object.keys(COPY.permissions);
  const on = names.filter((name) => state.permissions[name]).length;
  const [head, title] = heading(COPY.setupCapsule, COPY.setupTitle, COPY.setupSub(on, names.length));
  const permissions = card(COPY.permissionsCard, "list-checks", rows(names.map((name) => permissionRow(name, state.permissions[name]))));
  const note = node("p", "", { class: "sub", role: "status", id: "setup-note" });
  const updates = button(COPY.updates, async () => {
    await ask("checkForUpdates");
    note.textContent = COPY.checking;
  });
  const report = button(COPY.report, () => ask("sendProblemReport").then(() => (note.textContent = COPY.reportSent)));
  const mac = card(COPY.macCard, "laptop", kv([
    [COPY.keyLabel, state.license ? COPY.keySaved : COPY.keyNone],
    [COPY.versionLabel, state.version, updates],
    [COPY.helpLabel, "", report],
  ]));
  return [[head, permissions, mac, note, retro(state.version)], title];
}

function applySettings(settings) {
  document.documentElement.classList.toggle("is-large", settings.largerText === true);
  document.documentElement.classList.toggle("is-legible", settings.easierLetters === true);
}

function switchRow(key, label, settings) {
  const line = node("label", undefined, { class: "row" });
  const box = node("input", undefined, { type: "checkbox", role: "switch", class: "switch" });
  box.checked = settings[key] === true;
  box.addEventListener("change", async () => applySettings(await ask("setSetting", { key, value: box.checked })));
  line.append(textRow(label), box);
  return line;
}

function positions(settings) {
  const line = node("div", undefined, { class: "row" });
  const group = node("div", undefined, { class: "segments", role: "radiogroup", "aria-label": COPY.pillPosition });
  for (const [value, label] of Object.entries(COPY.positions)) {
    const choice = node("label");
    const radio = node("input", undefined, { type: "radio", name: "pill", value });
    radio.checked = settings.pillPosition === value;
    radio.addEventListener("change", () => ask("setSetting", { key: "pillPosition", value }));
    choice.append(radio, label);
    group.append(choice);
  }
  line.append(textRow(COPY.pillPosition), group);
  return line;
}

function keysRow(settings) {
  const line = node("div", undefined, { class: "row" });
  const group = node("div", undefined, { class: "segments", role: "radiogroup", "aria-label": COPY.holdToTalk });
  for (const [value, label] of Object.entries(COPY.hotkeys)) {
    const choice = node("label", undefined, { "aria-label": HOTKEYS[value].names });
    const radio = node("input", undefined, { type: "radio", name: "hotkey", value });
    radio.checked = settings.hotkey === value;
    radio.addEventListener("change", () => {
      currentHotkey = value;
      ask("setSetting", { key: "hotkey", value });
    });
    choice.append(radio, label);
    group.append(choice);
  }
  line.append(textRow(COPY.holdToTalk, COPY.holdHint), group);
  return line;
}

function renderVoice(settings) {
  const [head, title] = heading(COPY.voiceCapsule, COPY.voiceTitle, COPY.voiceSub);
  const cards = [
    card(COPY.keysCard, "keyboard", rows([keysRow(settings)])),
    card(COPY.pillCard, "circle-dot", rows([positions(settings)])),
    card(COPY.readingCard, "type", rows([switchRow("largerText", COPY.largerText, settings), switchRow("easierLetters", COPY.easierLetters, settings)])),
    card(COPY.startCard, "power", rows([switchRow("launchAtLogin", COPY.launchAtLogin, settings)])),
  ];
  return [[head, ...cards], title];
}

const RENDER = { today: renderToday, history: renderHistory, memory: renderMemory, plan: renderPlan, setup: renderSetup, voice: renderVoice };
const TITLES = { today: "today", history: "history", memory: "memory", plan: "plan", setup: "setup", voice: "voice & keys" };

function announce(text) {
  const live = document.getElementById("announce");
  live.textContent = "";
  requestAnimationFrame(() => (live.textContent = text));
}

function heads(page) {
  const heads = {
    today: [`${COPY.today} · ${shortDate(new Date())}`],
    history: [COPY.historyCapsule, COPY.historyTitle],
    memory: [COPY.memoryCapsule, COPY.memoryTitle],
    setup: [COPY.setupCapsule, COPY.setupTitle],
    voice: [COPY.voiceCapsule, COPY.voiceTitle],
    plan: [COPY.planCapsule, COPY.planTitle],
  };
  return heads[page];
}

function bone(kind) {
  return node("span", undefined, { class: `bone is-${kind}`, "aria-hidden": "true" });
}

function boneHead(page) {
  const [capsule, title] = heads(page);
  const head = node("header");
  head.append(node("span", capsule, { class: "capsule" }), title ? node("h1", title, { class: "headline" }) : bone("title"), bone("sub"));
  if (page === "today") head.append(bone("live"));
  return head;
}

function boneRows(count, lead) {
  const list = node("ul", undefined, { class: "rows" });
  for (let i = 0; i < count; i++) {
    const line = node("li", undefined, { class: "row" });
    const words = node("span", undefined, { class: "row-text" });
    words.append(bone("line"), bone("detail"));
    if (lead) line.append(bone(lead));
    line.append(words, bone("trail"));
    list.append(line);
  }
  return list;
}

function skeleton(page) {
  const head = boneHead(page);
  const shapes = {
    today: () => [card(COPY.doneTitle, "check", boneRows(4, "app")), waysGrid()],
    history: () => [bone("capsule"), node("section", undefined, { class: "card is-close" })],
    memory: () => [bone("capsule"), node("div", undefined, { class: "card is-close" })],
    setup: () => [card(COPY.permissionsCard, "list-checks", boneRows(4, "dot")), card(COPY.macCard, "laptop", boneRows(3))],
    voice: () => [card(COPY.keysCard, "keyboard", boneRows(1)), card(COPY.pillCard, "circle-dot", boneRows(1)), card(COPY.readingCard, "type", boneRows(2)), card(COPY.startCard, "power", boneRows(1))],
    plan: () => [card(COPY.planCard, "circle-dot", bone("meter"), boneRows(3))],
  };
  const parts = shapes[page]();
  if (page === "history") parts[1].append(boneRows(6, "app"));
  if (page === "memory") parts[1].append(boneRows(4));
  return [head, ...parts];
}

function failed(page) {
  const [capsule, title] = heads(page);
  const [head] = heading(capsule, title || greeting());
  const box = node("div", undefined, { class: "notice", role: "alert" });
  box.append(icon("circle-alert"), node("p", COPY.loadFailed[page]), button(COPY.tryAgain, () => show(page)));
  return [head, box];
}

function paint(content, busy) {
  const column = document.getElementById("column");
  column.replaceChildren(...content);
  column.setAttribute("aria-busy", String(busy));
  if (arrived) return;
  arrived = true;
  column.classList.add("is-arriving");
  after(column).then(() => column.classList.remove("is-arriving"));
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(() => resolve(LATE), ms));
}

async function withPlan(mine, data) {
  const plan = ask("getPage", { page: "plan" }, PLAN_WAIT_MS).then((reply) => (reply === LATE ? knownPlan : (knownPlan = reply.plan)));
  const first = await Promise.race([plan, wait(PLAN_BUDGET_MS)]);
  data.plan = first === LATE ? knownPlan : first;
  if (first !== LATE) return;
  plan.then((fresh) => {
    if (mine === turn && allowanceLow(fresh) !== allowanceLow(data.plan)) paint(RENDER.today({ ...data, plan: fresh })[0], false);
  });
}

async function show(page) {
  const mine = ++turn;
  const slow = setTimeout(() => mine === turn && paint(skeleton(page), true), SKELETON_AFTER_MS);
  const data = await ask("getPage", { page }, page === "plan" ? PLAN_WAIT_MS : PAGE_WAIT_MS);
  if (page === "today" && data !== LATE) await withPlan(mine, data);
  clearTimeout(slow);
  if (mine !== turn) return;
  let content;
  try {
    if (data === LATE) throw new Error(page);
    currentHotkey = data.hotkey || data.setup?.hotkey || currentHotkey;
    [content] = RENDER[page](data);
  } catch {
    content = failed(page);
  }
  paint(content, false);
  document.title = `zoya · ${TITLES[page]}`;
  window.scrollTo(0, 0);
  ask("pageState", { page });
}

function currentPage() {
  const page = location.hash.slice(1);
  return page in RENDER ? page : "today";
}

function setUpAsk() {
  const form = document.getElementById("ask");
  const input = document.getElementById("ask-input");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    await ask("ask", { text });
    announce(COPY.sent(text));
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") input.blur();
  });
  document.addEventListener("keydown", (event) => {
    if (event.metaKey && event.key.toLowerCase() === "k") {
      event.preventDefault();
      input.focus();
      input.select();
    }
  });
}

function watchTheme() {
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const root = document.documentElement;
    root.classList.add("is-theme-switching");
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("is-theme-switching")));
  });
}

window.addEventListener("hashchange", async () => {
  await show(currentPage());
  document.getElementById("page").focus({ preventScroll: true });
});

setUpAsk();
watchTheme();
ask("getPage", { page: "voice" }).then(applySettings);
show(currentPage());
