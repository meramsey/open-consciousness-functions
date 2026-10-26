"""Git index boundary check; private reference audio must remain local-only."""

import subprocess
from pathlib import Path

import pytest
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration

FORBIDDEN_PATH_PARTS = {
    ".ocf-work/renders/amy-reference-v4-",
    "F10 V4 Volume Adjusted.flac",
    "F11 V4.flac",
    "references/HumanPlusTranscripts/",
}


def _git_paths(*args):
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True)
    return [
        Path(item.decode("utf-8", errors="surrogateescape"))
        for item in result.stdout.split(b"\0")
        if item
    ]


def test_private_reference_sources_and_renders_are_not_tracked_or_staged():
    tracked = [path.as_posix() for path in _git_paths("ls-files", "--cached", "-z")]
    staged = [path.as_posix() for path in _git_paths("diff", "--cached", "--name-only", "-z")]
    offenders = [
        path
        for path in (*tracked, *staged)
        if any(marker in path for marker in FORBIDDEN_PATH_PARTS)
    ]
    assert not offenders, "private OCF references/renders entered Git: " + ", ".join(offenders)
