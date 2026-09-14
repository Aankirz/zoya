# Zoya website: design brief (one-page GTM)

Owner-confirmed inputs (2026-09-15): CTA = join the waitlist · audience = blind and low-vision people first ("think like Steve Jobs: research, then design for them") · identity = ChatGPT-Voice-style blue-to-white flowing gradient orb, **no violet** (owner: violet reads as AI slop) · stack = Next.js.

## 1. The one message

> **Your Mac, by voice. Say what you want done. Zoya does it.**

Supporting line (from the product's own pitch): *VoiceOver tells you what's on the screen. Zoya does what you meant.*

Everything on the page serves that message. If a section doesn't make it clearer or make someone want it more, cut it.

## 2. Who it's for, and what that forces

Primary: **blind and low-vision Mac users** (persona: Priya, 34, blind since birth, expert VoiceOver user, listens at 2× speed, frustrated by inaccessible shopping sites). Secondary: families and friends who set up tech for them; hackathon judges (they must "get it" in 5 seconds too).

Most visitors in the primary audience will **hear** this page through VoiceOver before (or instead of) seeing it. Design for that first, then make it beautiful for sighted people:

- **Linear order is the design.** Screen-reader users hear top to bottom. The h1, the one-line value, and the waitlist form must be the first things heard. No decorative text before the h1.
- **Few, meaningful landmarks and headings.** One `h1`, a handful of `h2`s. Too many headings is as bad as too few (TetraLogical, 2026). Real `<header> <main> <footer>`, skip link.
- **Nothing important only visual.** The orb is decorative (`aria-hidden`); its meaning is in text. No text baked into images, no hover-only content.
- **Hear it, don't just read it.** The signature delight for this audience: a **"Hear Zoya"** button that plays a real short clip of Zoya's actual voice (Amazon Polly Kajal, the voice Zoya uses) completing a task, e.g. *"I've added eggs, milk and bread. Your total is 243 rupees. Shall I place the order? Say confirm."* Plus a transcript right under it. The clip must be generated from Zoya's real voice pipeline (or clearly labelled a sample); never fake testimonials or metrics.
- **Waitlist form that a screen reader breezes through:** one email field with a visible label, one button, errors announced via `aria-live`, success announced and focused. No CAPTCHA (it's a blind audience).
- **Low vision:** large type (body ≥ 18 px), contrast ≥ 7:1 for body text (WCAG AAA) in both themes, honours `prefers-contrast`, 200 % zoom without horizontal scroll, `prefers-reduced-motion` stops the orb's motion.
- Language: short sentences, no jargon ("agent", "LLM", "multimodal" don't belong in the hero). Say what it does in everyday words.

Sources: https://tetralogical.com/blog/2026/04/02/designing-for-people-who-are-blind/ · https://pmc.ncbi.nlm.nih.gov/articles/PMC11872227/ (screen-reader wayfinding personas) · WCAG 2.2.

## 3. References (study them live; take the lesson, not the look)

- **heyclicky.com**: a character-led, personal, playful page. Lesson: a friendly "being" on screen, short honest copy, a founder note, a plain FAQ that answers real worries (privacy, is it watching me, what can it do).
- **wisprflow.ai**: "Don't type, *just speak.*" Lesson: a hero that shows the transformation (messy speech → finished result) instead of describing it; three crisp "how it works" beats.

Anti-references: generic AI SaaS (purple gradients, glass cards, "revolutionary AI"), invented stats, stock photos of people in sunglasses, pity framing ("for the disabled"). Zoya is capability and independence, not charity.

## 4. Page shape (one page, in this order)

1. **Hero:** h1 message · one supporting sentence · email waitlist form · "Hear Zoya" button. The flowing blue orb breathes behind/next to it (reacts to "Hear Zoya": listening → speaking).
2. **The transformation:** one spoken sentence ("Hey Zoya, order my usual groceries") → what Zoya actually does, step by step, as text that reads well aloud (opens Amazon, finds your usual items, reads the total, asks you to confirm). Wispr's lesson, in Zoya's words.
3. **Three promises** (not a card grid): *It does the whole task* · *It always asks before anything you can't undo* (spoken "confirm" before paying, sending, deleting) · *It never types your passwords or codes*. Plus "Say 'Zoya, stop' any time."
4. **Things you can say:** a short list of real commands she handles today (open apps, "what's on my screen?", web research, shopping, documents and presentations, reminders, memory, several tasks at once). Only capabilities that actually work (see README / docs/ZOYA_TECHNICAL_DOC.md §4).
5. **Honest FAQ** (4–6): Is it watching my screen all the time? Does it replace VoiceOver? (No, it works alongside it.) What about passwords? Which Mac? When can I get it? Is it free?
6. **Closing waitlist** + footer (built for the Vision OS hackathon; contact).

## 5. Visual direction

- **Scene:** a blind professional's sister in Bangalore opens the link on her phone at night to see what her sibling was talking about; a judge glances at it on a projector in a bright hall. → Both themes must feel intentional; pick a default by that scene (builder decides and says why), support the other via `prefers-color-scheme`.
- **Signature:** the orb. Blue-to-near-white, soft flowing clouds inside (see owner's reference: deep periwinkle blue at the top-left, milky white flowing across). Built with CSS/SVG/canvas (WebGL only if it stays smooth and light); GPU-composited; stops for reduced motion.
- **Colour strategy:** Restrained, with the orb's blue as the only accent. Tint neutrals toward that blue. No violet anywhere.
- **Type:** one distinctive, highly legible family with strong weight contrast (legibility beats novelty for low vision). Not on impeccable's reflex-reject list. Large, generous, calm.
- **Motion:** minimal and purposeful; ease-out, no bounce.

## 6. Constraints

- **Next.js** (App Router, TypeScript) in `site/` at the repo root. Static where possible. No UI kit; hand-written CSS (CSS modules or one global stylesheet with tokens).
- **Deploy: Vercel** (owner, 2026-09-15). The coordinator deploys after review and sets env vars. `npm run build` must pass with no env vars set.
- **Analytics:** Vercel Web Analytics (`@vercel/analytics`, cookieless) only. No other trackers.
- **Waitlist storage:** Neon Postgres via `DATABASE_URL`, table `waitlist(email pk, created_at)`, `on conflict do nothing`. Local dev without `DATABASE_URL` falls back to `site/data/waitlist.jsonl` (git-ignored). Honeypot field (no CAPTCHA); per-IP rate limit is best-effort on serverless.
- **Visitor count with an eye icon** (owner): real unique visitors from table `visitors(id pk, first_seen)`. A random id is kept in localStorage and posted once. Shown quietly as an aria-hidden eye icon plus the text "N people have visited", rendered server-side, never in an aria-live region, never seeded. Hidden when `DATABASE_URL` is unset.
- **Honest copy only:** no invented numbers, users, logos or quotes. No em dashes in copy.
- Performance: Lighthouse ≥ 95 on Accessibility, Best Practices and SEO; LCP < 2.5 s; JS kept small.
- **Local only.** Do not deploy anywhere or create accounts. Commit on `main` in small conventional commits; **do not push** until the owner has seen it.

## 7. Done when

1. VoiceOver (Safari, macOS) reads: skip link → h1 → value line → waitlist field → "Hear Zoya" within the first few swipes; every section is reachable by heading navigation.
2. Waitlist works end to end with keyboard + VoiceOver: invalid email announced, success announced, entry lands in `waitlist.jsonl`.
3. "Hear Zoya" plays a real Zoya voice clip with a visible transcript.
4. axe-core: 0 violations; Lighthouse Accessibility 100.
5. 320 / 375 / 768 / 1440 px: no horizontal scroll; 200 % zoom works.
6. Reduced motion stops the orb; body contrast ≥ 7:1 in both themes.
7. Owner judges it "clear in 5 seconds" and a delight (🧑).
8. Deployed on Vercel with the live link shared; waitlist signups land in Neon from the live site.
9. Vercel Web Analytics enabled and recording page views.
10. Visitor count with an eye icon shows real unique visitors: a second visit from the same browser doesn't increase it, and a fresh browser does. It isn't announced repeatedly by VoiceOver.
