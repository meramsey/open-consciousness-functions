"""Exact predecessor projection for the user-authorized HPLUS-015 migration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .utils import OCFError

LEDGER = "function-content/editorial/session-pacing-successor-015.json"
LEDGER_SHA256 = "b1f62426ec59f1b09a41528cf9f23ff7cd2927a2fba410b3a62c87e4850a8091"


def predecessor(root: Path, name: str, text: str) -> str:
    path = root / LEDGER
    if not path.is_file():
        return text
    raw = path.read_text(encoding="utf-8")
    if hashlib.sha256(raw.encode()).hexdigest() != LEDGER_SHA256:
        raise OCFError("immutable session-pacing successor record drift")
    ledger = json.loads(raw)
    if ledger["id"] != "OCF-SESSION-PACING-SUCCESSOR-015":
        raise OCFError("session-pacing successor identity drift")
    row = ledger["files"].get(name)
    if row is None:
        return text
    if hashlib.sha256(row["before"].encode()).hexdigest() != row["before_sha256"]:
        raise OCFError("session-pacing predecessor drift: " + name)
    if text == row["before"]:
        return text
    if hashlib.sha256(text.encode()).hexdigest() != row["after_sha256"]:
        raise OCFError("session-pacing successor source drift: " + name)
    return row["before"]
