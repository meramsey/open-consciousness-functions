"""Generated plain-editor cue previews, separate from editable cue authority."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .cue_templates import is_active, value
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError

START = "# BEGIN GENERATED CUE PREVIEW\n"
END = "# END GENERATED CUE PREVIEW\n"


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


def header(owner, locale: str, catalog: LocaleCatalog, root: Path, *, draft_review=False) -> str:
    title = (
        owner.canonical_name
        if draft_review and locale == "en-US"
        else value(owner, "function.title", locale, catalog)[0]
    )
    lines = [
        START.rstrip(),
        "# Generated preview, NOT editable authority. Refresh/check: python -m ocf_tools.cue_headers",
        "# "
        + json.dumps({"function": owner.id, "title": title, "locale": locale}, ensure_ascii=False),
        "# English authority: " + owner.path.relative_to(root).as_posix(),
    ]
    if draft_review:
        localized = catalog.require(locale).localized_functions.get(owner.id, {})
        approval = localized.get("record_metadata", {}).get("editorial_approval")
        lines.append(
            "# Editorial status: approved narration is stored in the canonical locale resource; listening/release pending."
            if approval
            else "# Editorial status: no embedded approval; this preview does not authorize promotion."
        )
        lines.append("# Entire view is read-only; edit only the canonical locale resource.")
    for command in owner.command_records:
        if not is_active(command) or command.role == "legacy-alias":
            continue
        symbol = "cue.id." + command.id
        try:
            spoken, provenance = value(owner, symbol, locale, catalog, draft_review=draft_review)
        except OCFError as exc:
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
    """Canonical locale resources already contain cues; no source snapshots exist."""
    from .function_catalog import resources

    for path, data in resources(root):
        text = path.read_text(encoding="utf-8")
        if text.startswith(START) or data.get("domain") != "function":
            raise OCFError(
                "canonical function resource contains an obsolete cue preview: " + path.name
            )
    return {}


def draft_plans(root: Path = REPO_ROOT) -> dict[str, str]:
    """There are no separate editable candidate or working function copies."""
    return {}


def check(root: Path = REPO_ROOT) -> list[str]:
    return [
        name
        for name, expected in plans(root).items()
        if (root / name).read_bytes() != expected.encode("utf-8")
    ]


def predecessor(root: Path, name: str, text: str) -> str:
    """Current cue resources are authoritative; no predecessor projection exists."""
    return text


def verify(root: Path = REPO_ROOT) -> list[str]:
    return check(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="retired; canonical resources need no cue headers"
    )
    args = parser.parse_args(argv)
    if args.write:
        raise OCFError(
            "cue-header generation is retired; edit the canonical locale function resource"
        )
    stale = check()
    print("\n".join(stale) if stale else "Generated cue previews: PASS")
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
