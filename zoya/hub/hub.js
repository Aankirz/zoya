const COPY = {
  morning: "Good morning.",
  afternoon: "Good afternoon.",
  evening: "Good evening.",
  todayLead: "Here’s what I did for you today.",
  todayEmpty: "Nothing yet today. Say “Hey Zoya” whenever you need me.",
  talkTitle: "Talk to me",
  talk: [
    ["Say", "Hey Zoya", "then say what you want."],
    ["Or hold", "Control + Option", "while you talk."],
    ["Say", "Stop", "and I stop, right away."],
  ],
  historyTitle: "History",
  historyLead: "Every request, and what came of it. It stays on this Mac.",
  historyEmpty: "Nothing here yet. Everything you ask me will be listed here, and only on this Mac.",
  asked: "I asked you to confirm",
  outcomes: {
    confirmed: "You said confirm.",
    cancel: "You said no, so nothing happened.",
    timeout: "No answer came, so nothing happened.",
    stop: "You said stop, so nothing happened.",
    changed: "The page changed, so I stopped.",
  },
  memoryTitle: "Memory",
  memoryLead: "What I remember about you. You decide what stays.",
  memoryPromise: "Delete anything here, and I forget it for good.",
  memoryEmpty: "I don’t remember anything about you yet. Tell me something, like “remember I like masala chai”, and it will be here.",
  delete: "Delete",
  deleted: "Deleted.",
  undo: "Undo",
  deleteFailed: "I couldn’t delete that. Try again in a moment.",
  planTitle: "Plan",
  planLead: "This month’s allowance.",
  planUsed: (used, cap) => `${used} used of ${cap}.`,
  planLeft: (left) => `${left} left this month.`,
  planMissing: "Your plan isn’t available right now. If you use your own keys, there’s no allowance to track.",
  setupTitle: "Setup",
  setupLead: "Everything I need, and whether it’s on.",
  permissions: { microphone: "Microphone", accessibility: "Accessibility", screen: "Screen Recording", automation: "Automation" },
  on: "On",
  off: "Off",
  turnOn: "Turn on",
  license: (has) => (has ? "Your Zoya key is saved." : "No Zoya key is saved. I’m using your own keys."),
  version: (v) => `Version ${v}.`,
  checkUpdates: "Check for updates",
  checking: "Checking. If there’s a new version, I’ll ask you out loud.",
  report: "Send a problem report",
  reportSent: "Making the report now. I’ll tell you when it’s on your Desktop.",
  voiceTitle: "Voice and settings",
  largerText: "Larger captions and text",
  launchAtLogin: "Open Zoya when you log in",
  pillPosition: "Where the pill sits",
  positions: { bottom: "Bottom", left: "Left edge", right: "Right edge" },
};

const UNDO_MS = 8000;
const pending = new Map();
let nextId = 1;

window.zoyaReceive = ({ id, result }) => {
  const resolve = pending.get(id);
  pending.delete(id);
  if (resolve) resolve(result);
};

function ask(cmd, args = {}) {
  const id = nextId++;
  return new Promise((resolve) => {
    pending.set(id, resolve);
    window.webkit.messageHandlers.zoya.postMessage(JSON.stringify({ cmd, id, args }));
  });
}

function node(tag, text, attrs = {}) {
  const made = document.createElement(tag);
  if (text !== undefined) made.textContent = text;
  for (const [key, value] of Object.entries(attrs)) made.setAttribute(key, value);
  return made;
}

function header(title, lead) {
  const head = node("header");
  head.append(node("h1", title));
  if (lead) head.append(node("p", lead, { class: "lead" }));
  return head;
}

