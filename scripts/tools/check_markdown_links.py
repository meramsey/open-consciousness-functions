"""Check internal Markdown links in the repository.

Resolves plain `[text](target)` links relative to each document and reports any
target that does not exist. External URLs, anchors, mailto:, and protocol-less
references are ignored. Used by CI (`make lint`-adjacent) to keep links from
rotting.

Exit code: 0 when all internal targets exist, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Directories we deliberately do not scan as link sources.

IGNORED_SCHEMES = ("http://", "https://", "mailto:", "tel:", "#", "?")


def iter_markdown() -> list[Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(REPO_ROOT).parts)
    )


def check_file(path: Path) -> list[str]:
    report: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.append(f"{path}: cannot read: {exc}")
        return report
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if any(target.startswith(prefix) for prefix in IGNORED_SCHEMES):
            continue
        # Strip trailing anchor (#section) and attempt resolution.
        clean = target.split("#")[0].strip()
        if not clean:
            continue
        resolved = (path.parent / clean).resolve()
        if not resolved.exists():
            report.append(f"{path}: broken internal link -> {target}")
    return report


def main() -> int:
    failures: list[str] = []
    for path in iter_markdown():
        failures.extend(check_file(path))
    if failures:
        for message in failures:
            print(message, file=sys.stderr)
        print(f"\n{len(failures)} broken internal link(s).", file=sys.stderr)
        return 1
    print("Markdown internal links: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
