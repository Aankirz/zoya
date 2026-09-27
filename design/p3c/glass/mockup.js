const STATES = [
  { id: "idle", title: "Idle", note: "untinted, no words", pill: `<span class="pill glass" data-tint="clear"><span class="eyes"><i></i><i></i></span></span>` },
  {
    id: "listening",
    title: "Listening",
    note: "blue tint",
    caption: `<span class="caption glass is-heard" data-tint="blue">“Play the new Arijit Singh song on Spotify”</span>`,
    pill: `<span class="pill glass" data-tint="blue"><span class="eyes is-tall"><i></i><i></i></span>Listening<button class="stop" type="button" aria-label="Stop"></button></span>`,
  },
  {
    id: "thinking",
    title: "Thinking",
    note: "neutral tint",
    pill: `<span class="pill glass" data-tint="neutral"><span class="eyes is-dot"><i></i><i></i></span>Searching Spotify<button class="stop" type="button" aria-label="Stop"></button></span>`,
  },
  {
    id: "speaking",
    title: "Speaking",
    note: "blue tint",
    caption: `<span class="caption glass" data-tint="blue">Playing Tum Hi Ho by Arijit Singh.</span>`,
    pill: `<span class="pill glass" data-tint="blue"><span class="eyes is-talk"><i></i><i></i></span>Speaking<button class="stop" type="button" aria-label="Stop"></button></span>`,
  },
  {
    id: "confirm",
    title: "Confirm",
    note: "near-opaque night",
    pill: `<span class="pill glass" data-tint="night"><span class="eyes is-up"><i></i><i></i></span><span class="ask"><strong>Place the order for boAt earphones, ₹1,249</strong><small>Say “confirm”, or “stop”</small></span><button class="stop" type="button" aria-label="Stop"></button></span>`,
  },
  {
    id: "error",
    title: "Error",
    note: "warm tint",
    caption: `<span class="caption glass" data-tint="warm">Check that this Mac is online, then ask me again.</span>`,
    pill: `<span class="pill glass" data-tint="warm"><span class="eyes is-sad"><i></i><i></i></span>Can’t reach Spotify<button class="stop" type="button" aria-label="Stop"></button></span>`,
  },
];

const WALLS = [
  ["white", "white wallpaper"],
  ["black", "black wallpaper"],
  ["busy", "busy photo (Sonoma, this Mac)"],
];

const RATIOS = window.RATIOS || {};

function buildWalls(id, states) {
  const grid = document.getElementById(id);
  grid.insertAdjacentHTML("beforeend", `<span></span>${WALLS.map(([, label]) => `<span class="col-head">${label}</span>`).join("")}`);
  for (const state of states) {
    grid.insertAdjacentHTML("beforeend", `<span class="row-head">${state.title}<small>${state.note}</small></span>`);
    for (const [wall] of WALLS) {
      const key = `${id === "walls" ? "" : "large-"}${state.id}-${wall}`;
      const ratio = RATIOS[key];
      const measured = ratio ? `<p class="note ratios">${ratio}</p>` : "";
      grid.insertAdjacentHTML(
        "beforeend",
        `<div><div class="scene is-${wall}" data-cell="${key}"><div class="stack">${state.caption || ""}${state.pill}</div></div>${measured}</div>`
      );
    }
  }
}

const BLUE = "oklch(47% 0.19 258)";
const CAPTION = "oklch(40% 0.17 258)";
const FROST = "oklch(98% 0.004 255)";
const INK = "oklch(18% 0.01 260)";
const PAPER = "oklch(99% 0.004 255)";

const FRAMES = [
  ["1 · idle", "One small frosted shape, eyes at rest.", { idle: true }],
  ["2 · bud", "You say “Hey Zoya”: the pill tints and a bead of glass rises.", { word: "Listening", bud: { y: 86, w: 64, h: 30 } }],
  ["3 · apart", "Your words appear in the caption, now its own shape.", { word: "Listening", cap: { y: 46, w: 250, h: 44, text: "“Play Tum Hi Ho on Spotify”" } }],
  ["4 · speaking", "Her answer takes the same caption.", { word: "Speaking", cap: { y: 46, w: 250, h: 44, text: "Playing Tum Hi Ho." } }],
  ["5 · merging back", "She finishes: the caption sinks into the pill.", { word: "Speaking", bud: { y: 84, w: 120, h: 34 } }],
  ["6 · idle", "One shape again. With Reduce Motion, frames 2 to 5 are a plain fade.", { idle: true }],
];

function pillShape(f) {
  if (f.idle) {
    return `<rect x="120" y="126" width="60" height="30" rx="15" fill="${FROST}" opacity="0.85"/><g fill="${INK}"><ellipse cx="143" cy="141" rx="4" ry="5.5"/><ellipse cx="157" cy="141" rx="4" ry="5.5"/></g>`;
  }
  return "";
}

function frame([title, line, f], index) {
  if (f.idle) {
    return `<figure><div class="scene is-busy"><svg viewBox="0 0 300 170" role="img" aria-label="${title}">${pillShape(f)}</svg></div><figcaption><b>${title}.</b> ${line}</figcaption></figure>`;
  }
  const bud = f.bud ? `<rect x="${150 - f.bud.w / 2}" y="${f.bud.y}" width="${f.bud.w}" height="${f.bud.h}" rx="${f.bud.h / 2}"/>` : "";
  const cap = f.cap ? `<rect x="${150 - f.cap.w / 2}" y="${f.cap.y}" width="${f.cap.w}" height="${f.cap.h}" rx="${f.cap.h / 2}" fill="${CAPTION}"/>` : "";
  const capText = f.cap ? `<text x="150" y="${f.cap.y + 27}" text-anchor="middle" font-size="14" fill="${PAPER}">${f.cap.text}</text>` : "";
  return `<figure><div class="scene is-busy"><svg viewBox="0 0 300 170" role="img" aria-label="${title}">
    <defs><filter id="goo-${index}" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="6"/><feColorMatrix values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 24 -10"/></filter></defs>
    <g filter="url(#goo-${index})" fill="${BLUE}">${bud}<rect x="85" y="118" width="130" height="40" rx="20"/></g>${cap}${capText}
    <g fill="${PAPER}"><ellipse cx="104" cy="138" rx="3.5" ry="5"/><ellipse cx="115" cy="138" rx="3.5" ry="5"/></g>
    <text x="126" y="143" font-size="13" fill="${PAPER}">${f.word}</text>
    <circle cx="198" cy="138" r="12" fill="${PAPER}"/><rect x="194" y="134" width="8" height="8" rx="1.5" fill="${INK}"/>
  </svg></div><figcaption><b>${title}.</b> ${line}</figcaption></figure>`;
}

function buildMerge() {
  document.getElementById("merge-frames").innerHTML = FRAMES.map(frame).join("");
}

function buildFindings() {
  const findings = window.FINDINGS || [["Pending", ["Audits run after the first render."]]];
  document.getElementById("findings").innerHTML = findings
    .map(([title, items]) => `<section><h3>${title}</h3><ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul></section>`)
    .join("");
}

buildWalls("walls", STATES);
buildWalls("walls-large", STATES.filter((st) => st.id === "speaking" || st.id === "confirm"));
buildMerge();
buildFindings();
