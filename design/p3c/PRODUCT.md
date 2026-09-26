# Product

Source: docs/phases/prod-3c-ui.md (the owner's brief), D105, D107, D119. Nothing here is new; it is the brief restated for the design skills.

## Register

product

## Users

Zoya is a voice agent that runs a Mac for people who cannot see the screen. Most users are blind and never look at it. Three groups do:

- low-vision users, who need large, high-contrast state and captions;
- the sighted family member who installs Zoya, and often pays for it;
- the owner's screenshots and the website.

Every surface must be beautiful to a sighted eye and fully usable with VoiceOver, keyboard only. One is never traded for the other.

## Product Purpose

- The pill answers "what is Zoya doing right now?" at a glance: idle, listening, thinking, speaking, waiting for "confirm" (the safety gate, most prominent of all) and error. Stop is always one click away. Captions of what she heard and what she says, larger with a larger-text setting.
- The Hub answers "what has Zoya done for me, and is everything okay?": Today, History, Memory (each memory deletable), Plan, Setup, Voice and settings.
- The app icon makes Zoya a real product in the Dock, Finder and System Settings.

## Brand Personality

Calm, capable, dignified. Copy in a Steve Jobs keynote voice: short, declarative, benefits over mechanics, dignity, never pity. No "AI-powered", no "seamless", no invented numbers. Delight is "pleasing to the eyes", in the spirit of heyclicky.com: clean, light, crafted.

## Anti-references

- Violet or purple anything. Blue gradient orbs. Radial or circular gradients ("the same ChatGPT ingredient").
- Left/right split heroes. Hero and empty states are centered; a Hub sidebar is fine.
- Fake content: fabricated stats, streaks or word counts (Wispr Flow's Hub leads with these; Zoya does not), sample transcripts presented as real.
- A copy of Wispr Flow: inspiration only, no names, assets or layouts one to one.

## Design Principles

1. State before style: every state reads without motion, by shape, colour and a word.
2. The confirmation is the loudest thing on screen. The pill shows it; only the voice answers it.
3. Light first; dark follows the system.
4. One brand with the site: palette built from site/app/globals.css tokens and Zoya blue.
5. True and kind empty states.

## Accessibility

WCAG 2.2 AA minimum, AAA for captions. VoiceOver and keyboard reach everything. Honour Reduce Motion (fades only), Reduce Transparency (opaque) and Increase Contrast. A larger-text setting scales captions and the Hub.
