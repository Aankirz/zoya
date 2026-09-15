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
    { href: "#demo", label: "watch" },
    { href: "#abilities", label: "what zoya does" },
    { href: "#get-zoya", label: "get zoya" },
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

// The owner's own demo (youtube oEmbed: "Zoya Demo", Ankit Kiran). The thumbnail is served from
// public/ so the page makes no youtube request until the visitor presses play.
export const DEMO = {
  label: "watch zoya",
  title: "see it for yourself.",
  windowTitle: "zoya demo",
  thumbnail: "/zoya-demo.jpg",
  thumbnailAlt: "a mac screen showing the zoya website, with ankit speaking in the corner of the video.",
  play: "play",
  playLabel: "play the zoya demo video",
  frameTitle: "Zoya demo video",
  embedSrc: "https://www.youtube-nocookie.com/embed/5xJdxuAq51Y?autoplay=1&rel=0",
  linkLabel: "watch on youtube",
  href: "https://youtu.be/5xJdxuAq51Y",
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

const DAILY_COMMAND = "cd zoya && ./start.sh";

// The real install flow is ../start.sh. Every command here must work on a fresh Apple Silicon Mac.
export const GET_ZOYA = {
  label: "get zoya",
  title: "one command. then just talk.",
  needs: "you need a mac with apple silicon, google chrome, and an openai api key.",
  windowTitle: "terminal",
  command: "git clone https://github.com/Aankirz/zoya.git && cd zoya && ./start.sh",
  // Where the URL may wrap on a narrow screen (rendered as <wbr>), so it never splits mid-word.
  commandBreakAfter: "https://github.com/",
  copyLabel: "copy install command",
  copy: "copy",
  copied: "copied",
  stepLabel: "step",
  steps: [
    {
      title: "open terminal and paste this.",
      line: "if your mac offers to install developer tools, say yes, then paste it again.",
      showCommand: true,
      command: "",
    },
    {
      title: "paste your keys when asked.",
      line: "only the openai key is required. your keys stay in a file on your mac.",
      showCommand: false,
      command: "",
    },
    {
      title: "let zoya hear, see and click.",
      // A reopened terminal starts in the home folder, so the rerun needs `cd zoya` too.
      line: "in system settings, privacy & security, allow terminal for microphone, accessibility and screen recording. quit terminal, open it again, and type",
      command: DAILY_COMMAND,
      showCommand: false,
    },
  ],
  after: "every day after: open terminal, type",
  afterCommand: DAILY_COMMAND,
};

// Each phrase checked against zoya/router.py, the skill triggers and zoya/shutdown.py.
export const TALK = {
  label: "talk to zoya",
  title: "say “hey zoya”. then say what you want.",
  line: "or hold fn and shift while you talk.",
  phrases: [
    { say: "hey zoya, open youtube", result: "opens it in your browser." },
    { say: "hey zoya, what's the weather in bangalore?", result: "tells you, out loud." },
    { say: "hey zoya, write a note: call mom at six", result: "saves it to notes." },
    // The spotify skill plays one named song; "a song by…" would search for the words "a song".
    { say: "hey zoya, play tum hi ho by arijit singh on spotify", result: "starts the song." },
    { say: "zoya, stop", result: "stops what it's doing." },
    { say: "zoya, quit", result: "closes zoya. so does control, shift and escape." },
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
      a: "zoya never types a password or a one-time code, and never stores your card. nothing is paid for until you say “confirm”.",
    },
    { q: "which mac do i need?", a: "a mac with apple silicon and an internet connection." },
    {
      q: "when can i get it?",
      a: "today. it's open source. follow the steps in get zoya, or join the waitlist to hear when installing gets even easier.",
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
