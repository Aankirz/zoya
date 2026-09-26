const STATES = [
  { id: "idle", title: "Idle", note: "Small and quiet. Nothing to stop." },
  {
    id: "listening",
    title: "Listening",
    heard: "Play the new Arijit Singh song on Spotify",
    note: "Reacts to the voice level.",
  },
  {
    id: "thinking",
    title: "Thinking",
    heard: "Play the new Arijit Singh song on Spotify",
    step: "Searching Spotify",
    note: "The step, in plain words.",
  },
  {
    id: "speaking",
    title: "Speaking",
    said: "Playing Tum Hi Ho by Arijit Singh.",
    note: "Her words, as she says them.",
  },
  {
    id: "confirm",
    title: "Waiting for confirm",
    said: "One pair of boAt earphones, from Amazon.",
    ask: "Place the order, ₹1,249",
    how: "Say “confirm”, or “stop”",
    note: "The safety gate. Shown here, answered only by voice.",
  },
  {
    id: "error",
    title: "Error",
    said: "Check that this Mac is online, then ask me again.",
    cause: "Can’t reach Spotify",
    note: "The cause in the pill, the fix in the caption.",
  },
];

const HUB_PAGES = [
  ["today", "Today"],
  ["history", "History"],
  ["memory", "Memory"],
];

const MAC_ICONS = ["finder", "notes", "mail", "music", "settings"];

function el(tag, attrs = {}, html = "") {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.innerHTML = html;
  return node;
}

function section(title, lead) {
  const node = el("section", { class: "sheet-section" });
  node.append(el("h2", {}, title));
  if (lead) node.append(el("p", {}, lead));
  return node;
}

function specSection(d) {
  const node = section(d.name, d.line);
  const spec = el(
    "dl",
    { class: "spec" },
    `<dt>Type</dt><dd>${d.type}</dd><dt>Motion</dt><dd>${d.motion}</dd><dt>Confirm</dt><dd>${d.confirm}</dd>`
  );
  node.append(spec);
  const swatches = el("div", { class: "swatches" });
  for (const [name, value] of d.tokens) {
    swatches.append(
      el("div", { class: "swatch", style: `--c:${value}` }, `<i></i><b>${name}</b><span>${value}</span>`)
    );
  }
  node.append(swatches);
  return node;
}

function desktopSection(d) {
  const node = section(
    "On this Mac, at real size",
    "1512 × 982 points: a capture of this Mac with everything below the menu bar blurred. The pill sits bottom-centre, above where the Dock appears."
  );
  const wrap = el("div", { class: "scroll-x" });
  const desk = el("div", { class: "desktop", role: "img", "aria-label": "The pill listening, on this Mac's desktop" });
  const dock = el("div", { class: "pill-dock" });
  dock.innerHTML = d.pill(STATES[1], {});
  desk.append(dock);
  wrap.append(desk);
  node.append(wrap);
  return node;
}

function statesSection(d) {
  const node = section(
    "Every state, 1:1",
    "Each state reads without motion: by shape, colour and a word. Example words; nothing here is a real request."
  );
  const strip = el("div", { class: "state-strip" });
  const crops = [...STATES.map((s) => [s, {}]), [STATES[4], { large: true }], [STATES[3], { large: true }]];
  for (const [state, opts] of crops) {
    const fig = el("figure", { class: "state-crop" });
    const stage = el("div", { class: "state-stage" });
    const dock = el("div", { class: "pill-dock" });
    dock.innerHTML = d.pill(state, opts);
    stage.append(dock);
    fig.append(stage);
    const suffix = opts.large ? " · larger text" : "";
    fig.append(el("figcaption", {}, `<b>${state.title}${suffix}.</b> ${state.note}`));
    strip.append(fig);
  }
  node.append(strip);
  return node;
}

function hubSection(d) {
  const node = section(
    "The Hub, at 1280 × 800",
    "Shown at half size; open any frame for the real page. Example content, labelled as such; the built Hub shows only this Mac's real data."
  );
  for (const large of [false, true]) {
    node.append(el("h3", {}, large ? "Larger text" : "Default text"));
    const row = el("div", { class: "hub-row" });
    for (const [page, label] of HUB_PAGES) {
      const src = `hub.html?page=${page}${large ? "&large=1" : ""}`;
      const fig = el("figure", { class: "hub-frame" });
      fig.innerHTML = `<div class="hub-viewport" style="--s:0.5"><iframe src="${src}" title="${label}${large ? ", larger text" : ""}" loading="lazy" tabindex="-1"></iframe></div><figcaption><a href="${src}">${label}${large ? ", larger text" : ""}</a></figcaption>`;
      row.append(fig);
    }
    node.append(row);
  }
  return node;
}

function candidate(src, size) {
  return `<span class="icon-tile" style="--size:${size}px"><span><img src="${src}" alt=""></span></span>`;
}

