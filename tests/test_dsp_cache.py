import pytest
from ocf_tools import dsp_cache


@pytest.mark.unit
def test_dsp_stems_require_matching_hash_and_respect_storage_bounds(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    source = tmp_path / "verified-engine-stem.wav"
    source.write_bytes(b"verified fixture bytes")
    key = "a" * 64
    assert dsp_cache.lookup(key) is None
    assert dsp_cache.store(key, source)
    cached = dsp_cache.lookup(key)
    assert cached.read_bytes() == source.read_bytes()
    cached.write_bytes(b"corrupted")
    assert dsp_cache.lookup(key) is None
    monkeypatch.setattr(dsp_cache, "MAX_BYTES", 0)
    assert not dsp_cache.store("b" * 64, source)
    assert dsp_cache.lookup(None) is None


@pytest.mark.unit
def test_dsp_cache_is_opt_in_and_does_not_probe_engines_in_unit_mode(tmp_path):
    assert dsp_cache.cache_key(tmp_path / "missing-preset", 0, 10) is None


@pytest.mark.unit
def test_dsp_key_tracks_content_even_when_cli_has_no_version_flag(monkeypatch, tmp_path):
    from ocf_tools import farfield
    from ocf_tools.speech_cache import enabled

    source = tmp_path / "preset.yaml"
    source.write_text("fixture: one")
    engine = tmp_path / "engine/src/farfield/module.py"
    engine.parent.mkdir(parents=True)
    engine.write_text("version = 1")
    from ocf_tools.utils import sha256_of_file

    monkeypatch.setattr(
        farfield,
        "engine_identity",
        lambda: {"version": None, "implementation_sha256": sha256_of_file(engine)},
    )
    with enabled():
        first = dsp_cache.cache_key(source, 0, 40)
        assert first is not None
        assert first != dsp_cache.cache_key(source, 1, 40)
        assert first != dsp_cache.cache_key(source, 0, 41)
        engine.write_text("version = 2")
        assert first != dsp_cache.cache_key(source, 0, 40)
