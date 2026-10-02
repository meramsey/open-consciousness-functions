"""Static container invariants complement, never replace, a real runtime check."""

from conftest import REPO_ROOT


def test_image_does_not_copy_reference_or_user_audio():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    ignored = (REPO_ROOT / ".dockerignore").read_text()
    assert "COPY . " not in dockerfile and "COPY references" not in dockerfile
    assert "USER ocf" in dockerfile and "ffmpeg" in dockerfile
    assert "references" in ignored and "audio/rendered" in ignored and "**/*.onnx" in ignored
    assert "OCF-TPL-SESSION-ATTENTION-001" not in dockerfile
