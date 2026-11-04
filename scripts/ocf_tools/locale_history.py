"""Exact predecessor projection for localized resource structural migrations."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import yaml

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
RESOURCE_MAP = "function-content/editorial/historical-resource-map-006.json"
RESOURCE_MAP_SHA256 = "23633eae6aa72898c135906782d694dfb011957ffd195396fbba8641f249f217"
FUNCTION_AUTHORITY = "function-content/editorial/function-authority-migration-007.json"
FUNCTION_AUTHORITY_SHA256 = "c149699f9a08d32a41e9b9ea74a7d3bd47562471b5b65fc920c104394f05e09a"


def _safe_path(root: Path, name: str) -> Path:
    """Use portable relative logical identities and reject every symlink component."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise OCFError("unsafe historical logical path")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise OCFError("unsafe historical logical path: " + name)
    root = root.resolve()
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise OCFError("symlink in historical logical path: " + name)
    if not path.resolve().is_relative_to(root):
        raise OCFError("historical path escapes repository: " + name)
    return path


def _record(root: Path, name: str, expected: str) -> dict | None:
    path = _safe_path(root, name)
    if not path.is_file():
        return None
    stat = path.stat()
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return _consolidation_record(path, signature, expected)


def _archive_text(root: Path, name: str, checksum: str) -> str:
    if not name.startswith(
        (
            "function-content/editorial/historical-locales/",
            "function-content/editorial/historical-functions/",
        )
    ):
        raise OCFError("unsafe historical locale archive: " + name)
    path = _safe_path(root, name)
    if not path.is_file():
        raise OCFError("missing historical locale archive: " + name)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise OCFError("historical locale archive drift: " + name)
    return raw.decode("utf-8")  # No universal-newline conversion: CRLF is identity.


def historical_resources(root: Path) -> dict:
    """Pinned retirement identities, not arbitrary absent paths from older ledgers."""
    signatures = []
    for name in (RESOURCE_MAP, FILENAMES, RETIREMENT):
        path = _safe_path(root, name)
        stat = path.stat() if path.is_file() else None
        signatures.append(
            None
            if stat is None
            else (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        )
    return deepcopy(
        _historical_resources(
            root.resolve(),
            tuple(signatures),
            RESOURCE_MAP_SHA256,
            FILENAMES_SHA256,
            RETIREMENT_SHA256,
        )
    )


@lru_cache(maxsize=8)
def _historical_resources(root, signatures, map_sha, filenames_sha, retirement_sha):
    """Cache map validation only; archive bytes are verified on every read."""
    data = _record(root, RESOURCE_MAP, map_sha)
    if data is None:
        return {}
    archives = set()
    for name, row in data["files"].items():
        _safe_path(root, name)
        if row["archive"] in archives:
            raise OCFError("historical archive identity collision")
        archives.add(row["archive"])
        expected = {FILENAMES: filenames_sha, RETIREMENT: retirement_sha}.get(row["ledger"])
        if expected is None:
            raise OCFError("unknown historical resource ledger")
        ledger = _record(root, row["ledger"], expected)
        prior = (ledger or {}).get("files", {}).get(name)
        if not prior or (prior["archive"], prior["before_sha256"], prior["after_sha256"]) != (
            row["archive"],
            row["sha256"],
            row["stub_sha256"],
        ):
            raise OCFError("historical resource map/ledger identity mismatch: " + name)
    return data["files"]


def read_logical(root: Path, name: str, *, preserve_newlines: bool = False) -> str:
    """Read a physical resource or verified virtual structural predecessor.

    This does not run earlier semantic projections: each caller retains its
    chosen replay depth. Present modified stubs fail closed, never hide drift.
    Active LocaleCatalog resources are deliberately NOT loaded through here.
    Physical files retain the legacy text-reader newline behavior unless a
    byte-fingerprint caller explicitly opts out; virtual archives are ALWAYS
    returned byte-exact, including CRLF.
    """
    path = _safe_path(root, name)
    function = historical_function_resources(root).get(name)
    if function is not None:
        if path.exists() and (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != function["sha256"]
        ):
            raise OCFError("historical function successor source drift: " + name)
        return _archive_text(root, function["archive"], function["sha256"])
    row = historical_resources(root).get(name)
    if row is not None:
        if path.exists() and (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["stub_sha256"]
        ):
            raise OCFError("historical locale successor source drift: " + name)
        return _archive_text(root, row["archive"], row["sha256"])
    if not path.is_file():
        raise OCFError(
            "missing or unsafe localized successor (unknown historical logical resource): " + name
        )
    return (
        path.read_bytes().decode("utf-8") if preserve_newlines else path.read_text(encoding="utf-8")
    )


def historical_function_resources(root: Path) -> dict:
    path = _safe_path(root, FUNCTION_AUTHORITY)
    stat = path.stat() if path.is_file() else None
    signature = (
        None
        if stat is None
        else (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    )
    return deepcopy(_function_archive_map(root.resolve(), signature, FUNCTION_AUTHORITY_SHA256))


@lru_cache(maxsize=8)
def _function_archive_map(root, signature, expected):
    data = _record(root, FUNCTION_AUTHORITY, expected)
    rows = (data or {}).get("files", {})
    archives = set()
    for name, row in rows.items():
        _safe_path(root, name)
        if not name.startswith("functions/") or not row["archive"].startswith(
            "function-content/editorial/historical-functions/007/"
        ):
            raise OCFError("invalid historical function identity")
        if row["archive"] in archives:
            raise OCFError("historical function archive identity collision")
        archives.add(row["archive"])
    return rows


def _before_function_authority(root: Path, name: str, text: str) -> str:
    data = _record(root, FUNCTION_AUTHORITY, FUNCTION_AUTHORITY_SHA256)
    row = (data or {}).get("locale_files", {}).get(name)
    if row is None:
        return text
    before = _archive_text(root, row["archive"], row["before_sha256"])
    if _sha(text) == row["after_sha256"]:
        return before
    if text == before or _known_predecessor(root, name, text):
        return text
    for ledger, expected in ((FILENAMES, FILENAMES_SHA256), (RETIREMENT, RETIREMENT_SHA256)):
        prior = (_record(root, ledger, expected) or {}).get("files", {}).get(name)
        if prior and _sha(text) == prior["before_sha256"]:
            return text
    raise OCFError("complete function authority successor drift: " + name)


def _before_discovery(root: Path, name: str, text: str) -> str:
    data = _record(root, RESOURCE_MAP, RESOURCE_MAP_SHA256)
    row = (data or {}).get("discovery_overlays", {}).get(name)
    if row is None:
        return text
    before = _archive_text(root, row["archive"], row["sha256"])
    if _known_predecessor(root, name, text):
        return text
    for ledger, expected in ((FILENAMES, FILENAMES_SHA256), (RETIREMENT, RETIREMENT_SHA256)):
        prior = (_record(root, ledger, expected) or {}).get("files", {}).get(name)
        if prior and _sha(text) == prior["before_sha256"]:
            return text

    def protected(raw):
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise OCFError("invalid historical discovery successor YAML") from error
        if not isinstance(value, dict) or not isinstance(value.get("relationships"), dict):
            raise OCFError("invalid historical discovery successor")
        for field in ("tags", "common_uses"):
            value.pop(field, None)
        value["relationships"].pop("proposals", None)
        return value

    if protected(text) != protected(before):
        raise OCFError("historical discovery successor protected source drift: " + name)
    return before


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
        active_text = before_structural(
            root, relative, read_logical(root, relative, preserve_newlines=True)
        )
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
    text = _before_function_authority(root, name, text)
    text = _before_discovery(root, name, text)
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
