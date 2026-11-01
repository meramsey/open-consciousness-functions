"""Historical predecessor view for the immutable shared-session successor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .paths import REPO_ROOT
from .utils import OCFError

LEDGER = "function-content/editorial/shared-session-successor-013.json"
LEDGER_SHA256 = "569a369a6ba51cd68ad30b428f778f5e95eaae725f038eccb6932b0ff9d82add"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(root: Path = REPO_ROOT) -> dict | None:
    path = root / LEDGER
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    if _sha(raw) != LEDGER_SHA256:
        raise OCFError("immutable shared-session successor record drift")
    data = json.loads(raw)
    if data.get("id") != "OCF-SHARED-SESSION-SUCCESSOR-013":
        raise OCFError("shared-session successor identity drift")
    return data


def predecessor(root: Path, name: str, text: str) -> str:
    from .locale_history import predecessor as before_localized_resources
    from .session_pacing_successor import predecessor as before_pacing

    ledger = record(root)
    row = ledger["files"].get(name) if ledger else None
    if row is not None and _sha(text) == row["before_sha256"] and text == row["before"]:
        return text
    text = before_localized_resources(root, name, text)
    text = before_pacing(root, name, text)
    if row is None:
        return text
    if _sha(text) != row["after_sha256"]:
        raise OCFError("shared-session successor source drift: " + name)
    if _sha(row["before"]) != row["before_sha256"]:
        raise OCFError("shared-session successor predecessor drift: " + name)
    return row["before"]
