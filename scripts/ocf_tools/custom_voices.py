"""Private model import, portable metadata and bounded original-passage auditions."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .paths import REPO_ROOT, unique_run_id, work_path
from .utils import OCFError, sha256_of_file, write_text_atomic, yaml_safe_dump


def asset_root() -> Path:
    value = os.environ.get("OCF_VOICE_ASSETS")
    if value:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else REPO_ROOT / path).resolve()
    return work_path("cache", "voices", "models")


def validate_profile(profile: dict, *, assets: bool = True) -> dict:
    from .validators import _load_schema, validate_against_schema

    errors = validate_against_schema(profile, _load_schema("voice-profile.schema.json"))
    if errors:
        raise OCFError("voice profile: " + " | ".join(errors))
    from pathlib import PureWindowsPath

    for value in [
        *profile.get("required_assets", []),
        *([profile["consent_record"]] if profile.get("consent_record") else []),
    ]:
        if Path(value).is_absolute() or PureWindowsPath(value).drive or ".." in Path(value).parts:
            errors.append(
                "portable asset/consent references must not contain personal absolute paths or traversal"
            )
    if profile.get("model"):
        model = profile["model"]
        relative = Path(model["asset"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in model["asset"]:
            errors.append("model asset must be a contained portable relative path")
        else:
            path = (asset_root() / relative).resolve()
            if not path.is_relative_to(asset_root()):
                errors.append("model asset escapes its configured root")
            elif assets:
                if not path.is_file():
                    errors.append("model asset is not installed")
                elif sha256_of_file(path) != model["sha256"]:
                    errors.append("model checksum mismatch")
                config = Path(str(path) + ".json")
                if not config.is_file():
                    errors.append("Piper model configuration is missing")
                elif (
                    model.get("config_sha256") and sha256_of_file(config) != model["config_sha256"]
                ):
                    errors.append("model configuration checksum mismatch")
    if profile.get("voice_kind") == "cloned" and (
        profile.get("consent_status") not in {"self-recorded", "authorized-contributor"}
        or not profile.get("consent_record")
    ):
        errors.append("cloned voice requires explicit authorization metadata and a consent record")
    if errors:
        raise OCFError("voice profile: " + " | ".join(errors))
    return {
        "id": profile["id"],
        "valid": True,
        "assets_checked": assets,
        "distribution_permission": profile.get("distribution_permission", "unknown"),
    }


def import_model(
    model_path: Path,
    *,
    voice_id: str,
    name: str,
    model_version: str = "unversioned-local",
    license: str = "unknown",
    voice_kind: str = "installed-model",
    consent_status: str = "unknown",
    consent_record: str | None = None,
) -> dict:
    from .indexes import load_voice_profiles
    from .locale import normalize_tag

    if any(p["id"] == voice_id for p in load_voice_profiles()):
        raise OCFError(
            "voice ID already exists; choose a new ID/version rather than replacing a voice"
        )
    model_path = model_path.expanduser().resolve()
    if model_path.suffix != ".onnx" or not model_path.is_file():
        raise OCFError("import requires a local Piper .onnx model and its .onnx.json configuration")
    config_path = Path(str(model_path) + ".json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    language = config.get("language", {}).get("code")
    rate = config.get("audio", {}).get("sample_rate")
    if not isinstance(language, str) or not language or type(rate) is not int:
        raise OCFError("Piper configuration lacks language.code or audio.sample_rate")
    checksum = sha256_of_file(model_path)
    profile = {
        "schema_version": "1.0",
        "id": voice_id,
        "slug": voice_id.lower(),
        "name": name,
        "version": "1.0.0",
        "backend": "piper",
        "language": language,
        "locale": normalize_tag(language.replace("_", "-")),
        "sample_rate": rate,
        "model": {
            "asset": checksum + ".onnx",
            "sha256": checksum,
            "config_sha256": sha256_of_file(config_path),
            "version": model_version,
        },
        "privacy": "private",
        "voice_kind": voice_kind,
        "consent_status": consent_status,
        "license": license,
        "attribution": "Operator-supplied local model; attribution must be completed before sharing.",
        "distribution_permission": "unknown",
        "pacing_compatibility": ["semantic-units", "piper-length-scale"],
    }
    if consent_record:
        profile["consent_record"] = consent_record
    validate_profile(profile, assets=False)
    root = asset_root()
    root.mkdir(parents=True, exist_ok=True)
    for source, destination in (
        (model_path, root / profile["model"]["asset"]),
        (config_path, root / (profile["model"]["asset"] + ".json")),
    ):
        if destination.exists():
            if sha256_of_file(destination) != sha256_of_file(source):
                raise OCFError("existing model asset differs; refusing replacement")
        else:
            with destination.open("xb") as out, source.open("rb") as incoming:
                shutil.copyfileobj(incoming, out)
    validate_profile(profile)
    path = work_path("cache", "voices", "profiles", voice_id + ".yaml")
    write_text_atomic(path, yaml_safe_dump(profile), overwrite=False)
    return {
        "profile": profile,
        "path": str(path),
        "inference_verified": False,
        "note": "Run voice audition to test real inference; import verifies metadata and checksums only.",
    }


def model_path(profile: dict) -> str | None:
    if not profile.get("model"):
        return None
    validate_profile(profile)
    return str(asset_root() / profile["model"]["asset"])


def audition(voices: list[str], *, locale: str = "en-US") -> dict:
    if not 1 <= len(set(voices)) <= 4 or locale != "en-US":
        raise OCFError("select 1..4 voices; the original comparison script is currently en-US only")
    from .locale import LocaleCatalog
    from .narration_first import _voice_profile
    from .narration_pacing import split_speech_units
    from .speech_cache import enabled
    from .voice import (
        _fade_spoken_unit,
        _paced_voice_spec,
        _read_pcm_from_bytes,
        _resample,
        _write_wav,
        apply_pronunciation,
        render_cue_wav,
    )

    script = json.loads((REPO_ROOT / "audio/voices/recording-script.json").read_text())
    root = work_path("renders", unique_run_id("voice-comparison"))
    root.mkdir(parents=True)
    outputs = []
    for query in voices:
        profile, backend = _voice_profile(query, locale, LocaleCatalog())
        samples, segments = [], []
        with enabled():
            for role in ("normal", "relaxation", "counting", "focus", "activation"):
                for unit in split_speech_units(script["passages"][role]):
                    spec, rate = _paced_voice_spec(backend, 0.9 if role == "relaxation" else 1.0)
                    text = apply_pronunciation(
                        unit["text"], profile.get("pronunciation", {}), spec["name"]
                    )
                    native_rate, pcm = _read_pcm_from_bytes(render_cue_wav(spec, text))
                    pcm = _fade_spoken_unit(_resample(pcm, native_rate, 44100), 44100)
                    start = len(samples) / 44100
                    samples.extend(pcm)
                    segments.append(
                        {
                            "role": role,
                            "text": unit["text"],
                            "start_seconds": start,
                            "speech_seconds": len(pcm) / 44100,
                            "rate": rate,
                        }
                    )
                    samples.extend([0] * 66150)
        peak = max((abs(v) for v in samples), default=0)
        if not peak:
            raise OCFError("voice audition produced no audible samples")
        factor = (32767 * 10 ** (-3 / 20)) / peak
        samples = [round(v * factor) for v in samples]
        path = root / f"{profile['id']}-audition.wav"
        _write_wav(path, samples, 44100, overwrite=False)
        outputs.append(
            {
                "voice_id": profile["id"],
                "path": path.name,
                "sha256": sha256_of_file(path),
                "duration_seconds": len(samples) / 44100,
                "normalization_gain": factor,
                "segments": segments,
            }
        )
    report = {
        "schema_version": "1.0",
        "locale": locale,
        "script_version": script["version"],
        "background": "none for every voice",
        "peak_target_dbfs": -3,
        "listening_approval": None,
        "outputs": outputs,
    }
    write_text_atomic(root / "comparison.json", json.dumps(report, indent=2) + "\n")
    return {"output_directory": str(root), "report": report}
