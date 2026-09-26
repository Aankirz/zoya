function eyes() {
  return `<span class="bp-eyes" aria-hidden="true"><i></i><i></i></span>`;
}

function bStop() {
  return `<button class="bp-stop" type="button" aria-label="Stop"></button>`;
}

function bCaption(s) {
  if (s.said) return `<div class="bc">${s.said}</div>`;
  if (s.heard) return `<div class="bc"><span class="bc-heard">“${s.heard}”</span></div>`;
  return "";
}

function bBody(s) {
  switch (s.id) {
    case "idle":
      return `${eyes()}<span class="sr-only" role="status">Zoya is ready</span>`;
    case "listening":
      return `${eyes()}<span role="status">Listening</span>${bStop()}`;
    case "thinking":
      return `${eyes()}<span role="status">${s.step}</span>${bStop()}`;
    case "speaking":
      return `${eyes()}<span role="status">Speaking</span>${bStop()}`;
    case "confirm":
      return `${eyes()}<span class="bp-ask"><strong role="status">${s.ask}</strong><small>${s.how}</small></span>${bStop()}`;
    default:
      return `${eyes()}<span role="status">${s.cause}</span>${bStop()}`;
  }
}

function pillB(s, opts) {
  return `<div class="${opts.large ? "is-large" : ""}" style="display:contents">${bCaption(s)}<div class="bp" data-state="${s.id}">${bBody(s)}</div></div>`;
}
