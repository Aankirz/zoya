// Every string on the page lives here so copy edits are one-line changes.
// House rules: say what Zoya does for a person, present tense, no em dashes, no invented numbers.
// Mono and grotesk labels are written in sentence case and uppercased in CSS, so screen readers don't spell them out.

export const CONTACT_EMAIL = "sahuankit453@gmail.com";

export const META = {
  title: "Zoya. Your Mac, by voice.",
  description: "Your Mac, by voice. Say what you want done, and Zoya does it. Made for blind and low-vision people.",
};

export const NAV = {
  wordmark: "Zoya",
  tag: "Coming soon",
  join: "Join the waitlist",
};

export const HERO = {
  name: "Zoya",
  chip: "For blind and low-vision people",
  intro: "Your Mac, by voice. Say what you want done, and Zoya does it.",
  origin: "Built in India",
};

export const SAY_HI = {
  src: "/audio/say-hi.mp3",
  label: "Say hi to Zoya",
  stopLabel: "Stop",
  hint: ["Move closer", "Click to say hi"],
  said: "Hi, I'm Zoya. Just tell me what you'd like done.",
};

export const WAITLIST = {
  label: "Your email",
  button: "Join the waitlist",
  sending: "Joining…",
  hint: "One email when Zoya is ready for you. Nothing else.",
  success: "You're on the list. We'll email you when Zoya is ready.",
  errors: {
    empty: "Enter your email address.",
    invalid: "That email doesn't look right. Check it and try again.",
    rateLimited: "Too many tries. Wait a few minutes, then try again.",
    network: "We couldn't reach the waitlist. Check your connection and try again.",
  },
};

export const PROMISES = {
  title: "You're in charge",
  items: [
    { title: "Asks first", detail: "Before anything you can't undo." },
    { title: "Never your passwords", detail: "You type them. Zoya waits." },
    { title: "Stops on your word", detail: "Say “Zoya, stop”." },
  ],
};

export const FOOTER = {
  copyright: "Zoya © 2026",
  contactLead: "Questions?",
  credit: "Built for the Vision OS hackathon.",
};
