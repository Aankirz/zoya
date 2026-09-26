const BAR_HEIGHTS = [8, 14, 20, 12, 18, 10, 6];

function bars() {
  return `<span class="zp-bars" aria-hidden="true">${BAR_HEIGHTS.map((h, i) => `<i style="--h:${h}px;--i:${i}"></i>`).join("")}</span>`;
}

function stop() {
  return `<button class="zp-stop" type="button" aria-label="Stop"></button>`;
}

function caption(s) {
  if (s.id === "confirm") return `<div class="zc">${s.said}</div>`;
  if (s.said) return `<div class="zc">${s.said}</div>`;
  if (s.heard) return `<div class="zc"><span class="zc-heard">“${s.heard}”</span></div>`;
  return "";
}

function body(s) {
  switch (s.id) {
    case "idle":
      return `<span class="sr-only" role="status">Zoya is ready</span>`;
    case "listening":
      return `${bars()}<span role="status">Listening</span>${stop()}`;
    case "thinking":
      return `<span class="zp-dots" aria-hidden="true"><i style="--i:0"></i><i style="--i:1"></i><i style="--i:2"></i></span><span role="status">${s.step}</span>${stop()}`;
    case "speaking":
      return `${bars()}<span role="status">Speaking</span>${stop()}`;
    case "confirm":
      return `<span class="zp-ask"><strong role="status">${s.ask}</strong><small>${s.how}</small></span>${stop()}`;
    default:
      return `<span class="zp-alert" aria-hidden="true"></span><span role="status">${s.cause}</span>${stop()}`;
  }
}

function pillA(s, opts) {
  return `<div class="${opts.large ? "is-large" : ""}" style="display:contents">${caption(s)}<div class="zp" data-state="${s.id}">${body(s)}</div></div>`;
}
