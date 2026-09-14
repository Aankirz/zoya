// Every string on the page lives here so copy edits are one-line changes.
// House rules (BRIEF-v3): heyclicky's lowercase, Steve Jobs voice, honest, no em dashes, no invented numbers or scenarios.

export const CONTACT_EMAIL = "sahuankit453@gmail.com";

export const META = {
  title: "zoya · your mac, by voice",
  description: "your mac, by voice. say what you want done, and zoya does it. made for blind and low-vision people.",
};

export const SKIP_LINK = "skip to the waitlist";

export const MENU = {
  brand: "zoya",
  links: [
    { href: "#promises", label: "promises" },
    { href: "#faq", label: "faq" },
  ],
  cta: "join the waitlist",
};

export const HERO = {
  title: "zoya",
  subline: "your mac, by voice. say what you want done, and zoya does it.",
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
  hint: "made for blind and low-vision people. mac only.",
  success: "you're on the list. we'll email you when zoya is ready.",
  errors: {
    empty: "enter your email address.",
    invalid: "that email doesn't look right. check it and try again.",
    rateLimited: "too many tries. wait a few minutes, then try again.",
    network: "we couldn't reach the waitlist. check your connection and try again.",
  },
};

export const PROMISES = {
  label: "promises",
  items: [
    {
      say: "confirm",
      title: "zoya asks before anything you can't undo",
      line: "paying, sending, deleting: zoya waits for your “confirm”.",
    },
    {
      say: "done",
      title: "your passwords stay yours",
      line: "zoya pauses, you type them, you say “done”.",
    },
    {
      say: "zoya, stop",
      title: "stop means stop",
      line: "say it any time, and zoya stops.",
    },
  ],
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
      a: "zoya never types a password or a one-time code, and never stores your card. it uses the payment already saved on the site, and pays only after you say “confirm”.",
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
  credit: "built for the vision os hackathon",
  iconsLead: "icons by",
  iconsName: "rune icons",
  iconsHref: "https://www.runeicons.com",
  copyright: "© zoya 2026",
};
