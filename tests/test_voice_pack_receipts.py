"""Private inference receipts are only trusted when every binding still matches."""

import json

import pytest
from ocf_tools import voice_packs
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit

REFERENCE = "a" * 64


def receipt(output="", **changes):
    result = {
        "status": "success",
        "backend": "chatterbox-nano",
        "model_identifier": "ResembleAI/chatterbox-nano",
        "model_revision": "1" * 40,
        "adapter_revision": "2" * 40,
        "model_tree_sha256": "3" * 64,
        "output_sha256": "4" * 64,
        "reference_sha256": REFERENCE,
        "reference_text_sha256": "5" * 64,
        "text_sha256": "6" * 64,
        "sample_rate": 24000,
        "duration_s": 1.0,
        "sample_peak": 0.5,
        "output": output,
    }
    return {**result, **changes}


@pytest.mark.parametrize(
    "changes,reference",
    [
        ({"status": "failed"}, None),
        ({"backend": "piper"}, None),
        ({"model_identifier": "other"}, None),
        ({"model_revision": "not-a-commit"}, None),
        ({"adapter_revision": "not-a-commit"}, None),
        ({"model_tree_sha256": "bad"}, None),
        ({"output_sha256": "bad"}, None),
        ({"reference_sha256": "bad"}, None),
        ({"reference_text_sha256": "bad"}, None),
        ({"text_sha256": "bad"}, None),
        ({"reference_sha256": "b" * 64}, REFERENCE),
        ({"sample_rate": 16000}, None),
        ({"duration_s": 0}, None),
        ({"duration_s": "1"}, None),
        ({"sample_peak": 0}, None),
        ({"sample_peak": 0.981}, None),
        ({"sample_peak": "0.5"}, None),
    ],
)
def test_receipt_proof_rejects_unbound_or_invalid_inference(changes, reference):
    assert not voice_packs._receipt_proves_inference(receipt(**changes), reference)


def test_receipt_proof_accepts_complete_matching_inference():
    assert voice_packs._receipt_proves_inference(receipt(), REFERENCE)
    assert not voice_packs._receipt_proves_inference(receipt(), "f" * 64)


@pytest.mark.parametrize(
    "case,match",
    [
        ("wrong-backend", "only chatterbox-nano"),
        ("wrong-model", "model identifier differs"),
        ("empty-text", "text must not be empty"),
        ("no-interpreter", "optional environment is missing"),
        ("missing-reference", "reference is missing or fails its checksum"),
        ("reference-mismatch", "reference is missing or fails its checksum"),
    ],
)
def test_synthesis_preflight_rejects_invalid_pack_without_subprocess(
    monkeypatch, tmp_path, case, match
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    assets = tmp_path / "assets"
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(assets))
    interpreter = tmp_path / "chatterbox-python"
    interpreter.write_text("fake interpreter path; no subprocess is launched")
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(interpreter))
    reference = assets / "OCF-VOICE-9899/reference.wav"
    profile = {
        "id": "OCF-VOICE-9899",
        "backend": "chatterbox-nano",
        "reference_audio": {
            "model_identifier": "ResembleAI/chatterbox-nano",
            "asset": "OCF-VOICE-9899/reference.wav",
            "sha256": "a" * 64,
        },
    }
    text = "A new utterance."
    if case == "wrong-backend":
        profile["backend"] = "piper"
    elif case == "wrong-model":
        profile["reference_audio"]["model_identifier"] = "other-model"
    elif case == "empty-text":
        text = "   "
    elif case == "no-interpreter":
        monkeypatch.delenv("OCF_CHATTERBOX_PYTHON")
    elif case == "reference-mismatch":
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_bytes(b"different reference bytes")

    monkeypatch.setattr(voice_packs, "_profile_for_synthesis", lambda _query: profile)
    with pytest.raises(OCFError, match=match):
        voice_packs.synthesize("OCF-VOICE-9899", text)


def test_inference_receipts_ignores_corrupt_wrong_voice_and_failed_records(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    root = tmp_path / "work/logs/voice-inference/OCF-VOICE-9899"
    root.mkdir(parents=True)
    (root / "success.json").write_text(json.dumps({**receipt(), "voice_id": "OCF-VOICE-9899"}))
    (root / "other.json").write_text(json.dumps({**receipt(), "voice_id": "OCF-VOICE-9898"}))
    (root / "failed.json").write_text(
        json.dumps({**receipt(), "voice_id": "OCF-VOICE-9899", "status": "failed"})
    )
    (root / "corrupt.json").write_text("{")
    (root / "ignored.txt").write_text("not a receipt")
    assert [row["voice_id"] for row in voice_packs.inference_receipts("OCF-VOICE-9899")] == [
        "OCF-VOICE-9899"
    ]
    assert voice_packs.inference_receipts("OCF-VOICE-9898") == []


def test_inference_verified_requires_confined_real_output_and_matching_hash(monkeypatch, tmp_path):
    from ocf_tools.utils import sha256_of_file

    root = tmp_path / "work/renders/voice-pack-auditions/OCF-VOICE-9899"
    root.mkdir(parents=True)
    output = root / "audition.wav"
    output.write_bytes(b"verified output bytes")
    base = receipt(str(output), output_sha256=sha256_of_file(output))
    profile = {"id": "OCF-VOICE-9899", "reference_audio": {"sha256": REFERENCE}}
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(voice_packs, "inference_receipts", lambda _voice_id: [base])
    assert voice_packs.inference_verified(profile)

    monkeypatch.setattr(voice_packs, "inference_receipts", lambda _voice_id: [receipt(str(output))])
    assert not voice_packs.inference_verified(profile)
    monkeypatch.setattr(
        voice_packs,
        "inference_receipts",
        lambda _voice_id: [receipt(str(root / "missing.wav"))],
    )
    assert not voice_packs.inference_verified(profile)
    external = tmp_path / "outside.wav"
    external.write_bytes(b"verified output bytes")
    monkeypatch.setattr(
        voice_packs,
        "inference_receipts",
        lambda _voice_id: [receipt(str(external), output_sha256=sha256_of_file(external))],
    )
    assert not voice_packs.inference_verified(profile)


def test_inference_verified_rejects_symlink_output(monkeypatch, tmp_path):
    from ocf_tools.utils import sha256_of_file

    root = tmp_path / "work/renders/voice-pack-auditions/OCF-VOICE-9899"
    root.mkdir(parents=True)
    actual = root / "actual.wav"
    actual.write_bytes(b"audio")
    link = root / "linked.wav"
    try:
        link.symlink_to(actual)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(
        voice_packs,
        "inference_receipts",
        lambda _voice_id: [receipt(str(link), output_sha256=sha256_of_file(actual))],
    )
    assert not voice_packs.inference_verified(
        {"id": "OCF-VOICE-9899", "reference_audio": {"sha256": REFERENCE}}
    )
