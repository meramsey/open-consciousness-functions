"""CLI/service contracts use mocks; recording integration uses synthetic WAVs only."""

import argparse
import json
import math
import re
import shlex
import struct
import wave
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from ocf_tools import voice_engine_cli as engine
from ocf_tools.utils import OCFError, sha256_of_file


@pytest.fixture
def parser():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    voice = commands.add_parser("voice").add_subparsers(dest="voice_kind")
    # Existing commands remain owned by the shared CLI.
    voice.add_parser("doctor")
    voice.add_parser("training-plan")
    engine.add_commands(voice)
    new = commands.add_parser("new").add_subparsers(dest="new_kind")
    new.add_parser("voice")
    engine.add_new_commands(new)
    return parser


@pytest.mark.unit
@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["voice", "capabilities"], {"voice_kind": "capabilities", "gpu": False, "json": False}),
        (
            ["voice", "capabilities", "--gpu", "--json"],
            {"voice_kind": "capabilities", "gpu": True, "json": True},
        ),
        (
            ["voice", "export-profile", "My private voice", "--output", "portable.json"],
            {"query": "My private voice", "output": Path("portable.json"), "include_assets": False},
        ),
        (
            ["voice", "import-profile", "portable.json"],
            {
                "file": Path("portable.json"),
                "include_assets": False,
                "id": None,
                "consent_record": None,
            },
        ),
        (
            ["voice", "dataset-guide", "dataset.json", "--json"],
            {"voice_kind": "dataset-guide", "manifest": Path("dataset.json"), "json": True},
        ),
        (
            ["new", "voice-dataset", "dataset.json"],
            {"new_kind": "voice-dataset", "manifest": Path("dataset.json")},
        ),
        (["new", "voice"], {"new_kind": "voice"}),
        (["voice", "training-plan"], {"voice_kind": "training-plan"}),
    ],
)
def test_registration_destinations_and_safe_defaults(parser, argv, expected):
    namespace = vars(parser.parse_args(argv))
    assert expected.items() <= namespace.items()


@pytest.mark.unit
@pytest.mark.parametrize(
    "argv",
    [
        "voice export-profile PROFILE",
        "voice import-profile",
        "voice dataset-guide",
        "voice dataset-record dataset.json normal-001 --session day-one --speaker me",
        "voice dataset-record dataset.json normal-001 --audio take.wav --speaker me",
        "voice dataset-record dataset.json normal-001 --audio take.wav --session day-one",
        "voice clone",
        "voice train",
    ],
)
def test_missing_required_arguments_and_unshipped_commands(parser, argv):
    with pytest.raises(SystemExit) as error:
        parser.parse_args(shlex.split(argv))
    assert error.value.code == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    ("argv", "owner", "service", "positional", "keywords"),
    [
        (
            "voice export-profile OCF-VOICE-9001 --output portable.json",
            engine.custom_voices,
            "export_profile",
            ("OCF-VOICE-9001", Path("portable.json")),
            {"include_assets": False},
        ),
        (
            "voice export-profile OCF-VOICE-9001 --output portable.json --include-assets",
            engine.custom_voices,
            "export_profile",
            ("OCF-VOICE-9001", Path("portable.json")),
            {"include_assets": True},
        ),
        (
            "voice import-profile portable.json",
            engine.custom_voices,
            "import_profile",
            (Path("portable.json"),),
            {"include_assets": False, "voice_id": None, "consent_record": None},
        ),
        (
            "voice import-profile portable.json --include-assets --id OCF-VOICE-9002 "
            "--consent-record private/consent.txt",
            engine.custom_voices,
            "import_profile",
            (Path("portable.json"),),
            {
                "include_assets": True,
                "voice_id": "OCF-VOICE-9002",
                "consent_record": "private/consent.txt",
            },
        ),
        (
            "voice dataset-record dataset.json normal-001 --audio take.wav "
            "--session day-one --speaker me",
            engine.voice_datasets,
            "import_recording",
            (Path("dataset.json"), "normal-001", Path("take.wav")),
            {"session_id": "day-one", "speaker": "me"},
        ),
        (
            "voice dataset-guide dataset.json --json",
            engine.voice_datasets,
            "recording_workflow",
            (Path("dataset.json"),),
            {},
        ),
        (
            "new voice-dataset dataset.json",
            engine,
            "run_recording_wizard",
            (Path("dataset.json"),),
            {},
        ),
    ],
)
def test_dispatch_preserves_service_results(
    parser, monkeypatch, capsys, argv, owner, service, positional, keywords
):
    result = {"service": service, "inference_verified": False}
    mocked = Mock(return_value=result)
    monkeypatch.setattr(owner, service, mocked)
    assert engine.dispatch(parser.parse_args(shlex.split(argv))) is result
    mocked.assert_called_once_with(*positional, **keywords)
    assert capsys.readouterr().out == ""


