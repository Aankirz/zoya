const BRAILLE_Z = [1, 0, 1, 0, 1, 1];

function cell() {
  const dots = [0, 3, 1, 4, 2, 5].map((i) => `<i class="${BRAILLE_Z[i] ? "" : "off"}"></i>`).join("");
  return `<span class="cp-cell" aria-hidden="true">${dots}</span>`;
}

const DOMES = `<svg class="cp-domes" viewBox="0 0 48 48" aria-hidden="true"><g fill="currentColor">${[6, 18, 30, 42].flatMap((y) => [6, 18, 30, 42].map((x) => `<circle cx="${x}" cy="${y}" r="4"/>`)).join("")}</g></svg>`;

const GLYPHS = {
  speaking: `<svg class="cp-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  thinking: `<svg class="cp-glyph" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="2.4" fill="currentColor"/><circle cx="12" cy="12" r="2.4" fill="currentColor"/><circle cx="19" cy="12" r="2.4" fill="currentColor"/></svg>`,
  error: `<svg class="cp-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 22 20H2z" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round"/><path d="M12 10v4.5M12 17.2v.1" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`,
};

function cStop() {
  return `<button class="cp-stop" type="button">Stop</button>`;
}

function cCaption(s) {
  if (s.said) return `<div class="cc"><b>Zoya</b>${s.said}</div>`;
  if (s.heard) return `<div class="cc"><b>You</b>${s.heard}</div>`;
  return "";
}

function cBody(s) {
  switch (s.id) {
    case "idle":
      return `${cell()}<span role="status">Zoya</span>`;
    case "listening":
      return `<span class="cp-meter" aria-hidden="true"></span><span role="status">Listening</span>${cStop()}`;
    case "thinking":
      return `${GLYPHS.thinking}<span role="status">${s.step}</span>${cStop()}`;
    case "speaking":
      return `${GLYPHS.speaking}<span role="status">Speaking</span>${cStop()}`;
    case "confirm":
      return `${DOMES}<span class="cp-ask"><strong role="status">${s.ask}</strong><small>${s.how}</small></span>${cStop()}`;
    default:
      return `${GLYPHS.error}<span role="status">${s.cause}</span>${cStop()}`;
  }
}

function pillC(s, opts) {
  return `<div class="${opts.large ? "is-large" : ""}" style="display:contents">${cCaption(s)}<div class="cp" data-state="${s.id}">${cBody(s)}</div></div>`;
}
