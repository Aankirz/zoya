# Copy deck P5: launch positioning

Every visible string that changed on heyyzoya.com for launch, old → new. All strings live in
`app/copy.ts`; the constant and key are given for each one. "(new)" means there was no old string.

Positioning: zoya is a voice assistant for the mac, for everyone. Hold fn and shift, say it, let go,
done. Blind and low-vision people are fully supported, as one proud line rather than the whole story.
One plan, $20 a month. Join the waitlist is the only call to action.

## Sources for the claims

| Claim | Where it's true |
| --- | --- |
| hold fn and shift to talk | `zoya/voice.py` module docstring: "Push-to-talk (fn + Shift by default)", `PUSH_TO_TALK_KEYS` |
| press ⌘k and type | `zoya/hub/index.html`: the ask field has `aria-keyshortcuts="Meta+K"` |
| transcribed on your mac | `zoya/config.py`: `STT_MODEL_REPO = "mlx-community/whisper-large-v3-turbo"` (local mlx whisper) |
| pays, sends or deletes waits for "confirm" | the existing `CHARGE` copy (spoken confirm gate) |
| $20 a month, no api keys, runs on your mac | the launch brief (task C1) |

## Meta (browser tab, search, social previews)

| Key | Old | New |
| --- | --- | --- |
| `META.title` | zoya · your mac, by voice, for people who can't see the screen | zoya · your mac, by voice |
| `META.description` | zoya lets people who can't see the screen use their mac by voice: say what you want done, and zoya does it. | zoya is a voice assistant for the mac. hold fn and shift, say what you want, let go, and zoya does it across your apps and websites. |
| `META.ogImageAlt` | unchanged: it describes `public/og.jpg`, which still shows the old subline | unchanged until the image is re-shot |

## Menu

| Key | Old | New |
| --- | --- | --- |
| `MENU.links[2]` | get zoya (`#get-zoya`) | pricing (`#pricing`) |

## Hero

| Key | Old | New |
| --- | --- | --- |
| `HERO.subline` | your mac, by voice. made for people who can't see the screen. | your mac, by voice. hold fn and shift, say what you want, and it's done. |

## How it works (new section, after the hello window)

| Key | Old | New |
| --- | --- | --- |
| `HOW.label` | (new) | how it works |
| `HOW.title` | (new) | hold. say it. let go. |
| `HOW.stepLabel` | (new) | step |
| `HOW.steps[0]` | (new) | **hold fn and shift.** in any app, on any website. zoya is listening. |
| `HOW.steps[1]` | (new) | **say it.** in your own words, the way you'd ask a friend. |
| `HOW.steps[2]` | (new) | **let go.** zoya takes it from there, across your apps and the web. |
| `HOW.steps[3]` | (new) | **done.** and anything that pays, sends or deletes still waits for your “confirm”. |

## Why zoya

| Key | Old | New |
| --- | --- | --- |
| `WHY.title` | the computer was built for people who can see. | your mac should do what you mean. |
| `WHY.body` | apps, the internet, and now ai agents. all of it assumes you can see the screen. zoya hands that power to people who can't. say what you want, and zoya does it for you. | every app and every website asks you to find the right button. zoya doesn't. say what you want in your own words, and zoya does it for you, across your apps and the web. |
| `WHY.closer` | a screen reader tells you what's there. zoya does what you meant. | built first for people who can't see the screen. made for everyone. |

## Get zoya (section removed)

The open-source install section is gone: it asked for an openai api key and a terminal command, which
contradicts "no api keys" and "join the waitlist is the only call to action". `InstallCommand.tsx` went
with it. Removed strings:

| Key | Old | New |
| --- | --- | --- |
| `GET_ZOYA.label` | get zoya | (removed) |
| `GET_ZOYA.title` | one command. then just talk. | (removed) |
| `GET_ZOYA.needs` | you need a mac with apple silicon, google chrome, and an openai api key. | (removed) |
| `GET_ZOYA.windowTitle` | terminal | (removed) |
| `GET_ZOYA.command` | git clone https://github.com/Aankirz/zoya.git && cd zoya && ./start.sh | (removed) |
| `GET_ZOYA.copyLabel` / `copy` / `copied` | copy install command / copy / copied | (removed) |
| `GET_ZOYA.stepLabel` | step | (removed) |
| `GET_ZOYA.steps[0]` | **open terminal and paste this.** if your mac offers to install developer tools, say yes, then paste it again. | (removed) |
| `GET_ZOYA.steps[1]` | **paste your keys when asked.** only the openai key is required. your keys stay in a file on your mac. | (removed) |
| `GET_ZOYA.steps[2]` | **let zoya hear, see and click.** in system settings, privacy & security, allow terminal for microphone, accessibility and screen recording. quit terminal, open it again, and type `cd zoya && ./start.sh` | (removed) |
| `GET_ZOYA.after` | every day after: open terminal, type `cd zoya && ./start.sh` | (removed) |

## Talk to zoya

| Key | Old | New |
| --- | --- | --- |
| `TALK.title` | say “hey zoya”. then say what you want. | hold fn and shift. say what you want. |
| `TALK.line` | or hold fn and shift while you talk. | or start with “hey zoya”. or press ⌘k in zoya's window and type. |

## Pricing (new section, before the faq)

| Key | Old | New |
| --- | --- | --- |
| `PRICING.label` | (new) | pricing |
| `PRICING.title` | (new) | one plan. $20 a month. |
| `PRICING.line` | (new) | everything zoya does, for one price. |
| `PRICING.items[0]` | (new) | **everything included.** shopping, music, slides and the rest. no tiers, no add-ons. |
| `PRICING.items[1]` | (new) | **no api keys.** nothing to find, copy or paste. |
| `PRICING.items[2]` | (new) | **runs on your mac.** hold fn and shift, say “hey zoya”, or press ⌘k in zoya's window and type. |
| `PRICING.items[3]` | (new) | **private.** what you say is transcribed right on your mac. |
| call to action | (new) | the existing waitlist form (`WAITLIST.*`, unchanged): your email · join the waitlist · mac only. |

## FAQ

| Key | Old | New |
| --- | --- | --- |
| `FAQ.items` "who is zoya for?" | (new) | anyone with a mac. and if you can't see the screen, zoya is fully built for you too. |
| `FAQ.items` "how much does it cost?" | (new) | $20 a month, with everything included. you don't need an api key. |
| `FAQ.items` "when can i get it?" | today. it's open source. follow the steps in get zoya, or join the waitlist to hear when installing gets even easier. | soon. join the waitlist, and we'll email you when zoya is ready. |

## Unchanged on purpose

Skip link, the hello window and its audio, the demo, what zoya does, you're in charge, the waitlist
form strings, the other faq answers, and the footer. `lib/copy.test.ts` guards the rules above: no
"ai-powered", "seamless" or "revolutionary", no em dashes, the hero leads with fn and shift, and one
$20 plan with the waitlist as the only call to action.
