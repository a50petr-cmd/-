from __future__ import annotations

import html
import re

_NBSP = re.compile(r"&nbsp;|&#160;|\xa0", re.IGNORECASE)


def clean_product_text(text: str) -> str:
    if not text:
        return text
    out = html.unescape(text)
    out = _NBSP.sub(" ", out)
    return " ".join(out.split())