@pytest.mark.unit
def test_dispatch_propagates_service_errors(parser, monkeypatch):
    monkeypatch.setattr(
        engine.custom_voices, "import_profile", Mock(side_effect=OCFError("checksum mismatch"))
    )
    with pytest.raises(OCFError, match="checksum mismatch"):
        engine.dispatch(parser.parse_args(["voice", "import-profile", "bad.json"]))
    with pytest.raises(OCFError, match="unknown voice engine command"):
        engine.dispatch(argparse.Namespace(voice_kind="training-plan"))


@pytest.mark.unit
@pytest.mark.parametrize("gpu", [False, True])
def test_capabilities_are_actionable_without_promoting_installation(parser, monkeypatch, gpu):
    registry = engine.voice_capabilities.capability_registry()

    def capability(backend):
        spec = deepcopy(registry[backend])
        return {
            **spec,
            "backend": backend,
            "installation": {"package_found": True, "executable_found": backend == "espeak"},
            "available": backend == "espeak",
        }

    monkeypatch.setattr(engine.voice_capabilities, "backend_capability", capability)
    preflight = Mock(return_value={"gpu_probe": "mocked", "training_resources_verified": False})
    monkeypatch.setattr(engine.voice_capabilities, "local_preflight", preflight)
    argv = ["voice", "capabilities", "--json"] + (["--gpu"] if gpu else [])
    result = engine.dispatch(parser.parse_args(argv))
    preflight.assert_called_once_with(probe_gpu=gpu)
    assert not result["training_supported"] and not result["inference_verified"]
    assert not result["resources"]["training_resources_verified"]
    backends = {b["backend"]: b for b in result["backends"]}
    assert not backends["f5-tts"]["available"]
    assert backends["f5-tts"]["upstream"]["reference_inference"]
    assert not backends["f5-tts"]["ocf"]["inference_supported"]
    assert "unsupported" in " ".join(backends["f5-tts"]["blockers"])
    assert "Install piper" in " ".join(backends["piper"]["next_actions"])
    assert backends["espeak"]["available"] and not backends["espeak"]["inference_verified"]
    assert all(b["blockers"] and b["next_actions"] and b["guide"] for b in result["backends"])
    json.dumps(result)  # The shared CLI can render this directly, including --json.


