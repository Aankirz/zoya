"""Shared fixture data for the Phase 0 speech benchmarks (STACK §4/§8).

20 commands (English + Hinglish) covering names and amounts, since the pass
bar is "word-correct on names/amounts", not free-form accuracy. Used by both
scripts/record_commands.py (owner records these) and stt_benchmark.py
(grades transcripts against `keywords` — the names/amounts that must survive
transcription).

Each keyword is a list of acceptable surface forms: Whisper normalizes
spoken numbers to digits ("fifteen thousand rupees" -> "Rs. 15,000"), so a
keyword must accept both, or every number gets marked a false miss.
"""

TARGET_COMMANDS: list[dict[str, object]] = [
    {"text": "Remind me to call Priya at six pm", "keywords": [["priya"], ["six", "6"]]},
    {"text": "Message Rohan and tell him I'm running late", "keywords": [["rohan"]]},
    {
        "text": "My order total is two thousand eight hundred and forty seven rupees",
        "keywords": [["two thousand eight hundred and forty seven", "2847", "2,847"]],
    },
    {"text": "Set a reminder for the team meeting at three pm", "keywords": [["three", "3"]]},
    {
        "text": "Send fifteen thousand rupees to Ankit Sharma",
        "keywords": [["fifteen thousand", "15,000", "15000"], ["ankit"]],
    },
    {
        "text": "Aapka Swiggy order pandrah minute mein aa jayega",
        "keywords": [["swiggy", "स्विगी"]],
    },
    {"text": "Spotify khol do aur mera playlist bajao", "keywords": [["spotify"]]},
    {
        "text": "Remind me to pay the electricity bill of twelve hundred rupees",
        "keywords": [["twelve hundred", "1200", "1,200"]],
    },
    {"text": "Message Sneha and ask if she's free tonight", "keywords": [["sneha"]]},
    {
        "text": "Mummy ko message bhejo ki main ghar aa raha hoon",
        "keywords": [["mummy", "मम्मी", "मामी"]],
    },
    {"text": "What's the weather in Bangalore today", "keywords": [["bangalore"]]},
    {"text": "Set a reminder to take medicine at nine pm", "keywords": [["nine", "9"]]},
    {"text": "Search the web for the best biryani near me", "keywords": [["biryani"]]},
    {
        "text": "Open WhatsApp and read my latest message from Karthik",
        "keywords": [["whatsapp"], ["karthik", "kartik"]],
    },
    {"text": "Bataiye mera cart mein kitne items hai", "keywords": [["cart", "कार्ट"]]},
    {"text": "Add discount code FESTIVE and check the new total", "keywords": [["festive"]]},
    {
        "text": "Deliver this order to Sneha Reddy at MG Road",
        "keywords": [["sneha reddy"], ["mg road"]],
    },
    {"text": "Zoya stop, cancel what you're doing", "keywords": [["stop"]]},
    {"text": "Ruk jao Zoya, mujhe kuch aur bolna hai", "keywords": [["zoya", "जोया", "ज़ोया"]]},
    {
        "text": "Confirm the transfer of two thousand rupees to my sister",
        "keywords": [["two thousand", "2000", "2,000"]],
    },
]
