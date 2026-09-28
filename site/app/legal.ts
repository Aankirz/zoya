// DRAFT FOR LEGAL REVIEW. Not reviewed by a lawyer. Do not treat as final terms until the owner and counsel sign off.
// The words of /terms, /privacy and /refunds. Every product fact is checked against the code and cited beside it;
// every fact the code can't show is a [PLACEHOLDER] listed in OWNER_NEEDED, and lib/legal.test.ts fails on any other.

export const PLACEHOLDER_PATTERN = /\[[A-Z][A-Z ]*[A-Z]\]/g;

// What only the owner can supply, and why it's needed.
export const OWNER_NEEDED = {
  "[LEGAL ENTITY]": "The person or company that sells Zoya and is the contracting party.",
  "[ENTITY COUNTRY]": "Where that entity is established.",
  "[POSTAL ADDRESS]": "A postal address for legal notices and privacy requests.",
  "[GOVERNING LAW]": "Which country's (or state's) law governs the terms, and its courts.",
  "[MINIMUM AGE]": "The minimum age to buy and use Zoya.",
  "[REFUND WINDOW]": "How many days after a charge a refund can be asked for.",
  "[HOW TO CANCEL]": "How a customer cancels: a Dodo customer portal link, an email, or both.",
  "[RETENTION PERIOD]": "How long license and usage rows and Dodo records are kept after a subscription ends.",
  "[EFFECTIVE DATE]": "The date these documents take effect.",
} as const;

export type Placeholder = keyof typeof OWNER_NEEDED;

export type LegalSection = {
  readonly heading: string;
  readonly body?: readonly string[];
  readonly list?: readonly string[];
};

export type LegalDoc = {
  readonly path: string;
  readonly label: string;
  readonly title: string;
  readonly lead: string;
  readonly sections: readonly LegalSection[];
};

export const LEGAL_COMMON = {
  capsule: "legal",
  draft: "draft. this page is waiting for legal review.",
  effective: "effective [EFFECTIVE DATE].",
  contactHeading: "contact",
  contactLead: "Questions about this page? Write to",
  postal: "Post: [LEGAL ENTITY], [POSTAL ADDRESS].",
  home: "back to zoya",
};

// Sources: relay/src/relay.ts (overCap, the 402 "allowance" message), relay/src/cost.ts (OVERALL_CEILING_MULTIPLIER),
// relay/PAYMENTS.md (Dodo emails the key; cancelled, expired, on hold and paused revoke it), app/copy.ts (the confirm gate).
export const TERMS: LegalDoc = {
  path: "/terms",
  label: "terms",
  title: "terms of service",
  lead: "These terms are the agreement between you and [LEGAL ENTITY], of [ENTITY COUNTRY], when you buy or use Zoya.",
  sections: [
    {
      heading: "what zoya is",
      body: [
        "Zoya is a voice assistant for the Mac. You hold fn and shift, say what you want, and Zoya does it across your apps and websites.",
        "Zoya needs a Mac with Apple silicon and an internet connection.",
      ],
    },
    {
      heading: "who can use it",
      body: [
        "You must be at least [MINIMUM AGE] to buy or use Zoya. If you buy for a business, you confirm you're allowed to accept these terms for it.",
      ],
    },
    {
      heading: "buying zoya",
      body: [
        "Zoya costs $20 a month. Dodo Payments sells the subscription as our reseller and merchant of record: Dodo takes the payment and handles billing, sales tax and receipts.",
        "After you pay, Dodo emails you a license key. The key is for you. Don't share it or resell it.",
        "Your subscription renews every month until it is cancelled. [HOW TO CANCEL]",
        "When a subscription is cancelled, expires, is paused or is put on hold after a failed payment, Dodo tells us and the key stops working. If the subscription comes back, the key works again.",
      ],
    },
    {
      heading: "fair use",
      body: [
        "Each subscription includes a monthly allowance of the cloud services Zoya uses. Heavier tasks pause first when a month's allowance is used up, and everything pauses at a higher ceiling. Both reset at the start of the next calendar month (UTC).",
        "Don't use Zoya to break the law, to harm people, to attack or overload our service, or to get around the allowance.",
      ],
    },
    {
      heading: "you stay in charge",
      body: [
        "Zoya acts for you on your Mac and on the websites and apps you ask it to use. Before anything that pays, sends or deletes, Zoya stops and waits for you to say “confirm”. Zoya never types a password or a one-time code for you.",
        "What you confirm is your decision. Check what Zoya reads back to you before you say “confirm”.",
        "The websites and apps Zoya uses for you have their own terms, and those still apply to you.",
      ],
    },
    {
      heading: "zoya can make mistakes",
      body: [
        "Zoya uses AI models, and they can mishear, misread a screen or get things wrong. Zoya is not a substitute for professional, medical, legal or financial advice.",
        "Zoya is provided as it is. As far as the law allows, [LEGAL ENTITY] is not liable for indirect or consequential losses. Nothing in these terms limits rights the law in your country says can't be limited.",
      ],
    },
    {
      heading: "changes and ending",
      body: [
        "We may update Zoya and these terms. If a change matters, we'll say so in the app and on this page before it takes effect.",
        "You can stop using Zoya at any time. We may suspend a key that breaks these terms.",
      ],
    },
    {
      heading: "the law that applies",
      body: ["These terms are governed by [GOVERNING LAW]."],
    },
  ],
};

