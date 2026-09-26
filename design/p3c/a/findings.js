const FINDINGS = [
  ["Hallmark audit: 0 critical · 1 major · 4 minor", [
    "Major, fixed: colours written inline instead of as tokens (gate 48). Hover, success, confirm wash and danger wash are now tokens.",
    "Minor, fixed: straight apostrophes in shown copy; nav had no pressed state; Delete's colour change wasn't in its transition; the Memory promise was a filled panel inside the page card, now a line of text.",
    "Minor, open: a few spacing values sit off the 4 px scale. Tightened when the chosen direction is built.",
  ]],
  ["Impeccable critique: 27/40, passes the slop test", [
    "P1, fixed: with larger text the confirm pill was clamped to 56 px and cut its own words. It now grows with its text.",
    "P1, fixed: Error looked like Thinking. It now has a coral outline and names the cause (“Can’t reach Spotify”); the fix is in the caption.",
    "P2, fixed: Listening and Speaking differed only by bar colour. Speaking now fills the pill with Zoya blue: her voice is blue.",
    "P2, fixed: deleting a memory had no undo. A deleted row now reads “Deleted. Undo” for a few seconds before it is forgotten.",
    "P1, for Stage 2: no dark theme yet, and the idle dash needs a light hairline on dark wallpapers.",
  ]],
  ["Deterministic detector (impeccable 4.1.0)", [
    "1 warning: the thinking dots pulse. Kept on purpose: they are tied to live work, stop with Reduce Motion, and stay fully visible.",
  ]],
  ["Every direction, fixed after review", [
    "“Waiting for your yes” taught the wrong word: the gate listens for “confirm”. The pill now says what is at stake (“Place the order, ₹1,249”) and how to answer (“Say confirm, or stop”).",
    "VoiceOver: the pill's label overrode its live text. Now only the state words are a live region, and Stop sits outside it.",
    "“Everything is working” moved under the greeting, above the fold, as plain status rather than a link.",
  ]],
];
