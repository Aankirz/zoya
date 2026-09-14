# Zoya website v3: heyclicky-style redesign (supersedes BRIEF.md and BRIEF-v2.md for look, layout and copy)

Owner decisions (2026-09-15):
- The reference is **heyclicky.com** (confirmed, after heyliki). Look "exactly like heyclicky".
- **Light theme only.** No dark theme, no `prefers-color-scheme: dark` variant.
- **Everything centered.** heyclicky's left/right feature rows and 4-column footer get stacked and centered.
- **No gradient orb, no glows, no line-art portrait.** Glossy pill buttons (heyclicky's soft linear gradient) are allowed.
- **Illustrated props only:** no videos or screen recordings.
- **No founder note, no tweet wall, no user counts, no pricing** (none exist yet).
- **No scripted task scenarios** (no grocery orders, no invented transcripts).
- Steve Jobs voice, written in heyclicky's lowercase.

Still binding from BRIEF.md: blind and low-vision people first (VoiceOver order), the waitlist as the only CTA, Next.js in `site/`, Neon waitlist + real visitor count with the eye icon, Vercel Web Analytics, honest copy, no em dashes, axe 0 and Lighthouse Accessibility 100.

Captured reference: builder scratchpad `clicky/` (desktop-light-00…08, mobile-light-00…10, interaction frames, info.json, text.txt).

## 1. heyclicky DNA to mirror (with Zoya's own content and drawn assets; copy no files, text, photos or GIFs)

- **Ground:** `#f5f5f5` light grey with a faint dotted grid (draw it with an SVG pattern, not radial-gradient), white cards, near-black text, one link blue (≈ `#0f7fff`, darkened if needed for contrast).
- **Type:** a neutral neo-grotesk at weight 500, all lowercase headings and body (h1 ≈ 88 px, h2 ≈ 56 px, body 18–20 px). Inter matches heyclicky exactly; the owner's "exactly like" wins over impeccable's reject list here. Small uppercase **capsule labels** in outlined grey pills ("promises", "faq").
- **macOS menu-bar nav:** thin bar pinned at the top. Left: "zoya" plus 2–3 in-page links (promises, faq). Centre: a small animated Zoya mark we draw (a simple glyph that blinks or squishes, like heyclicky's logo). Right: decorative status icons (wifi, battery, clock) marked `aria-hidden`, and a blue "join the waitlist" link.
- **Hero "desktop":** centered `h1` "zoya", subline, glossy blue pill CTA, a grey note under it. The dotted desktop around it is scattered with **props we draw**: Mac windows with traffic lights (showing drawn, abstract content, e.g. a Notes window, a Finder window), blue Finder folders, a trash can, a "HELLO my name is zoya" sticker, one or two simple kaomoji. All props are `aria-hidden` and `pointer-events: none`, or a hover lift that never blocks the CTA. On mobile, props thin out and never cover text.
- **The big window:** heyclicky's large `hello.mov` window becomes a large Mac window titled "hello" that plays **Zoya's real voice greeting** (Polly Kajal, reuse `say-hi.mp3`). A glossy "play" pill sits in the middle; while it plays, animated **waveform dots** show and the words type out in a glossy speech bubble. The button is named "Hear Zoya say hello" and flips to "Stop"; the transcript is in the DOM.
- **Feature rows → three promises, stacked and centered.** Each row: waveform dots, a glossy speech bubble that types a real Zoya control word, a lowercase title, and one line:
  1. bubble "confirm" · **zoya asks before anything you can't undo** · paying, sending, deleting: zoya waits for your "confirm".
  2. bubble "done" · **your passwords stay yours** · zoya pauses, you type them, you say "done".
  3. bubble "zoya, stop" · **stop means stop** · say it any time, and zoya stops.
  These are Zoya's real voice commands, not invented scenarios.
- **FAQ:** centered white rounded rows with a "+" (native details/summary), capsule label "faq". Keep 4–5 honest Q&As from v1: watching my screen, replaces VoiceOver, passwords and payments, which Mac, when can I get it.
- **Footer:** a giant **"zoya" wordmark built from blue Finder-folder shapes we draw** (CSS/SVG), centered. Below it, centered and stacked: a short disclaimer line ("zoya looks at your screen only when a task needs it"), eye icon + "N people have visited", "questions? sahuankit453@gmail.com", "built for the vision os hackathon", "© zoya 2026". A trash can and folder prop may flank it decoratively.
- **Motion:** logo blink/squish, waveform dots, typing bubbles, hover lift on windows (≤ 0.12 s transforms). Everything stops under reduced motion.

## 2. Copy (lowercase, Jobs voice)

- title: "zoya · your mac, by voice"
- h1: **zoya**
- subline: **your mac, by voice. say what you want done, and zoya does it.**
- CTA area: email field (label "your email") + glossy pill **"join the waitlist"**. Note under it: "made for blind and low-vision people. mac only."
- success: "you're on the list. we'll email you when zoya is ready."
- Error messages as in v1, lowercase.

## 3. Accessibility guardrails on heyclicky's style

- Grey text must meet ≥ 4.5:1 (body ≥ 7:1). heyclicky's alpha greys are too faint; darken them.
- Lowercase is visual only if needed; real text stays readable, and brand names read correctly aloud.
- Reading order: skip link → h1 → subline → email → join the waitlist → note → "Hear Zoya say hello" → promises → faq → footer. Decorative props, status icons and kaomoji are `aria-hidden`.
- No layout shift from props; no horizontal scroll at 320 px or at 200 % zoom.

## 4. Done when (v3)

1. Light only; side by side with heyclicky at 1440 and 390, it reads as the same family (🧑 owner judges).
2. Every block centered at 320 / 375 / 768 / 1440, with no left/right splits.
3. No orb or glow; the only gradients are the glossy pills and speech bubbles.
4. No videos, founder note, testimonials, counts or pricing.
5. The hello window plays Zoya's real voice with keyboard and VoiceOver, and the transcript is in the DOM.
6. axe 0 violations (AA + AAA contrast), Lighthouse Accessibility 100, reduced motion honoured.
7. Waitlist + visitor counter + analytics work on Vercel after deploy.
