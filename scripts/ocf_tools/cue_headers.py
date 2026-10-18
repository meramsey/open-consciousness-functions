"""Generated plain-editor cue previews, separate from editable cue authority."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from .cue_templates import CueTemplateError, is_active, value
from .locale import LocaleCatalog, LocalizationError
from .models import function_from_dict
from .paths import REPO_ROOT
from .utils import OCFError

START = "# BEGIN GENERATED CUE PREVIEW\n"
END = "# END GENERATED CUE PREVIEW\n"
LEDGER = "function-content/editorial/cue-headers-001.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_header(text: str) -> tuple[str, str]:
    """Only a single leading marked comment block may be replaced."""
    normalized = text.replace("\r\n", "\n")
    if START not in normalized and END not in normalized:
        return "", text
    if (
        not normalized.startswith(START)
        or normalized.count(START) != 1
        or normalized.count(END) != 1
    ):
        raise OCFError("malformed/duplicate generated cue preview markers")
    index = normalized.index(END) + len(END)
    header = normalized[:index]
    if any(not line.startswith("#") for line in header.splitlines()):
        raise OCFError("cue preview block must contain only comments")
    # Slice the original bytes' character positions, never a reconstructed
    # newline style: mixed LF/CRLF comments must not consume authored content.
    offset = 0
    for line in text.splitlines(keepends=True):
        offset += len(line)
        if line.replace("\r\n", "\n") == END:
            return text[:offset], text[offset:]
    raise OCFError("generated cue preview end marker is not on its own line")


def header(owner, locale: str, catalog: LocaleCatalog, root: Path) -> str:
    title, _ = value(owner, "function.title", locale, catalog)
    lines = [
        START.rstrip(),
        "# Generated preview, NOT editable authority. Refresh/check: python -m ocf_tools.cue_headers",
        "# "
        + json.dumps({"function": owner.id, "title": title, "locale": locale}, ensure_ascii=False),
        "# English authority: " + owner.path.relative_to(root).as_posix(),
    ]
    for command in owner.command_records:
        if not is_active(command) or command.role == "legacy-alias":
            continue
        symbol = "cue.id." + command.id
        try:
            spoken, provenance = value(owner, symbol, locale, catalog)
        except (CueTemplateError, LocalizationError) as exc:
            lines.append(
                "# "
                + json.dumps(
                    {"command": command.id, "binding_status": "unavailable", "reason": str(exc)},
                    ensure_ascii=False,
                )
            )
            continue
        lines.append(
            "# "
            + json.dumps(
                {
                    "symbol": "cue.primary" if command.designation == "primary" else symbol,
                    "command": command.id,
                    "role": command.role,
                    "display": provenance.get("display_cue"),
                    "spoken": spoken,
                    "locale_definition": provenance.get("spoken_cue_key"),
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + "\n" + END


def plans(root: Path = REPO_ROOT) -> dict[str, str]:
    records = [
        function_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")), path)
        for path in sorted((root / "functions").rglob("*.yaml"))
    ]
    catalog = LocaleCatalog(root / "locales", function_records=lambda: records)
    result = {}
    for owner in records:
        # Existing complete source-English files only. Translated previews use
        # header() with their reviewed locale; there is no English fallback.
        path = root / "locales/en-US" / f"hplus-{owner.id}.yaml"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            text = stream.read()
        _, body = split_header(text)
        preview = header(owner, "en-US", catalog, root)
        if "\r\n" in text:
            preview = preview.replace("\n", "\r\n")
        result[path.relative_to(root).as_posix()] = preview + body
    return result


def check(root: Path = REPO_ROOT) -> list[str]:
    return [
        name
        for name, expected in plans(root).items()
        if (root / name).read_bytes() != expected.encode("utf-8")
    ]


def predecessor(root: Path, name: str, text: str) -> str:
    """Replay the exact checked comment-only successor before older ledgers."""
    from .cue_completion import predecessor as before_completion

    text = before_completion(root, name, text)
    path = root / LEDGER
    if not path.is_file():
        return text
    record = json.loads(path.read_text(encoding="utf-8"))
    generated = record.get("plans", {}).get(name)
    if generated is not None:
        if not name.startswith("audio/session-plans/en-US/"):
            raise OCFError("cue header plan outside authorized scope")
        old = generated["predecessor"]
        if sha(text) != generated["after_sha256"] or sha(old) != generated["before_sha256"]:
            raise OCFError("cue header plan successor drift: " + name)
        previous, current = json.loads(old), json.loads(text)
        if name.endswith("/_shared.json"):
            for key in ("defaults_lock", "defaults_sha256"):
                previous[key] = current[key]
        else:
            previous["defaults"]["sha256"] = current["defaults"]["sha256"]
        if previous != current:
            raise OCFError("cue header successor changed session behavior: " + name)
        return old
    row = record["files"].get(name)
    if row is None:
        return text
    prefix, body = split_header(text)
    if (
        not prefix
        or sha(text) != row["after_sha256"]
        or sha(body) != row["before_sha256"]
        or body != row["predecessor"]
    ):
        raise OCFError("cue preview successor source drift: " + name)
    return body


def verify(root: Path = REPO_ROOT) -> list[str]:
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    from .cue_completion import verify as verify_completion
    from .cue_migration import contained
    from .validators import _load_schema, validate_against_schema

    path = root / LEDGER
    if not path.is_file():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_against_schema(record, _load_schema("cue-header-successor.schema.json"))
    if errors:
        return errors
    for name in record["files"]:
        predecessor(root, name, contained(root, name).read_text(encoding="utf-8"))
    for name in record.get("plans", {}):
        predecessor(root, name, contained(root, name).read_text(encoding="utf-8"))
    if text_fingerprints(narration_texts(root)) != record["resolved_text_sha256"]:
        errors.append("cue header successor changed resolved narration")
    old_raw = contained(root, record["previous_defaults_lock"]).read_text(encoding="utf-8")
    old = json.loads(old_raw)
    new = json.loads(contained(root, record["defaults_lock"]).read_text(encoding="utf-8"))
    if sha(old_raw) != record["previous_defaults_sha256"]:
        errors.append("cue header predecessor lock changed")
    if old["profiles"] != new["profiles"] or old["files"].keys() != new["files"].keys():
        errors.append("cue header engineering profiles/dependencies changed")
    for name, checksum in old["files"].items():
        expected = record["files"].get(name, {}).get("after_sha256", checksum)
        if new["files"].get(name) != expected:
            errors.append("cue header lock changed beyond comments: " + name)
    errors.extend(verify_completion(root))
    errors.extend("stale cue preview: " + name for name in check(root))
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="refresh comments, preserving authored bytes"
    )
    args = parser.parse_args(argv)
    planned = plans()
    if args.write:
        # Deliberate frozen-source changes need successor evidence. Never
        # silently rewrite an existing record or baseline while refreshing.
        if not (REPO_ROOT / LEDGER).is_file():
            raise OCFError("protected source preview requires an explicit successor ledger first")
        record = json.loads((REPO_ROOT / LEDGER).read_text(encoding="utf-8"))
        if set(planned) - record["files"].keys():
            raise OCFError("every preview write requires an explicit successor file record")
        for name, text in planned.items():
            predecessor(REPO_ROOT, name, text.replace("\r\n", "\n"))
        for name, text in planned.items():
            (REPO_ROOT / name).write_bytes(text.encode("utf-8"))
    stale = check()
    print("\n".join(stale) if stale else "Generated cue previews: PASS")
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