@pytest.mark.integration
def test_shared_parser_compatibility_and_documented_commands(repo_root):
    from ocf_tools.cli import _build_parser

    parser = _build_parser()
    assert parser.parse_args(["new", "voice"]).new_kind == "voice"
    assert (
        parser.parse_args(["voice", "training-plan", "--backend", "piper"]).voice_kind
        == "training-plan"
    )
    commands = []
    for name in ("VOICE_CLONING.md", "VOICE_TRAINING.md"):
        text = (repo_root / "docs" / name).read_text()
        for block in re.findall(r"```bash\n(.*?)```", text, re.DOTALL):
            for line in block.replace("\\\n", " ").splitlines():
                if line.startswith("python scripts/ocf.py "):
                    args = parser.parse_args(shlex.split(line)[2:])
                    commands.append(getattr(args, "voice_kind", getattr(args, "new_kind", None)))
    assert {
        "capabilities",
        "export-profile",
        "import-profile",
        "dataset-record",
        "dataset-guide",
        "voice-dataset",
        "training-plan",
    } <= set(commands)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("argv", "owner", "service", "positional", "keywords"),
    [
        (
            "voice export-profile OCF-VOICE-9001 --output portable.json --include-assets",
            engine.custom_voices,
            "export_profile",
            ("OCF-VOICE-9001", Path("portable.json")),
            {"include_assets": True},
        ),
        (
            "voice import-profile portable.json --include-assets --id OCF-VOICE-9002 "
            "--consent-record private/consent.txt",
            engine.custom_voices,
            "import_profile",
            (Path("portable.json"),),
            {
                "include_assets": True,
                "voice_id": "OCF-VOICE-9002",
                "consent_record": "private/consent.txt",
            },
        ),
        (
            "voice dataset-record dataset.json normal-001 --audio take.wav "
            "--session day-one --speaker me",
            engine.voice_datasets,
            "import_recording",
            (Path("dataset.json"), "normal-001", Path("take.wav")),
            {"session_id": "day-one", "speaker": "me"},
        ),
        (
            "voice dataset-guide dataset.json --json",
            engine.voice_datasets,
            "recording_workflow",
            (Path("dataset.json"),),
            {},
        ),
        (
            "new voice-dataset dataset.json",
            engine,
            "run_recording_wizard",
            (Path("dataset.json"),),
            {},
        ),
    ],
)
def test_main_forwards_new_commands_to_services(
    monkeypatch, capsys, argv, owner, service, positional, keywords
):
    from ocf_tools.cli import main

    result = {"status": "completed", "service": service, "note": "Synthetic café fixture"}
    mocked = Mock(return_value=result)
    monkeypatch.setattr(owner, service, mocked)
    assert main(shlex.split(argv)) == 0
    mocked.assert_called_once_with(*positional, **keywords)
    output = capsys.readouterr()
    assert json.loads(output.out) == result
    assert output.err == ""


@pytest.mark.integration
@pytest.mark.parametrize("gpu", [False, True])
def test_main_capabilities_forwards_explicit_gpu_flag_to_preflight(monkeypatch, capsys, gpu):
    from ocf_tools.cli import main

    registry = engine.voice_capabilities.capability_registry()
    monkeypatch.setattr(
        engine.voice_capabilities, "capability_registry", lambda: {"piper": registry["piper"]}
    )
    capability = {
        **registry["piper"],
        "backend": "piper",
        "available": False,
        "installation": {"package_found": False, "executable_found": False},
    }
    backend = Mock(return_value=capability)
    preflight = Mock(return_value={"gpu_probe": "mocked", "training_resources_verified": False})
    monkeypatch.setattr(engine.voice_capabilities, "backend_capability", backend)
    monkeypatch.setattr(engine.voice_capabilities, "local_preflight", preflight)
    assert main(["voice", "capabilities", "--json"] + (["--gpu"] if gpu else [])) == 0
    backend.assert_called_once_with("piper")
    preflight.assert_called_once_with(probe_gpu=gpu)
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert not report["training_supported"] and not report["inference_verified"]
    assert report["resources"]["gpu_probe"] == "mocked"
    assert report["backends"][0]["blockers"] and report["backends"][0]["next_actions"]
    assert output.err == ""


@pytest.mark.integration
def test_main_reports_profile_service_errors(monkeypatch, capsys):
    from ocf_tools.cli import main

    service = Mock(side_effect=OCFError("checksum mismatch"))
    monkeypatch.setattr(engine.custom_voices, "import_profile", service)
    assert main(["voice", "import-profile", "bad.json"]) == 1
    service.assert_called_once_with(
        Path("bad.json"), include_assets=False, voice_id=None, consent_record=None
    )
    output = capsys.readouterr()
    assert output.out == "" and "checksum mismatch" in output.err


@pytest.fixture
def original_dataset(tmp_path):
    result = engine.voice_datasets.initialize(tmp_path / "dataset", dataset_id="wizard-test")
    manifest = Path(result["path"])
    return manifest, json.loads(manifest.read_text())


