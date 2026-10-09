"""The held-out scenario set for the motion harness (S2-Feel): fresh content and orderings the dev
set in motion_harness.py never ran, kept out of tuning and run once to check the fixes hold.

    uv run python scripts/motion_harness.py --set held-out --out design/s2/held-out/light
"""

from __future__ import annotations

from motion_harness import LONG_S, RING, Step

from zoya import events

TRANSFER = "I'm about to transfer ₹12,500 to Kavya Iyer's HDFC account for the October rent."
GIFT = "I'm about to order a Kannada–English picture dictionary for Aarav, total ₹649."
SAID_LONG = (
    "Your sister's flight from Pune lands at 9:55 tonight at Terminal 2, about forty minutes "
    "late, so leaving home at 9:15 still gets you there before she reaches the baggage belt."
)
SAID_HINDI = "ठीक है, मैंने शनिवार सुबह दस बजे की योगा क्लास आपके कैलेंडर में जोड़ दी है।"
ASK_HINDI = "माँ को व्हाट्सऐप पर बता दो कि मैं सात बजे तक घर पहुँच जाऊँगा"


def _ear(kind: str) -> events.EarconEvent:
    return events.EarconEvent(kind)  # type: ignore[arg-type]


def _ask(task: str, summary: str, decision: str = "pending") -> events.ConfirmationEvent:
    return events.ConfirmationEvent(task, summary, decision)  # type: ignore[arg-type]


def _task(task: str, status: str) -> events.TaskEvent:
    return events.TaskEvent(task, status, "pay the rent", "orchestrator")  # type: ignore[arg-type]


def _user(text: str) -> events.OverlayEvent:
    return events.OverlayEvent(text, "listening", {"role": "user"})


HELD_OUT = (
    Step("start idle", (_task("h0", "done"),), "exit", LONG_S, frequent=False),
    Step("key-down → listening", (_ear("listening"),), sound="listening"),
    Step("you said, Hindi", (_user(ASK_HINDI),)),
    Step("key-up → heard + working", (_ear("heard"), _ear("working")), sound="heard"),
    Step("step update, same state", (events.OverlayEvent("", "working", {"tool": "web_search"}),)),
    Step("step update again", (events.OverlayEvent("", "working", {"tool": "read_screen_text"}),)),
    Step("speaking, long", (events.NarrateEvent(SAID_LONG),), settle_s=LONG_S),
    Step("asking while speaking", (_ask("h1", TRANSFER),), settle_s=LONG_S),
    Step("warning earcon", (_ear("warning"),), "beat", sound="warning"),
    Step(
        "cancel by timeout",
        (_ask("h1", TRANSFER, "timeout"), _ear("cancel")),
        "exit",
        sound="cancel",
    ),
    Step("late ask after timeout", (_ask("h1", TRANSFER),), "door"),
    Step("key-down → listening (2)", (_ear("listening"),), sound="listening"),
    Step("key-up → heard (2)", (_ear("heard"), _ear("working")), sound="heard"),
    Step("aim and act", (events.OverlayEvent("", "working", {"ring": RING}),), "ring", LONG_S),
    Step("asking (gift)", (_ask("h2", GIFT),), settle_s=LONG_S),
    Step("duplicate ask while asking", (_ask("h2", GIFT),), "door"),
    Step("confirmed", (_ask("h2", GIFT, "confirm"),)),
    Step("purchase earcon", (_ear("purchase"),), "beat", sound="purchase"),
    Step("task cancelled", (_task("h2", "cancelled"),), "exit"),
    Step("late ask after task ended", (_ask("h2", GIFT),), "door"),
    Step("speaking, Hindi", (events.NarrateEvent(SAID_HINDI),)),
    Step("failed", (_task("h3", "failed"),), sound=""),
    Step("idle", (_task("h3", "done"),), "exit", LONG_S),
)
