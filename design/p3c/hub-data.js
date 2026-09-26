const HUB = {
  nav: [
    ["today", "Today"],
    ["history", "History"],
    ["memory", "Memory"],
    ["plan", "Plan"],
    ["setup", "Setup"],
    ["voice", "Voice and settings"],
  ],
  today: {
    greeting: "Good evening.",
    lead: "Here’s what I did for you today.",
    done: [
      "Played Tum Hi Ho by Arijit Singh on Spotify.",
      "Wrote a note: call Mom at six.",
      "Read you the top story on Hacker News.",
      "Ordered earphones on Amazon, after you said confirm.",
    ],
    talkTitle: "Talk to me",
    talk: [
      ["Say", "Hey Zoya", "then say what you want."],
      ["Or hold", "Control + Option", "while you talk."],
      ["Say", "Stop", "and I stop, right away."],
    ],
    status: "Everything is working.",
  },
  history: {
    title: "History",
    lead: "Every request, and what came of it.",
    rows: [
      {
        time: "8:42 PM",
        heard: "Buy the boAt earphones in my cart",
        did: "Found them, added them to the cart and opened checkout.",
        asked: "Place the order: one pair of earphones, ₹1,249.",
        outcome: "You said confirm. Ordered, ₹1,249.",
        kind: "confirmed",
      },
      {
        time: "7:15 PM",
        heard: "Play Tum Hi Ho by Arijit Singh on Spotify",
        did: "Started the song on Spotify.",
        outcome: "Done.",
        kind: "done",
      },
      {
        time: "6:03 PM",
        heard: "Send the report to Priya",
        did: "Wrote the email and stopped before sending.",
        asked: "Send this email to Priya.",
        outcome: "You said stop. Nothing was sent.",
        kind: "stopped",
      },
      {
        time: "5:30 PM",
        heard: "Write a note: call Mom at six",
        did: "Saved it to Notes.",
        outcome: "Done.",
        kind: "done",
      },
    ],
  },
  memory: {
    title: "Memory",
    lead: "What I remember about you. You decide what stays.",
    promise: "Delete anything here, and I forget it for good.",
    undone: ["Your doctor’s appointments are on Tuesdays.", "Deleted.", "Undo"],
    items: [
      ["You like Arijit Singh.", "Learned September 12"],
      ["Your mother’s name is Asha.", "Learned September 3"],
      ["You shop on Amazon India.", "Learned August 28"],
      ["Your doctor’s appointments are on Tuesdays.", "Learned August 21"],
    ],
  },
  sample: "Example content for this mockup. The built Hub shows only this Mac’s real data.",
};

function hubParams() {
  const params = new URLSearchParams(location.search);
  return { page: params.get("page") || "today", large: params.get("large") === "1" };
}
