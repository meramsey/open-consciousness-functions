"""Static container invariants complement, never replace, a real runtime check."""

import os
import subprocess

import pytest
from conftest import REPO_ROOT


def test_image_does_not_copy_reference_or_user_audio():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    ignored = (REPO_ROOT / ".dockerignore").read_text()
    assert "COPY . " not in dockerfile and "COPY references" not in dockerfile
    assert "USER ocf" in dockerfile and "ffmpeg" in dockerfile
    assert "references" in ignored and "audio/rendered" in ignored and "**/*.onnx" in ignored
    assert ".ocf-work" in (REPO_ROOT / ".dockerignore").read_text()
    assert ".ocf-work/" in (REPO_ROOT / ".gitignore").read_text()
    assert "OCF-TPL-SESSION-ATTENTION-001" not in dockerfile
    assert "ENV OCF_WORK_DIR=/home/ocf/.ocf/work" in dockerfile


@pytest.mark.integration
@pytest.mark.external_tool
def test_nonroot_container_workspace():
    image = os.environ.get("OCF_TEST_CONTAINER_IMAGE")
    if not image:
        pytest.skip("set OCF_TEST_CONTAINER_IMAGE after building Dockerfile to run the real smoke")
    smoke = """
import os, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from ocf_tools.paths import (work_root, workspace_temp_directory, cleanup_workspace_temp,
    workspace_run, cleanup_workspace)
from ocf_tools.utils import write_text_atomic
assert os.getuid() == 10001
root = work_root()
assert root == Path('/home/ocf/.ocf/work')
assert not os.access('/opt/ocf', os.W_OK)
scratch = workspace_temp_directory('ocf-container-smoke-')
target = scratch / 'record.txt'
write_text_atomic(target, 'Complete café\\n', overwrite=False)
assert target.read_text(encoding='utf-8') == 'Complete café\\n'
result = workspace_run([sys.executable, '-c', 'print("workspace-ok")'],
    capture_output=True, text=True, timeout=10)
assert result.returncode == 0 and result.stdout.strip() == 'workspace-ok'
assert scratch in cleanup_workspace(0, dry_run=True)
assert cleanup_workspace_temp(scratch)
assert list((root / 'tmp').iterdir()) == []
print('Non-root read-only container workspace: PASS')
"""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/home/ocf/.ocf:uid=10001,gid=10001,mode=0700",
            "--entrypoint",
            "python",
            image,
            "-c",
            smoke,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "workspace: PASS" in result.stdout
