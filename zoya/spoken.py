"""Words as Whisper hears them, and Zoya's name among them (§7.1). Shared by the voice loop, the
stop parser and the router, so none of them imports another to read a transcript."""

from __future__ import annotations

import re
import unicodedata

# Lenient "Zoya" (§7.1): zoya, zoia, zooeya, zoa, zoea, zoyah — not soya, sonia, zoe.
NAME = re.compile(r"^z(?:oo?e?y|oi|oe|o)ah?$")
# large-v3-turbo writes Hinglish in Devanagari (D42): "ज़ोया, स्पॉटिफ़ाई खोल दो".
DEVANAGARI_NAME = re.compile(r"^(?:ज़|ज़|ज)ोया$")
WORD = re.compile(r"[a-z]+|\d+|[\u0900-\u097F]+")  # digits: "Zoya 5000" answers a budget question
LATIN_ACCENT = re.compile(r"[\u0300-\u036f]")


def words(text: str) -> list[str]:
    # Strip Latin accents only ("Zoëa" → "zoea"); Devanagari marks are letters, keep them.
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not LATIN_ACCENT.match(c))
    return WORD.findall(plain.lower())


def is_name(word: str) -> bool:
    return bool(NAME.match(word) or DEVANAGARI_NAME.match(word))
