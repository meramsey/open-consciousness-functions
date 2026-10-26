import os
from pathlib import Path

import pytest
from ocf_tools import utils

pytestmark = pytest.mark.unit


def test_verified_hash_reuse_is_job_scoped_and_detects_same_size_replacement(monkeypatch, tmp_path):
    source = tmp_path / "private.flac"
    source.write_bytes(b"source one")
    original_open = open
    reads = []

    def counted_open(path, *args, **kwargs):
        if Path(path) == source and args == ("rb",):
            reads.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(utils, "open", counted_open, raising=False)
    with utils.verified_file_hashes():
        before = utils.sha256_of_file(source)
        assert utils.sha256_of_file(source) == before
        assert len(reads) == 1
        stamp = source.stat().st_mtime_ns
        replacement = source.with_suffix(".new")
        replacement.write_bytes(b"source two")
        os.utime(replacement, ns=(stamp, stamp))
        os.replace(replacement, source)
        assert utils.sha256_of_file(source) != before
        assert len(reads) == 2
    utils.sha256_of_file(source)
    assert len(reads) == 3
    assert utils._file_hashes.get() is None


def test_changing_source_during_hash_is_not_verified(monkeypatch, tmp_path):
    source = tmp_path / "source.flac"
    source.write_bytes(b"source one")
    real_sha = utils.hashlib.sha256

    class ChangingHash:
        def __init__(self):
            self.digest = real_sha()

        def update(self, data):
            self.digest.update(data)
            source.write_bytes(b"changed")

        def hexdigest(self):
            return self.digest.hexdigest()

    monkeypatch.setattr(utils.hashlib, "sha256", ChangingHash)
    with utils.verified_file_hashes(), pytest.raises(utils.OCFError, match="changed while hashing"):
        utils.sha256_of_file(source)
