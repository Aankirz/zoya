window.FINDINGS = [
  [
    "Hallmark audit: 0 critical · 8 major · 8 minor, fixed",
    [
      "Colour outside the palette: the green status dot is now Zoya blue. Delete was red on a non-error; it is ink now, so red means errors only.",
      "Token discipline (gate 48): every colour, radius and font size now comes from a named token; no inline styles are left.",
      "Missing states (gate 26): Stop, toolbar buttons, the toast's Undo, the callout button and the sidebar rows gained hover, active and disabled.",
      "The worst case wasn't the worst case: the test scenes are now pure white and pure black, and the ratios were re-measured.",
      "Idle was unreadable on the photo: idle is now frosted glass with ink eyes (7.4:1 on black, 12.8:1 on the photo, 14.9:1 on white).",
      "Three equal columns for the layers became one list; the metadata column no longer wanders; newest first; the toast wraps instead of cutting off the memory; the retro window is real text with a stronger dotted fill.",
      "The confirm pill's focus ring is yellow; History's record of a past confirm is quieter (an ink outline and a yellow marker), so only the live pill is loud.",
    ],
  ],
  [
    "Impeccable critique: 28/40, not slop",
    [
      "P1, fixed: captions were 5.6:1, below the AAA target for the text low-vision users read most. They are now 18 pt semibold on a darker blue: 8.2:1 or more over white, black and the photo.",
      "P1, fixed: “is everything okay?” was the faintest text on Today. It is now a full sentence at 20 pt in ink.",
      "P2, fixed: the merge is six frames: idle, bud, apart with words, speaking, merging back, idle; Reduce Motion is a plain fade.",
      "P1, open for the build: these ratios are measured on a CSS approximation. G3 counts only when re-measured on real NSGlassEffectView pixels; if a tint must be lighter to look like glass, the words grow instead.",
      "Added a larger-text row: confirm and speaking at the larger setting.",
    ],
  ],
  [
    "Deterministic detector (impeccable 4.1.0)",
    [
      "Inter is overused: the logged D120 exception.",
      "Nested cards: the mockup's desktop frame around each window, not a product surface.",
      "Side-tab border: the toggle's triangle drew as a border trick; it's now a clip-path, and the finding is gone.",
    ],
  ],
  [
    "Questions for the coordinator before the native build",
    [
      "Toolbar actions such as “Clear history” and “Check for updates” are native NSToolbarItems acting on the page. “Check for updates” is on the allowlist; “Clear history” would be a new command. Add it, or drop the button?",
      "The Undo toast inside WKWebView can only be CSS glass (backdrop-filter), not NSGlassEffectView. Keep it as web glass (my recommendation), or overlay a native glass view?",
      "The spec puts the page title in the toolbar and in the page header; one reviewer finds that redundant. Keep both, or show the toolbar title only once the header scrolls away?",
    ],
  ],
];
