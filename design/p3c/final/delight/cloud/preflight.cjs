// Mechanical slop pre-flight over a Hub folder: accent hues, grey families, radii, emoji, gradients, repeated labels.
//   node design/p3c/final/delight/cloud/preflight.cjs <hub dir>

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const HUB = path.resolve(process.argv[2] || "zoya/hub");
const read = (name) => fs.readFileSync(path.join(HUB, name), "utf8");
const css = read("tokens.css") + read("hub.css");
const js = read("hub.js");
const html = read("index.html");
const BRAND_GLOSS = /^\s*(\.pill-glossy|\.bubble-glossy|\.segments label:has\(input:checked\)|\.switch:checked)\s*$/;

function colours() {
  const accents = new Set();
  const greys = new Set();
  for (const [, property, value] of css.matchAll(/([\w-]+)\s*:\s*([^;{}]+);/g)) {
    for (const [, l, c, h] of value.matchAll(/oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)/g)) {
      const [light, chroma, hue] = [Number(l), Number(c), Number(h)];
      if (light === 0 || light === 100) continue;
      if (chroma >= 0.03 || property.startsWith("--gloss")) accents.add(hue >= 235 && hue <= 265 ? "zoya blue" : hue >= 60 && hue <= 80 ? "warn yellow" : `hue ${hue}`);
      else greys.add(chroma === 0 ? "hueless" : `hue ${hue}`);
    }
  }
  const warnUses = [...css.matchAll(/([^{}]+)\{[^{}]*var\(--warn\)/g)].map((m) => m[1].trim());
  return { accents: [...accents], greys: [...greys], warnUses };
}

function radii() {
  const scale = css.match(/--radius-[a-z]+:\s*[^;]+/g) || [];
  const off = [];
  for (const [, value] of css.matchAll(/border(?:-[a-z-]+)?-radius:\s*([^;]+);/g)) {
    if (value.split(/\s+/).every((part) => /^var\(--radius-[a-z]+\)$/.test(part))) continue;
    off.push(value);
  }
  return { scale, off };
}

function emoji() {
  return [...(html + js + css).matchAll(/\p{Emoji_Presentation}|\p{Extended_Pictographic}️/gu)].map((m) => m[0]);
}

function gradients() {
  const loose = [];
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/gradient\(/.test(body)) continue;
    if (!BRAND_GLOSS.test(selector.trim().split("\n").pop())) loose.push(selector.trim());
  }
  return loose;
}

function labels() {
  const source = js.slice(js.indexOf("const HOTKEYS"), js.indexOf("\n};\n", js.indexOf("const COPY")) + 3);
  const sandbox = {};
  vm.runInNewContext(`${source}\nthis.COPY = COPY;`, sandbox);
  const seen = new Map();
  const walk = (value, key) => {
    if (typeof value === "string") seen.set(value, [...(seen.get(value) || []), key]);
    else if (Array.isArray(value)) value.forEach((v, i) => walk(v, `${key}[${i}]`));
    else if (value && typeof value === "object") for (const k of Object.keys(value)) walk(value[k], key ? `${key}.${k}` : k);
  };
  walk(sandbox.COPY, "");
  return [...seen].filter(([, keys]) => keys.length > 1).map(([text, keys]) => `${JSON.stringify(text)}: ${keys.join(", ")}`);
}

const { accents, greys, warnUses } = colours();
const { scale, off } = radii();
const report = { accents, warnUses, greys, radiusScale: scale, radiusOffScale: off, emoji: emoji(), gradientsWithoutBrand: gradients(), repeatedLabels: labels() };
console.log(JSON.stringify(report, null, 2));
