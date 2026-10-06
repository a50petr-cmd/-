from __future__ import annotations

import re

_CMD_AT_BOT = re.compile(r"^(/[\w]+)(?:@[\w]+)?(?:\s+(.*))?$", re.DOTALL)


def parse_bot_command(text: str) -> tuple[str | None, str]:
    """Return (command like '/search', args) or (None, '') if not a command."""
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None, raw
    match = _CMD_AT_BOT.match(raw)
    if not match:
        cmd = raw.split()[0].split("@")[0]
        rest = raw[len(raw.split()[0]) :].strip()
        return cmd.lower(), rest
    cmd, args = match.group(1).lower(), (match.group(2) or "").strip()
    return cmd, args
