"""Exercise the actual optional-tool Make target, not a copied shell expression."""

import os
import shutil
import subprocess

import pytest
from conftest import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.external_tool]


@pytest.mark.skipif(os.name == "nt", reason="the Makefile lint recipe uses a POSIX shell")
@pytest.mark.parametrize("exit_code", [None, 0, 7])
def test_optional_markdownlint_preserves_installed_tool_failure(tmp_path, exit_code):
    make = shutil.which("make")
    if not make:
        pytest.skip("make is not installed")
    if exit_code is not None:
        executable = tmp_path / "markdownlint"
        executable.write_text(f"#!/bin/sh\necho fixture-markdownlint\nexit {exit_code}\n")
        executable.chmod(0o700)
    env = {**os.environ, "PATH": str(tmp_path)}
    result = subprocess.run(
        [make, "lint-markdown"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if exit_code is None:
        assert result.returncode == 0 and "not installed; skipping" in result.stdout
    else:
        assert (result.returncode == 0) is (exit_code == 0)
        assert "fixture-markdownlint" in result.stdout
        assert "not installed" not in result.stdout
        if exit_code:
            assert "Error 7" in result.stderr
