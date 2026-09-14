// Every string on the page lives here so copy edits are one-line changes.
// House rules: say what Zoya does for a person, present tense, no em dashes, no invented numbers.

export const CONTACT_EMAIL = "sahuankit453@gmail.com";

export const META = {
  title: "Zoya. Your Mac, by voice.",
  description:
    "Say what you want done. Zoya does it: orders your groceries, reads your screen, makes your presentation. Made for blind and low-vision people.",
};

export const SKIP_LINK = "Skip to the waitlist";

export const HERO = {
  titleLines: ["Your Mac,", "by voice."],
  lede: "Say what you want done. Zoya does it.",
};

export const CLIP = {
  src: "/audio/hear-zoya.mp3",
  playLabel: "Hear Zoya",
  pauseLabel: "Pause Zoya",
  label: "Zoya's real voice, finishing a grocery order.",
  text: "I've added eggs, milk and bread. Your total is 243 rupees. Shall I place the order? Say confirm.",
  // Amazon Polly word speech marks for this exact clip (Kajal, neural, en-IN): [ms, start char].
  marks: [
    [200, 0], [450, 5], [937, 11], [1375, 17], [1750, 22], [1875, 26],
    [2892, 33], [3042, 38], [3455, 44], [3642, 47], [4480, 51],
    [4842, 59], [5130, 65], [5217, 67], [5530, 73], [5830, 77],
    [6747, 84], [6922, 88],
  ] as ReadonlyArray<readonly [number, number]>,
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
  title: "You're in charge. Always.",
  items: [
    {
      title: "Zoya asks before anything you can't undo.",
      body: "Paying, sending, deleting. Zoya stops and waits for you to say “confirm”. Even if you said “just buy it”.",
    },
    {
      title: "Zoya never types your passwords.",
      body: "Passwords and one-time codes stay yours. Zoya pauses, you type them, you say “done”, and it carries on.",
    },
    {
      title: "Zoya stops the moment you say so.",
      body: "Say “Zoya, stop” any time. While it talks. While it clicks. While it thinks.",
    },
  ],
};

export const TRANSFORMATION = {
  title: "One sentence. The whole task.",
  lead: "With a screen reader, a grocery order takes hundreds of keystrokes. With Zoya, it takes one sentence.",
  saidLabel: "You say",
  said: "“Hey Zoya, order my usual groceries.”",
  doneLabel: "Zoya does",
  steps: [
    "Opens Amazon.",
    "Remembers your usual: eggs, milk and bread.",
    "Adds them to your cart.",
    "Reads you the total.",
    "Waits for your “confirm” before it pays.",
  ],
  closerQuiet: "VoiceOver tells you what's on the screen.",
  closerLoud: "Zoya does what you meant.",
};

export const THINGS_TO_SAY = {
  title: "Things you can say today.",
  items: [
    { say: "“Open Spotify.”", does: "Opens any app or website." },
    { say: "“What's on my screen?”", does: "Tells you what's in front of you." },
    {
      say: "“Find the best budget headphones and read me the top three.”",
      does: "Searches the web and reads back what matters.",
    },
    { say: "“Order my usual groceries.”", does: "Shops for you, then waits for your “confirm”." },
    {
      say: "“Make a six-slide presentation on renewable energy.”",
      does: "Builds the deck while you get on with your day.",
    },
    { say: "“Remember I like brown bread.”", does: "Remembers what matters to you." },
    { say: "“Remind me in ten minutes to drink water.”", does: "Reminds you, right on time." },
    {
      say: "“What are you working on?”",
      does: "Runs several tasks at once and tells you where each one stands.",
    },
  ],
};

export const FAQ = {
  title: "Questions",
  items: [
    {
      q: "Is Zoya watching my screen all the time?",
      a: "No. Zoya looks at your screen only when a task needs it, like when you ask “What's on my screen?”. It listens for “Hey Zoya” right on your Mac, and your voice recordings stay there.",
    },
    {
      q: "Does Zoya replace VoiceOver?",
      a: "No. Keep VoiceOver for moving around your Mac. Zoya works right alongside it and takes on whole tasks.",
    },
    {
      q: "What about passwords and payments?",
      a: "Zoya never types a password or a one-time code, and never stores your card. It uses the payment already saved on the site, and pays only after you say “confirm”.",
    },
    { q: "Which Mac do I need?", a: "A Mac with Apple silicon and an internet connection." },
    {
      q: "When can I get it?",
      a: "Zoya works today on our own Macs. Join the waitlist and we'll email you the moment it's ready for yours.",
    },
    { q: "Is it free?", a: "Pricing isn't set yet. People on the waitlist hear first." },
  ],
};

export const CLOSING = {
  title: "Be one of the first.",
  body: "Join the waitlist. We'll email you when Zoya is ready for your Mac.",
};

export const FOOTER = {
  brand: "Zoya",
  credit: "Built for the Vision OS hackathon.",
  contactLead: "Questions?",
};
