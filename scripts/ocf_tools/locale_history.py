"""Exact predecessor projection for localized resource structural migrations."""

import hashlib
import json
from pathlib import Path

from .utils import OCFError

LEDGER = "function-content/editorial/localized-resource-migration-001.json"
LEDGER_SHA256 = "530754a081cd72fbedb76ed3f7ccf5b2f8ba3ce4330947bd39c4ec6dae4a98cf"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def predecessor(root: Path, name: str, text: str) -> str:
    path = root / LEDGER
    if not path.is_file():
        return text
    raw = path.read_text(encoding="utf-8")
    if _sha(raw) != LEDGER_SHA256:
        raise OCFError("immutable localized resource migration ledger drift")
    data = json.loads(raw)
    row = data["files"].get(name)
    if row is None:
        return text
    if _sha(row["before"]) != row["before_sha256"]:
        raise OCFError("localized resource predecessor drift: " + name)
    if text == row["before"]:
        return text
    if _sha(text) != row["after_sha256"]:
        raise OCFError("localized resource successor source drift: " + name)
    for relative, checksum in data["active_resources"].items():
        active = (root / relative).resolve()
        if not active.is_relative_to(root.resolve()) or not active.is_file():
            raise OCFError("missing or unsafe localized successor: " + relative)
        if hashlib.sha256(active.read_bytes()).hexdigest() != checksum:
            raise OCFError("localized resource active source drift: " + relative)
    return row["before"]
