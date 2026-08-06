"""Rewrite gate for SquareHotSource.

Context: Binance Square's trending feed is predominantly English and the
generator writes Chinese, so most rewrites are EN->CN translation plus
re-framing. A faithful translation is already a meaningful rewrite for a
different-language audience — it does not need to be blocked, and trying
to compare EN vs CN text character-by-character is meaningless (the ratio
is always near zero, so the gate fires on nothing).

Policy:
- If original and rewrite are in different scripts (CJK vs Latin), treat
  the language shift itself as sufficient transformation and pass.
- If both are in the same script (CN->CN or EN->EN synonym swap), use
  SequenceMatcher on stripped text and reject when ratio > threshold.
- Empty/short inputs pass (not enough signal to block on).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_CJK = re.compile(r"[一-鿿぀-ヿ가-힯]")


def _script(text: str) -> str:
    return "cjk" if _CJK.search(text or "") else "latin"


def is_too_similar(original: str, rewritten: str, threshold: float) -> bool:
    """Return True when rewrite is too close to original.

    threshold is a SequenceMatcher ratio in [0, 1]; higher = more lenient.
    Cross-script pairs always return False because the language shift
    itself is a sufficient rewrite.
    """
    if not original or not rewritten:
        return False
    if _script(original) != _script(rewritten):
        return False
    ratio = SequenceMatcher(
        None, original.strip(), rewritten.strip()
    ).ratio()
    return ratio > threshold
