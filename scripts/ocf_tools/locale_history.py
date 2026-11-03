"""Exact predecessor projection for localized resource structural migrations."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .utils import OCFError

LEDGER = "function-content/editorial/localized-resource-migration-001.json"
LEDGER_SHA256 = "530754a081cd72fbedb76ed3f7ccf5b2f8ba3ce4330947bd39c4ec6dae4a98cf"
CONSOLIDATION = "function-content/editorial/localized-consolidation-002.json"
CONSOLIDATION_SHA256 = "007edf20495c1e43e65200ab3962766dde1c2ff328d4c90a29ee1031eee218bf"
AUTHORITY = "function-content/editorial/localized-authority-003.json"
AUTHORITY_SHA256 = "b3fe1cd421aa10d6a6d9da1134f1110e08a731e201d1d6c126acb815efc88bad"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def predecessor(root: Path, name: str, text: str) -> str:
    text = before_consolidation(root, name, text)
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


def before_consolidation(root: Path, name: str, text: str) -> str:
    text = before_authority(root, name, text)
    path = root / CONSOLIDATION
    if not path.is_file():
        return text
    stat = path.stat()
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    row = _consolidation_record(path, signature, CONSOLIDATION_SHA256)["files"].get(name)
    if row is None:
        return text
    if _sha(row["before"]) != row["before_sha256"]:
        raise OCFError("localized consolidation predecessor drift: " + name)
    if text == row["before"]:
        return text
    if _sha(text) != row["after_sha256"]:
        raise OCFError("localized consolidation successor source drift: " + name)
    return row["before"]


def before_authority(root: Path, name: str, text: str) -> str:
    path = root / AUTHORITY
    if not path.is_file():
        return text
    stat = path.stat()
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    row = _consolidation_record(path, signature, AUTHORITY_SHA256)["files"].get(name)
    if row is None:
        return text
    if _sha(row["before"]) != row["before_sha256"]:
        raise OCFError("localized authority predecessor drift: " + name)
    if text == row["before"]:
        return text
    if _sha(text) != row["after_sha256"]:
        raise OCFError("localized authority successor source drift: " + name)
    return row["before"]


@lru_cache(maxsize=8)
def _consolidation_record(path: Path, signature: tuple, expected_sha: str) -> dict:
    """Recheck the full ledger on any filesystem identity/change-time change."""
    raw = path.read_text(encoding="utf-8")
    if _sha(raw) != expected_sha:
        raise OCFError("immutable localized consolidation ledger drift")
    return json.loads(raw)