// Sources, all in the repo: zoya/config.py (STT_MODEL_REPO, RELAY_URL, MEMORY_LOCAL_FILE, LOG_DIR),
// zoya/speech.py (_engines: Polly via the relay with a license), zoya/models.py (store=False), zoya/decisions.py
// (_endpoint: Jev via the relay), zoya/tools/memory.py (memory.json only), zoya/hub_data.py (history from
// local logs), zoya/screen.py (screenshots in memory only), zoya/tools/weather.py (Open-Meteo, city name only),
// zoya/setup_models.py (Hugging Face download), zoya/diagnostics.py (report zipped to the Desktop),
// packaging/build_app.py (SUFeedURL https://zoya.app/appcast.xml), relay/src/relay.ts (ROUTES, rewrite store:false,
// sha256Hex, log fields), relay/schema.sql and relay/src/store.ts (what the relay keeps), relay/wrangler.jsonc
// (Cloudflare Workers, POLLY_REGION ap-south-1, AI Gateway), site/lib/waitlist.ts, site/lib/visitors.ts,
// site/app/layout.tsx (Vercel Analytics), site/app/copy.ts (DEMO: youtube-nocookie only after play).
export const PRIVACY: LegalDoc = {
  path: "/privacy",
  label: "privacy",
  title: "privacy policy",
  lead: "Zoya keeps as much as it can on your Mac. This page says exactly what leaves it, where it goes, and what we keep. [LEGAL ENTITY] is responsible for your data.",
  sections: [
    {
      heading: "what stays on your mac",
      body: ["These never leave your Mac:"],
      list: [
        "Your voice. Zoya turns speech into text right on your Mac, with a Whisper model that runs locally. The audio is not sent anywhere.",
        "Your memories. Things Zoya remembers about you are kept in one file on your Mac, ~/.zoya/memory.json, and nowhere else. Card numbers, passwords and one-time codes are refused before anything is saved. When a memory helps answer you, it travels with that request through the relay to OpenAI, like anything else you ask, and nothing is kept there. Delete a memory on the Hub's Memory page and it's gone from the file.",
        "Your history. The Hub's list of what you asked and what Zoya did is read from files on your Mac.",
        "Your license key, which is kept in your Mac's Keychain.",
        "Screenshots. When a task needs to see your screen, the picture is held in memory for that request and never written to disk.",
        "Problem reports. If you ask for one, Zoya saves it to your Desktop with personal details removed. It is only sent if you send it.",
      ],
    },
    {
      heading: "what leaves your mac, and why",
      body: [
        "To understand a request and act on it, Zoya sends the text of what you asked, and, when a task needs it, what's on the relevant screen or web page, through Zoya's relay to the services below. Your recorded voice is never part of it.",
        "Every request to OpenAI is sent with storage turned off (store set to false). Zoya's app sets it, and the relay sets it again on every request.",
      ],
    },
    {
      heading: "what our relay keeps",
      body: [
        "The relay is Zoya's own small server. It checks your license, forwards the request, and counts what it cost. It keeps:",
      ],
      list: [
        "A SHA-256 hash of your license key, never the key itself.",
        "Your usage for each month, in cents, and the number of requests.",
        "The IDs Dodo gives your subscription and your customer account, and whether your key is active.",
        "For beta keys only, the email address the key was sent to.",
        "Short operational logs: the first 8 characters of the key's hash, which service was called, how long it took, how many tokens or characters it used, and what it cost.",
      ],
    },
    {
      heading: "what our relay never keeps",
      body: [
        "The relay does not store your license key, the text of your requests, what was on your screen, or the answers that come back. It passes them through and forgets them.",
      ],
    },
    {
      heading: "who processes your data",
      body: ["These companies handle data for Zoya, each for one job:"],
      list: [
        "OpenAI: the language models that understand your request and plan the steps, with storage turned off.",
        "Amazon Web Services (Amazon Polly, in the ap-south-1 Mumbai region): turns Zoya's replies into speech. It receives the words Zoya is about to say.",
        "Vercel (AI Gateway): carries requests to Jev, a model made by TypeSafe AI that Zoya uses to check what's on screen while it works. It receives a text description of the screen and short questions about it.",
        "Cloudflare: runs the relay.",
        "Neon: the database behind the relay (the hash, usage and subscription rows above) and behind this website (the waitlist and the visitor counter).",
        "Dodo Payments: our merchant of record. Dodo takes your payment, handles tax and receipts, and emails you your key. Dodo holds what you give it at checkout, such as your email address and payment details. We see only the subscription and customer IDs Dodo sends the relay.",
      ],
    },
    {
      heading: "other connections zoya makes",
      list: [
        "Open-Meteo, for the weather. Only the city name you ask about is sent.",
        "Hugging Face, once, to download Zoya's speech models when you first set it up.",
        "zoya.app, to check whether a new version of Zoya is available.",
        "The websites you ask Zoya to use, like any browser would, in Zoya's own browser profile on your Mac.",
      ],
    },
    {
      heading: "this website",
      list: [
        "If you join the waitlist, we keep your email address to tell you when Zoya is ready.",
        "The visitor counter stores a random ID in your browser and counts it once. It is not linked to you.",
        "Vercel hosts the site and runs Vercel Web Analytics.",
        "The demo video loads from YouTube (youtube-nocookie.com) only after you press play.",
      ],
    },
    {
      heading: "how long we keep it",
      body: [
        "Relay records and waitlist emails are kept while your subscription or waitlist spot is active, and for [RETENTION PERIOD] after. What stays on your Mac is yours to delete.",
      ],
    },
    {
      heading: "your choices",
      body: [
        "You can ask us what we hold about you, and ask us to correct or delete it. Write to us and we'll answer. Depending on where you live, you may have more rights, including to complain to your data protection authority.",
        "We don't sell your data, and we don't use it for advertising.",
      ],
    },
  ],
};