function real(name, size) {
  return `<img class="icon-real" style="--size:${size}px" src="../assets/macos/${name}-${size === 64 ? 128 : size}.png" alt="">`;
}

function iconSection(d) {
  const node = section(
    "Three icons",
    "Square, full-bleed art. Checked on this Mac: macOS 27 masks a full-bleed .icns into its rounded shape and adds its edge, so this sheet masks it the same way. Beside Finder, Notes, Safari, Music and System Settings, rendered by this Mac."
  );
  node.append(el("h3", {}, "1024 px"));
  const big = el("div", { class: "scroll-x" });
  const row = el("div", { class: "icons-1024" });
  d.icons.forEach(([file, name]) => {
    row.append(el("div", {}, `${candidate(file, 1024)}<div class="icon-label">${name}</div>`));
  });
  row.append(el("div", {}, `${real("finder", 1024)}<div class="icon-label">Finder, for scale</div>`));
  big.append(row);
  node.append(big);
  node.append(el("h3", {}, "128 px, in a light and a dark Dock"));
  for (const dark of [false, true]) {
    const scene = el("div", { class: `dock-scene${dark ? " is-dark" : ""}` });
    d.icons.forEach(([file]) => {
      const dock = el("div", { class: `dock${dark ? " is-dark" : ""}` });
      dock.innerHTML = MAC_ICONS.slice(0, 3).map((n) => real(n, 128)).join("") + candidate(file, 128) + MAC_ICONS.slice(3).map((n) => real(n, 128)).join("");
      scene.append(dock);
    });
    node.append(scene);
  }
  node.append(el("h3", {}, "32 px, as in Finder and the permission lists"));
  const lists = el("div", { class: "hub-row" });
  for (const dark of [false, true]) {
    d.icons.forEach(([file, name]) => {
      const list = el("div", { class: `finder-list${dark ? " is-dark" : ""}` });
      list.innerHTML = [
        `<div class="finder-row">${real("finder", 32)}Finder</div>`,
        `<div class="finder-row">${real("notes", 32)}Notes</div>`,
        `<div class="finder-row">${candidate(file, 32)}Zoya · ${name}</div>`,
        `<div class="finder-row">${real("settings", 32)}System Settings</div>`,
      ].join("");
      lists.append(list);
    });
  }
  node.append(lists);
  return node;
}

function findingsSection(d) {
  const node = section("What the audits flagged", "Hallmark audit and Impeccable critique of this direction, and what changed because of them.");
  const grid = el("div", { class: "findings" });
  for (const [title, items] of d.findings) {
    grid.append(el("section", {}, `<h3>${title}</h3><ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul>`));
  }
  node.append(grid);
  return node;
}

function buildSheet(d) {
  document.title = `Zoya P3c · ${d.name}`;
  const main = el("main", { class: "sheet" });
  main.append(
    el(
      "header",
      { class: "sheet-head" },
      `<p><a href="../index.html">All three directions</a></p><h1>${d.name}</h1><p>${d.line}</p>`
    )
  );
  for (const build of [specSection, desktopSection, statesSection, hubSection, iconSection, findingsSection]) {
    main.append(build(d));
  }
  document.body.append(main);
}

function cropFigure(d, state, caption) {
  return `<figure class="state-crop card-crop"><div class="state-stage"><div class="pill-dock">${d.pill(state, {})}</div></div><figcaption>${caption}</figcaption></figure>`;
}

function buildCard(d) {
  document.body.classList.add("is-card");
  const findings = d.findings
    .map(([title, items]) => `<h3>${title}</h3><ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul>`)
    .join("");
  const swatches = d.tokens
    .map(([name, value]) => `<div class="swatch" style="--c:${value}"><i></i><b>${name}</b></div>`)
    .join("");
  const icons = d.icons.map(([file, name]) => `<div>${candidate(file, 128)}<div class="icon-label">${name}</div></div>`).join("");
  document.body.innerHTML = `<main class="card">
    <h2><a href="index.html" target="_top">${d.name}</a></h2><p class="card-line">${d.line}</p>
    <dl class="spec"><dt>Type</dt><dd>${d.type}</dd><dt>Motion</dt><dd>${d.motion}</dd><dt>Confirm</dt><dd>${d.confirm}</dd></dl>
    <div class="swatches">${swatches}</div>
    ${cropFigure(d, STATES[1], "<b>Listening</b>, at 80%")}
    ${cropFigure(d, STATES[4], "<b>Waiting for confirm</b>, the loudest state, at 80%")}
    <figure class="hub-frame"><div class="hub-viewport" style="--s:0.3672"><iframe src="hub.html?page=today" title="Today" tabindex="-1"></iframe></div><figcaption>The Hub, Today</figcaption></figure>
    <div class="card-icons">${icons}</div>
    <section class="card-findings">${findings}</section>
  </main>`;
}

function start(d) {
  if (new URLSearchParams(location.search).get("card") === "1") buildCard(d);
  else buildSheet(d);
}
