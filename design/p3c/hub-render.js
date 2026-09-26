function renderNav(current, opts) {
  const items = HUB.nav
    .map(([id, label], i) => {
      const hint = opts.shortcuts ? `<kbd>⌘${i + 1}</kbd>` : "";
      const here = id === current ? ' aria-current="page"' : "";
      return `<li><a href="?page=${id}${hubParams().large ? "&large=1" : ""}"${here}><span>${label}</span>${hint}</a></li>`;
    })
    .join("");
  return `<nav class="side" aria-label="Zoya"><ul>${items}</ul><p class="side-status">${opts.statusMark || ""}<span>Zoya is on</span></p></nav>`;
}

function renderToday(opts) {
  const t = HUB.today;
  const talk = t.talk.map(([a, phrase, b]) => `<li>${a} <span class="phrase">${phrase}</span> ${b}</li>`).join("");
  return `<header class="today-head">${opts.mark || ""}<h1>${t.greeting}</h1><p class="ok">${t.status}</p><p class="lead">${t.lead}</p></header>
    <ul class="sentences">${t.done.map((d) => `<li>${d}</li>`).join("")}</ul>
    <section aria-labelledby="talk"><h2 id="talk">${t.talkTitle}</h2><ul class="talk">${talk}</ul></section>`;
}

function renderHistory() {
  const h = HUB.history;
  const rows = h.rows
    .map(
      (r) => `<li class="request"><time>${r.time}</time><div>
        <p class="heard">“${r.heard}”</p>
        <p class="did">${r.did}</p>
        ${r.asked ? `<p class="asked"><b>I asked you to confirm</b>${r.asked}</p>` : ""}
        <p class="outcome" data-kind="${r.kind}">${r.outcome}</p></div></li>`
    )
    .join("");
  return `<header class="page-head"><h1>${h.title}</h1><p class="lead">${h.lead}</p></header>
    <section aria-labelledby="day"><h2 class="day" id="day">Today</h2><ol class="requests">${rows}</ol></section>`;
}

function renderMemory(opts) {
  const m = HUB.memory;
  const [fact, done, undo] = m.undone;
  const undone = `<li class="memory is-deleted"><p><s>${fact}</s><small role="status">${done}</small></p><button class="delete undo" type="button" aria-label="${undo}: ${fact}">${undo}</button></li>`;
  const items = m.items
    .slice(0, -1)
    .map(
      ([fact, when]) =>
        `<li class="memory"><p>${fact}<small>${when}</small></p><button class="delete" type="button" aria-label="${opts.deleteLabel || "Delete"}: ${fact}">${opts.deleteLabel || "Delete"}</button></li>`
    )
    .join("");
  return `<header class="page-head"><h1>${m.title}</h1><p class="lead">${m.lead}</p></header>
    <p class="promise">${opts.promiseMark || ""}${m.promise}</p>
    <ul class="memories">${items}${undone}</ul>`;
}

function renderHub(opts = {}) {
  const { page, large } = hubParams();
  if (large) document.documentElement.classList.add("is-large");
  const pages = { today: renderToday, history: renderHistory, memory: renderMemory };
  const body = (pages[page] || renderToday)(opts);
  document.body.innerHTML = `${renderNav(page, opts)}<main class="content"><div class="column">${body}<p class="sample">${HUB.sample}</p></div></main>`;
}