// Sources: relay/PAYMENTS.md (the revocation lifecycle); Dodo processes refunds to the original payment method, per
// https://docs.dodopayments.com/features/transactions/refunds (search snippet; the page itself was not reachable).
export const REFUNDS: LegalDoc = {
  path: "/refunds",
  label: "refunds",
  title: "refunds and cancellation",
  lead: "Zoya is $20 a month, sold by Dodo Payments as our merchant of record. Here's how cancelling and refunds work.",
  sections: [
    {
      heading: "cancelling",
      body: [
        "You can cancel at any time. [HOW TO CANCEL]",
        "Once the subscription ends, Dodo tells us and your key stops working. You won't be charged again.",
      ],
    },
    {
      heading: "refunds",
      body: [
        "If Zoya isn't right for you, write to us within [REFUND WINDOW] of a charge to ask for a refund.",
        "Refunds are paid by Dodo Payments, back to the card or payment method you used, in the currency you paid.",
      ],
    },
    {
      heading: "failed payments",
      body: [
        "If a renewal payment fails, your key keeps working during Dodo's grace period. If the subscription is then put on hold, your key pauses, and it works again once the subscription comes off hold.",
      ],
    },
  ],
};

export const LEGAL_DOCS: readonly LegalDoc[] = [TERMS, PRIVACY, REFUNDS];
