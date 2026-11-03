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
RETIREMENT = "function-content/editorial/localized-retirement-004.json"
RETIREMENT_SHA256 = "97236e0165be4fa9f6757d6b6625e2250a1892497f200aff20e8ca64e38ceb81"
FILENAMES = "function-content/editorial/localized-filenames-005.json"
FILENAMES_SHA256 = "ece5435b619e400bd3f2ddeb414ae07d69bd6265e38629cfab0c909dc793c11f"


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
        with active.open(encoding="utf-8", newline="") as stream:
            active_text = before_structural(root, relative, stream.read())
        if _sha(active_text) != checksum:
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
    text = before_structural(root, name, text)
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


def before_structural(root: Path, name: str, text: str) -> str:
    """Reproduce original logical resources from checked immutable archives.

    Small unlisted compatibility stubs contain no editable localized words.
    Active locale manifests never declare those stubs as resources. Archive
    content and the current compatibility/successor bytes both fail closed.
    """
    for ledger_name, expected in ((FILENAMES, FILENAMES_SHA256), (RETIREMENT, RETIREMENT_SHA256)):
        path = root / ledger_name
        if not path.is_file():
            continue
        stat = path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        row = _consolidation_record(path, signature, expected)["files"].get(name)
        if row is None:
            continue
        source_archive = root / row["archive"]
        archive = source_archive.resolve()
        if (
            not archive.is_relative_to(root.resolve())
            or not archive.is_relative_to(
                (root / "function-content/editorial/historical-locales").resolve()
            )
            or source_archive.is_symlink()
        ):
            raise OCFError("unsafe historical locale archive: " + name)
        with archive.open(encoding="utf-8", newline="") as stream:
            before = stream.read()
        if _sha(before) != row["before_sha256"]:
            raise OCFError("historical locale archive drift: " + name)
        if text == before:
            continue
        if _sha(text) != row["after_sha256"]:
            if _known_predecessor(root, name, text):
                continue  # Already projected by an older, independently pinned ledger.
            raise OCFError("historical locale successor source drift: " + name)
        text = before
    return text


def _known_predecessor(root: Path, name: str, text: str) -> bool:
    for ledger_name, expected in (
        (LEDGER, LEDGER_SHA256),
        (CONSOLIDATION, CONSOLIDATION_SHA256),
        (AUTHORITY, AUTHORITY_SHA256),
    ):
        path = root / ledger_name
        if not path.is_file():
            continue
        stat = path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        row = _consolidation_record(path, signature, expected)["files"].get(name)
        if (
            row
            and isinstance(row.get("before"), str)
            and _sha(row["before"]) == row["before_sha256"]
            and text == row["before"]
        ):
            return True
    return False


@lru_cache(maxsize=8)
def _consolidation_record(path: Path, signature: tuple, expected_sha: str) -> dict:
    """Recheck the full ledger on any filesystem identity/change-time change."""
    raw = path.read_text(encoding="utf-8")
    if _sha(raw) != expected_sha:
        raise OCFError("immutable localized consolidation ledger drift")
    return json.loads(raw)
