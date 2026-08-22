"""Resolve which crop a free-text question is about.

This exists to close a specific hole. The guardrail is "a Cotton question may
only be answered from Cotton documents", and explain mode gets that for free
because the caller passes `crop_id`. Ask mode had no crop at all - it retrieved
with `crop_id=None`, so a Cotton question could be answered from Tomato
chunks. Enforcing the rule requires knowing the crop, and the only place the
crop appears in ask mode is the question text.

Matching is deliberately dumb - a word list, not a model:

* The farmer-facing UI runs in English, Hindi and Marathi, so the aliases carry
  the names people actually type (kapas / कापूस, kanda / कांदा) rather than only
  the English row in `crops`.
* Word-boundary matching, so "Maize" is not found inside a longer word.
* No fuzzy matching. A near-miss that silently resolves to the wrong crop is
  the exact failure this module is here to prevent; not resolving is safe,
  because a question with no crop is answered from crop-agnostic sources only.

Two crops in one question is reported as two, and the caller refuses rather
than picking one - answering "compare Cotton and Soybean" from one crop's
documents would break the rule while looking like it worked.
"""

from __future__ import annotations

import re

from psycopg import Cursor

# Keyed by the `crops.name` value, so a new crop row without an entry here
# still matches on its own English name.
#
# Two omissions are deliberate: bare "gram" for Chickpea (it collides with the
# unit - "500 gram" is not a crop mention) and bare "us" for Sugarcane (Marathi
# ऊस transliterates to a English stopword). Both would fire constantly.
ALIASES: dict[str, tuple[str, ...]] = {
    "Cotton": ("kapas", "कपास", "कापूस"),
    "Soybean": ("soya", "soyabean", "soya bean", "सोयाबीन"),
    "Maize": ("corn", "makka", "makai", "मक्का", "मका"),
    "Wheat": ("gehu", "gehun", "गेहूं", "गहू"),
    "Rice": ("paddy", "dhan", "chawal", "धान", "चावल", "भात", "तांदूळ"),
    "Onion": ("pyaz", "pyaaz", "kanda", "प्याज", "कांदा"),
    "Tomato": ("tamatar", "टमाटर", "टोमॅटो"),
    "Chilli": ("chili", "chile", "chilly", "mirch", "mirchi", "मिर्च", "मिरची"),
    "Potato": ("aloo", "alu", "batata", "आलू", "बटाटा"),
    "Sugarcane": ("ganna", "sugar cane", "गन्ना", "ऊस"),
    "Chickpea": ("chana", "bengal gram", "chick pea", "चना", "हरभरा"),
    "Grapes": ("grape", "angoor", "draksha", "अंगूर", "द्राक्षे"),
    "Groundnut": ("peanut", "ground nut", "moongphali", "mungfali", "bhuimug", "मूंगफली", "भुईमूग"),
}


# `\b` cannot be used here. Python's `\w` excludes Unicode combining marks, and
# Devanagari vowel signs are combining marks - so in "कांदा" the trailing ा is a
# non-word character, `\bकांदा\b` never matches, and every Hindi/Marathi alias
# silently fails to be found. Spelling the word character class out, with the
# Devanagari block included, makes the boundary work in all three languages.
_WORD_CHAR = r"[\wऀ-ॿ]"


def _find(haystack: str, needle: str) -> int | None:
    """Position of `needle` in `haystack` as a whole word, else None."""
    match = re.search(
        rf"(?<!{_WORD_CHAR}){re.escape(needle.lower())}(?!{_WORD_CHAR})",
        haystack,
    )
    return match.start() if match else None


def detect_crops(cur: Cursor, question: str) -> list[dict]:
    """Every crop the question names, in the order they first appear.

    Empty when the question names none - which is a normal outcome ("when
    should I apply urea?"), not an error.
    """
    cur.execute("SELECT id, name FROM crops ORDER BY id")
    crops = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]

    lowered = question.lower()
    found: list[tuple[int, dict]] = []
    for crop in crops:
        terms = (crop["name"], *ALIASES.get(crop["name"], ()))
        positions = [pos for term in terms if (pos := _find(lowered, term)) is not None]
        if positions:
            found.append((min(positions), crop))

    return [crop for _, crop in sorted(found, key=lambda pair: pair[0])]