def synthetic_wav(path, rate):
    """A synthetic tone verifies byte import, never speaker quality or inference."""
    payload = b"".join(
        struct.pack("<h", round(8000 * math.sin(2 * math.pi * 220 * i / rate)))
        for i in range(rate // 10)
    )
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(payload)
    return path


@pytest.mark.integration
def test_wizard_original_script_synthetic_imports_setup_and_perprompt_identities(
    original_dataset, tmp_path
):
    manifest, original = original_dataset
    source = synthetic_wav(tmp_path / "external take.wav", original["sample_rate"])
    source_bytes = source.read_bytes()
    answers = iter(
        [
            "Soft room; room tone inspected manually",
            "Mic 20 cm off-axis",
            "Peaks near -9 dBFS",
            str(source),
            "day-one",
            "speaker-one",
            str(source),
            "day-two",
            "speaker-two",
            ":quit",
        ]
    )
    questions, output = [], []

    def input_fn(question):
        questions.append(question)
        return next(answers)

    report = engine.run_recording_wizard(manifest, input_fn=input_fn, print_fn=output.append)
    assert report["status"] == "cancelled" and len(report["imports"]) == 2
    assert not report["capture_supported"] and not report["microphone_captured"]
    assert not report["model_produced"] and not report["validation"]["authorization_verified"]
    assert not report["validation"]["readiness"]["dataset_ready"]
    assert not report["import_errors"]
    saved = json.loads(manifest.read_text())
    assert [(s["id"], s["speaker"]) for s in saved["sessions"]] == [
        ("day-one", "speaker-one"),
        ("day-two", "speaker-two"),
    ]
    assert saved["sessions"][0]["microphone"] == "Mic 20 cm off-axis"
    assert saved["sessions"][0]["gain_notes"] == "Peaks near -9 dBFS"
    assert saved["consent_status"] == original["consent_status"] == "unknown"
    assert source.read_bytes() == source_bytes
    assert len(saved["records"]) == len(original["records"])
    for index, imported in enumerate(report["imports"]):
        record, prompt = imported["record"], original["records"][index]
        assert record["text"] == prompt["text"] and record["split"] == prompt["split"]
        assert record["text_sha256"] == engine.voice_datasets.text_fingerprint(prompt["text"])
        assert record["source_sha256"] == record["sha256"] == sha256_of_file(source)
        assert (manifest.parent / record["audio"]).read_bytes() == source_bytes
        assert not imported["converted"] and imported["source_preserved"]
        assert prompt["text"] in output
    assert sum(q.startswith("Session ID") for q in questions) == 2
    assert any("not measurements" in line for line in output)


@pytest.mark.integration
def test_wizard_skip_all_preserves_manifest(original_dataset):
    manifest, data = original_dataset
    before = manifest.read_bytes()
    report = engine.run_recording_wizard(manifest, input_fn=lambda _: "", print_fn=lambda _: None)
    assert report["status"] == "completed" and not report["imports"]
    assert report["skipped_prompts"] == [r["id"] for r in data["records"]]
    assert manifest.read_bytes() == before


@pytest.mark.integration
def test_wizard_bad_audio_retry_empty_identity_and_interruption_preserve_success(
    original_dataset, tmp_path
):
    manifest, data = original_dataset
    source = synthetic_wav(tmp_path / "take.wav", data["sample_rate"])
    answers = iter(
        [
            "",
            "",
            "",
            str(tmp_path / "missing.wav"),
            "day-one",
            "speaker",
            str(source),
            "",
            "day-one",
            "",
            "speaker",
        ]
    )
    output = []

    def input_fn(_):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    report = engine.run_recording_wizard(manifest, input_fn=input_fn, print_fn=output.append)
    assert report["status"] == "cancelled" and len(report["imports"]) == 1
    assert len(report["import_errors"]) == 1
    assert "requires a local" in report["import_errors"][0]["message"]
    assert output.count("A nonempty identity is required.") == 2
    assert any("Input interrupted" in line for line in output)
    assert json.loads(manifest.read_text())["records"][0]["sha256"] == sha256_of_file(source)


@pytest.mark.integration
@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_wizard_interrupted_setup_does_not_write(original_dataset, exception):
    manifest, _ = original_dataset
    before = manifest.read_bytes()

    def input_fn(_):
        raise exception

    report = engine.run_recording_wizard(manifest, input_fn=input_fn, print_fn=lambda _: None)
    assert report["status"] == "cancelled" and not report["imports"]
    assert manifest.read_bytes() == before
