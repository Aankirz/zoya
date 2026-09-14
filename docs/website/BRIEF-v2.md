# Zoya website v2: redesign brief (supersedes BRIEF.md for layout, visuals and copy)

Owner feedback on v1 (2026-09-15), verbatim in spirit:
- "I hate websites that are not centered." No left/right split anywhere.
- Remove the circular gradient orb completely. No radial glows, no ChatGPT-voice swirl.
- Take inspiration from **https://heyliki.com** and look very similar to it.
- The scripted examples (grocery order, transcript, "things you can say") are unconvincing. Remove all of them.
- Think like Steve Jobs: one idea, said simply, with total confidence.

Unchanged from BRIEF.md: blind and low-vision people first (VoiceOver order is the design), waitlist is the only CTA, Next.js in `site/`, Neon waitlist + real visitor count with the eye icon, Vercel Web Analytics, honest copy, no em dashes, accessibility "Done when" items 1–6 and 8–10.

## 1. What to take from heyliki.com (DNA, not assets)

- **Surface:** near-black ground (theirs `#0a0a0c`), warm cream text (`#f2f1ec` / `#ede8dc`), muted grey secondary text, one blue accent (`#4d6bfe`) used sparingly. Dark by default. Write ours in OKLCH, tinted.
- **Voice of the type:** a clean grotesk for statements (they use Host Grotesk); a handwritten script greeting, slightly rotated, in cream (they use Italianno); tiny uppercase mono meta lines with wide tracking (e.g. `ALGORITHM ENGINEER · AI PRODUCT BUILDER`).
- **Signature:** a cream **line-art illustration** on black that you can click. A mono hint under it says `MOVE CLOSER · CLICK TO SAY HI`, and it reacts.
- **Calm:** lots of black space, small restrained type for secondary text, ease-out motion.
- Don't copy their illustration, photos, words or files.

## 1b. Captured reference (builder, Playwright)

heyliki.com on desktop is actually a left/right split (copy left, portrait right) with a soft navy radial glow, and stacks to one column on mobile. The owner wants the heyliki look but centered and without glows. So: **heyliki's components, arranged as its mobile stack, centered, at every width.** Components to mirror:

- A floating **pill nav**, top center: script wordmark "Zoya" + a small outlined tag, plus one light pill button "Join the waitlist" (it jumps to the form). No other links.
- A big **script name** ("Zoya") in cream: the `h1`, real text.
- An **outlined chip** with a blue dot: `FOR BLIND AND LOW-VISION PEOPLE · ON YOUR MAC`.
- A short **intro paragraph** in muted grey: "Your Mac, by voice. Say what you want done, and Zoya does it."
- A **mono line**: `BUILT IN INDIA · COMING TO YOUR MAC`. It must stay true.
- **Big numbered ruled rows** (01 / 02 / 03, hairline rules, grotesk labels, mono sub-lines) for the three promises, centered.
- The **line-art character** with `MOVE CLOSER · CLICK TO SAY HI`: on click, a cream speech bubble shows the words while Zoya's real voice says them.
- A **hairline footer** with mono lines: `Zoya © 2026` · eye icon + visitor count · contact.

Where this conflicts with §2 below, §1b wins.

## 2. Zoya's page, centered, top to bottom

Every block is a single centered column (text-align center, max-width ~640px for text, ~440px for the form). No grid splits at any width.

1. **Greeting (decorative):** script "hi, I'm Zoya", cream, slightly rotated. `aria-hidden`, because the h1 carries the meaning.
2. **Line-art Zoya moment (the signature):** a hand-drawn-style cream line illustration, centered, about 320–380px. Suggested subject: a listening face in profile with a few soft sound lines. The builder may propose something better but must show it at the checkpoint. It's an inline SVG with `stroke="currentColor"` and no gradient or glow.
   - It is a real `<button>` labelled **"Say hi to Zoya"**. Clicking it plays Zoya's real Polly Kajal voice saying one line, e.g. *"Hi, I'm Zoya. Just tell me what you'd like done."* The lines get a subtle "speaking" motion (stroke-dash or gentle scale), the label flips to "Stop", and it stays static under reduced motion.
   - Mono hint under it: `CLICK TO SAY HI` (aria-hidden, since the button name says it).
   - This replaces the grocery clip. It's a greeting, not a fake task.
3. **h1:** "Your Mac, by voice."
4. **One line:** "Say what you want done. Zoya does it."
5. **Mono meta line:** `FOR BLIND AND LOW-VISION PEOPLE · ON YOUR MAC`
6. **Waitlist:** email + "Join the waitlist", same accessible behaviour and strings as v1.
7. **Three promises**, centered, small mono label `YOU'RE IN CHARGE`, three short lines with no cards and no numbers:
   - Zoya asks before anything you can't undo.
   - Zoya never types your passwords.
   - Say "Zoya, stop" and it stops.
8. **Footer**, centered: `Zoya` · eye icon + "N people have visited" · Questions? sahuankit453@gmail.com · Built for the Vision OS hackathon.

**Removed:** the orb (everywhere, including the favicon if it's orb-like), the hero clip and transcript, the "One sentence. The whole task." band, "Things you can say today", the FAQ, and the closing waitlist duplicate. One form only.

## 3. Low-vision guardrails on heyliki's style

- Tiny mono text: minimum 13px (theirs is 9–10px) and contrast ≥ 4.5:1. Body and statement text ≥ 7:1.
- Script greeting is decorative only; never the only place a word appears.
- Keep a legible body family (Atkinson Hyperlegible Next is fine). Statements may use a grotesk. Mono label family: any legible mono.
- Light theme via `prefers-color-scheme: light` stays supported (cream becomes ink on warm off-white), but dark is the default look.
- Blue accent only for the button, focus rings and links.

## 4. Done when (v2)

1. No two-column layout at 320 / 375 / 768 / 1440 px; every block is centered.
2. No radial or circular gradient anywhere (grep the CSS for `radial-gradient` and `blur(`).
3. VoiceOver order: skip link → h1 → one line → "Say hi to Zoya" → meta → email → Join the waitlist → promises → footer.
4. The greeting clip is real Polly Kajal and plays with keyboard and VoiceOver.
5. axe 0 violations, Lighthouse Accessibility 100, no horizontal scroll at 200 % zoom.
6. Owner says it looks like heyliki and feels Steve-Jobs simple (🧑).