function timeOf(at) {
  return new Date(at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? COPY.morning : hour < 17 ? COPY.afternoon : COPY.evening;
}

function talkSection() {
  const section = node("section", undefined, { "aria-labelledby": "talk" });
  section.append(node("h2", COPY.talkTitle, { id: "talk" }));
  const list = node("ul", undefined, { class: "talk" });
  for (const [before, phrase, after] of COPY.talk) {
    const item = node("li");
    item.append(`${before} `, node("span", phrase, { class: "phrase" }), ` ${after}`);
    list.append(item);
  }
  section.append(list);
  return section;
}

function renderToday({ entries }) {
  const page = [header(greeting(), entries.length ? COPY.todayLead : COPY.todayEmpty)];
  if (entries.length) {
    const list = node("ul", undefined, { class: "sentences" });
    for (const e of entries) list.append(node("li", `${e.did}: “${e.heard}”`));
    page.push(list);
  }
  page.push(talkSection());
  return page;
}

function confirmBlock(confirm) {
  const block = node("p", undefined, { class: "asked" });
  const stake = [confirm.action, confirm.recipient_or_item, confirm.amount].filter(Boolean).join(", ");
  block.append(node("b", COPY.asked), node("span", stake));
  const outcome = node("p", COPY.outcomes[confirm.decision] || "", { class: "outcome", "data-kind": confirm.decision });
  return [block, outcome];
}

function renderHistory({ entries }) {
  const page = [header(COPY.historyTitle, entries.length ? COPY.historyLead : COPY.historyEmpty)];
  const list = node("ol", undefined, { class: "requests" });
  for (const e of entries) {
    const item = node("li", undefined, { class: "request" });
    const body = node("div");
    body.append(node("p", `“${e.heard}”`, { class: "heard" }), node("p", e.did, { class: "did" }));
    if (e.confirm) body.append(...confirmBlock(e.confirm));
    item.append(node("time", timeOf(e.at), { datetime: e.at }), body);
    list.append(item);
  }
  if (entries.length) page.push(list);
  return page;
}

function memoryRow(item) {
  const row = node("li", undefined, { class: "memory" });
  const text = node("p", item.content);
  const button = node("button", COPY.delete, { type: "button", class: "delete", "aria-label": `${COPY.delete}: ${item.content}` });
  button.addEventListener("click", () => softDelete(row, text, button, item));
  row.append(text, button);
  return row;
}

function softDelete(row, text, button, item) {
  const status = node("small", COPY.deleted, { role: "status" });
  row.classList.add("is-deleted");
  text.append(status);
  button.textContent = COPY.undo;
  button.setAttribute("aria-label", `${COPY.undo}: ${item.content}`);
  const timer = setTimeout(async () => {
    const ok = await ask("deleteMemory", { memory: item.id });
    if (ok) row.remove();
    else status.textContent = COPY.deleteFailed;
  }, UNDO_MS);
  button.onclick = () => {
    clearTimeout(timer);
    row.replaceWith(memoryRow(item));
  };
}

function renderMemory({ items }) {
  const page = [header(COPY.memoryTitle, items.length ? COPY.memoryLead : COPY.memoryEmpty)];
  if (items.length) {
    page.push(node("p", COPY.memoryPromise, { class: "promise" }));
    const list = node("ul", undefined, { class: "memories" });
    for (const item of items) list.append(memoryRow(item));
    page.push(list);
  }
  return page;
}

function dollars(cents) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(cents / 100);
}

function renderPlan({ plan }) {
  const page = [header(COPY.planTitle, COPY.planLead)];
  if (!plan) return [...page, node("p", COPY.planMissing)];
  const meter = node("meter", undefined, { min: "0", max: String(plan.capCents), value: String(Math.min(plan.usedCents, plan.capCents)) });
  const left = Math.max(plan.capCents - plan.usedCents, 0);
  return [...page, meter, node("p", COPY.planUsed(dollars(plan.usedCents), dollars(plan.capCents))), node("p", COPY.planLeft(dollars(left)))];
}

function actionButton(label, onClick) {
  const button = node("button", label, { type: "button" });
  button.addEventListener("click", onClick);
  return button;
}

function renderSetup(state) {
  const page = [header(COPY.setupTitle, COPY.setupLead)];
  const list = node("ul", undefined, { class: "permissions" });
  for (const [name, label] of Object.entries(COPY.permissions)) {
    const on = state.permissions[name];
    const item = node("li");
    item.append(node("span", label), node("span", on ? COPY.on : COPY.off, { class: on ? "is-on" : "is-off" }));
    if (!on) item.append(actionButton(COPY.turnOn, () => ask("openPermissionPane", { pane: name })));
    list.append(item);
  }
  const note = node("p", "", { role: "status" });
  page.push(list, node("p", COPY.license(state.license)), node("p", COPY.version(state.version)));
  page.push(
    actionButton(COPY.checkUpdates, () => ask("checkForUpdates").then(() => (note.textContent = COPY.checking))),
    actionButton(COPY.report, () => ask("sendProblemReport").then(() => (note.textContent = COPY.reportSent))),
    note
  );
  return page;
}

function toggle(key, label, checked) {
  const wrap = node("label");
  const box = node("input", undefined, { type: "checkbox" });
  box.checked = checked;
  box.addEventListener("change", () => ask("setSetting", { key, value: box.checked }));
  wrap.append(box, ` ${label}`);
  return wrap;
}

function renderVoice(settings) {
  const page = [header(COPY.voiceTitle)];
  const select = node("select", undefined, { id: "pill-position" });
  for (const [value, label] of Object.entries(COPY.positions)) {
    const option = node("option", label, { value });
    option.selected = settings.pillPosition === value;
    select.append(option);
  }
  select.addEventListener("change", () => ask("setSetting", { key: "pillPosition", value: select.value }));
  const position = node("p");
  position.append(node("label", COPY.pillPosition, { for: "pill-position" }), " ", select);
  page.push(toggle("largerText", COPY.largerText, settings.largerText), toggle("launchAtLogin", COPY.launchAtLogin, settings.launchAtLogin), position);
  return page;
}

const RENDER = { today: renderToday, history: renderHistory, memory: renderMemory, plan: renderPlan, setup: renderSetup, voice: renderVoice };

async function show(page) {
  const main = document.getElementById("page");
  const data = await ask("getPage", { page });
  main.replaceChildren(...RENDER[page](data));
  for (const link of document.querySelectorAll("nav a")) {
    if (link.dataset.page === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

function currentPage() {
  const page = location.hash.slice(1);
  return page in RENDER ? page : "today";
}

window.addEventListener("hashchange", () => show(currentPage()));
show(currentPage());
