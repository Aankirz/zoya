// Every string on the page lives here so copy edits are one-line changes.
// House rules (BRIEF-v3): heyclicky's lowercase, Steve Jobs voice, honest, no em dashes, no invented numbers or scenarios.

export const CONTACT_EMAIL = "sahuankit453@gmail.com";

export const META = {
  title: "zoya · your mac, by voice, for people who can't see the screen",
  description:
    "zoya lets people who can't see the screen use their mac by voice: say what you want done, and zoya does it.",
};

export const SKIP_LINK = "skip to the waitlist";

export const MENU = {
  brand: "zoya",
  links: [
    { href: "#abilities", label: "what zoya does" },
    { href: "#faq", label: "faq" },
  ],
  cta: "join the waitlist",
};

export const HERO = {
  title: "zoya",
  subline: "your mac, by voice. made for people who can't see the screen.",
};

export const WHY = {
  label: "why zoya",
  title: "the computer was built for people who can see.",
  body: "apps, the internet, and now ai agents. all of it assumes you can see the screen. zoya hands that power to people who can't. say what you want, and zoya does it for you.",
  closer: "a screen reader tells you what's there. zoya does what you meant.",
};

export const HELLO = {
  src: "/audio/say-hi.mp3",
  windowTitle: "hello",
  caption: "hello.mp3",
  playLabel: "hear zoya say hello",
  stopLabel: "stop",
  // What the clip says, word for word (Polly Kajal). Shown typed in the bubble; read by screen readers as the transcript.
  transcript: "Hi, I'm Zoya. Just tell me what you'd like done.",
  transcriptLead: "Zoya says:",
  bubble: "hi, i'm zoya. just tell me what you'd like done.",
};

export const WAITLIST = {
  label: "your email",
  button: "join the waitlist",
  sending: "joining…",
  placeholder: "you@example.com",
  hint: "mac only.",
  success: "you're on the list. we'll email you when zoya is ready.",
  errors: {
    empty: "enter your email address.",
    invalid: "that email doesn't look right. check it and try again.",
    rateLimited: "too many tries. wait a few minutes, then try again.",
    network: "we couldn't reach the waitlist. check your connection and try again.",
  },
};

// Real shipped abilities only (Phase 4 amazon.in shopping with a spoken "confirm", the Spotify skill, the Phase 6
// document agent). Spotify plays by song, artist or album (zoya/skills/spotify_web), so no "mood" claim.
export const ABILITIES = {
  label: "what zoya does",
  items: [
    {
      say: "zoya, buy this on amazon",
      title: "shops for you",
      // Honest: the confirm gate is verified; a real paid order has not been completed yet.
      line: "finds it, adds it to your cart, and asks for your spoken “confirm” before anything is paid for.",
      window: "amazon",
    },
    {
      say: "zoya, play a song on spotify",
      title: "plays your music",
      line: "name a song, an artist or an album, and it starts playing.",
      window: "spotify",
    },
    {
      say: "zoya, make a presentation",
      title: "makes your slides",
      line: "tell it the topic, and your deck is ready in keynote or powerpoint.",
      window: "slides",
    },
  ],
} as const;

// Zoya's two safety habits, shown as drawn windows (tech doc §5.1 and §9.9: spoken confirm; password hand-off with "done").
export const CHARGE = {
  label: "you're in charge",
  items: [
    {
      say: "confirm",
      title: "nothing happens without your yes",
      line: "paying, sending, deleting: zoya stops and waits for your “confirm”.",
      window: "confirm",
    },
    {
      say: "done",
      title: "your passwords stay yours",
      line: "zoya pauses at a password or code. you type it, say “done”, and it carries on.",
      window: "password",
    },
  ],
} as const;

// Visible words inside the drawn windows (decorative, aria-hidden). Text names only, no logos.
export const APP_WINDOWS = {
  amazon: { title: "amazon.in", placeOrder: "place order", sayConfirm: "say confirm" },
  spotify: { title: "spotify" },
  slides: { title: "presentation.pptx" },
  confirm: { title: "checkout", cancel: "cancel", confirm: "confirm" },
  password: { title: "sign in", waiting: "zoya is waiting" },
};

export const FAQ = {
  label: "faq",
  title: "questions, answered",
  items: [
    {
      q: "is zoya watching my screen all the time?",
      a: "no. zoya looks at your screen only when a task needs it, like when you ask “what's on my screen?”. it listens for “hey zoya” right on your mac, and your voice recordings stay there.",
    },
    {
      q: "does zoya replace voiceover?",
      a: "no. keep voiceover for moving around your mac. zoya works right alongside it and takes on whole tasks.",
    },
    {
      q: "what about passwords and payments?",
      a: "zoya never types a password or a one-time code, and never stores your card. nothing is paid for until you say “confirm”.",
    },
    { q: "which mac do i need?", a: "a mac with apple silicon and an internet connection." },
    {
      q: "when can i get it?",
      a: "zoya works today on our own macs. join the waitlist and we'll email you the moment it's ready for yours.",
    },
  ],
};

export const FOOTER = {
  disclaimer: "zoya looks at your screen only when a task needs it.",
  contactLead: "questions?",
  iconsLead: "icons by",
  iconsName: "rune icons",
  iconsHref: "https://www.runeicons.com",
  copyright: "© zoya 2026",
};
