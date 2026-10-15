"""Private model import, portable metadata and bounded original-passage auditions."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from .paths import REPO_ROOT, unique_run_id, work_path
from .utils import (
    OCFError,
    read_json_object,
    sha256_of_file,
    write_text_atomic,
    yaml_safe_dump,
)


def _portable_relative(value: str) -> Path:
    """Validate portable path syntax without consulting a sender's filesystem."""
    relative = Path(value)
    if (
        not value
        or not relative.parts
        or any(ord(character) < 32 for character in value)
        or relative.is_absolute()
        or PureWindowsPath(value).root
        or PureWindowsPath(value).drive
        or ".." in relative.parts
        or "\\" in value
        or value.startswith("~")
        or "$" in value
    ):
        raise OCFError("asset/consent reference must be a contained portable relative path")
    return relative


def _contained(root: Path, value: str) -> Path:
    """Reject POSIX and Windows escapes, including symlink escapes on this host."""
    relative = _portable_relative(value)
    path = (root.resolve() / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise OCFError("asset reference escapes its configured root")
    return path


def _validate_finite_json(value, location: str = "voice profile") -> None:
    """Reject non-finite numbers recursively, including JSON exponent overflow."""
    if isinstance(value, float) and not math.isfinite(value):
        raise OCFError(f"{location}: non-finite number; NaN and Infinity are not permitted")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise OCFError(f"{location}: JSON metadata keys must be strings")
            _validate_finite_json(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_finite_json(item, f"{location}[{index}]")
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise OCFError(f"{location}: metadata must contain JSON-compatible values")


def _copy_verified(source: Path, destination: Path, checksum: str) -> bool:
    if not source.is_file() or sha256_of_file(source) != checksum:
        raise OCFError("asset checksum mismatch or asset missing")
    if destination.is_symlink():
        raise OCFError("refusing to replace or reuse a symlink asset")
    if destination.exists():
        if not destination.is_file() or sha256_of_file(destination) != checksum:
            raise OCFError("existing model asset differs; refusing replacement")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as out, source.open("rb") as incoming:
        shutil.copyfileobj(incoming, out)
    if sha256_of_file(destination) != checksum:
        raise OCFError("copied asset checksum mismatch")
    return True


def asset_root() -> Path:
    value = os.environ.get("OCF_VOICE_ASSETS")
    if value:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else REPO_ROOT / path).resolve()
    return work_path("cache", "voices", "models")


def validate_profile(profile: dict, *, assets: bool = True) -> dict:
    from .validators import _load_schema, validate_against_schema

    _validate_finite_json(profile)
    errors = validate_against_schema(profile, _load_schema("voice-profile.schema.json"))
    if errors:
        raise OCFError("voice profile: " + " | ".join(errors))
    for value in [
        *profile.get("required_assets", []),
        *([profile["consent_record"]] if profile.get("consent_record") else []),
    ]:
        try:
            path = _contained(asset_root(), value)
            if (
                assets
                and value == profile.get("consent_record")
                and (
                    profile.get("voice_kind") == "cloned"
                    or profile.get("customization_method") == "trained-adapted"
                )
                and not path.is_file()
            ):
                errors.append(
                    "cloned/trained voice consent record must exist as a file under the asset root"
                )
        except OCFError as exc:
            errors.append(str(exc))
    if profile.get("model"):
        model = profile["model"]
        try:
            path = _contained(asset_root(), model["asset"])
        except OCFError as exc:
            errors.append(str(exc))
        else:
            if assets:
                if not path.is_file():
                    errors.append("model asset is not installed")
                elif sha256_of_file(path) != model["sha256"]:
                    errors.append("model checksum mismatch")
                config = _contained(asset_root(), model["asset"] + ".json")
                if profile["backend"] != "piper":
                    config = None
                if config is None:
                    pass
                elif not config.is_file():
                    errors.append("Piper model configuration is missing")
                elif (
                    model.get("config_sha256") and sha256_of_file(config) != model["config_sha256"]
                ):
                    errors.append("model configuration checksum mismatch")
                elif config.is_file():
                    metadata = read_json_object(config)
                    _validate_finite_json(metadata, "Piper configuration")
                    audio = metadata.get("audio")
                    if not isinstance(audio, dict):
                        errors.append("model configuration lacks an audio object")
                    elif profile.get("sample_rate") and profile["sample_rate"] != audio.get(
                        "sample_rate"
                    ):
                        errors.append("declared sample rate differs from model configuration")
                    speakers = metadata.get("num_speakers", 1)
                    if type(speakers) is not int or speakers < 1:
                        errors.append("model speaker count must be a positive integer")
                    elif "speaker_id" in profile and profile["speaker_id"] >= speakers:
                        errors.append("speaker ID is outside the model speaker range")
    elif assets and profile.get("backend") == "piper":
        from .voice import _expand_model_path

        legacy = _expand_model_path(profile.get("piper_model"))
        if not legacy or not Path(legacy).is_file():
            errors.append("legacy Piper model is not installed")
    if profile.get("reference_audio"):
        reference = profile["reference_audio"]
        for key in ("asset", "config_asset", "consent_record"):
            if reference.get(key):
                try:
                    path = _contained(asset_root(), reference[key])
                    checksum_key = "sha256" if key == "asset" else "config_sha256"
                    if assets:
                        if key == "consent_record":
                            if not path.is_file():
                                errors.append(
                                    "reference audio consent record must exist as a file under the asset root"
                                )
                        elif not path.is_file() or sha256_of_file(path) != reference[checksum_key]:
                            errors.append(
                                "reference audio/config asset missing or checksum mismatch"
                            )
                except OCFError as exc:
                    errors.append(str(exc))
        if reference["consent_status"] not in {
            "self-recorded",
            "authorized-contributor",
        } or not reference.get("consent_record"):
            errors.append(
                "reference audio requires explicit authorization metadata and a consent record"
            )
        if profile.get("locale") and reference["locale"] != profile["locale"]:
            errors.append("reference audio locale differs from profile locale")
    if (
        profile.get("voice_kind") == "cloned"
        or profile.get("customization_method") == "trained-adapted"
    ) and (
        profile.get("consent_status") not in {"self-recorded", "authorized-contributor"}
        or not profile.get("consent_record")
    ):
        errors.append(
            "cloned/trained voice requires explicit authorization metadata and a consent record"
        )
    if errors:
        raise OCFError("voice profile: " + " | ".join(errors))
    from .voice_capabilities import profile_capability

    capability = profile_capability(profile)
    return {
        "id": profile["id"],
        "valid": True,
        "assets_checked": assets,
        "distribution_permission": profile.get("distribution_permission", "unknown"),
        "available": capability["available"] if assets else False,
        "inference_supported": capability["inference_supported"],
        "inference_verified": False,
        "blockers": capability["blockers"] + ([] if assets else ["Assets have not been checked."]),
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
    config = read_json_object(config_path)
    _validate_finite_json(config, "Piper configuration")
    if not isinstance(config.get("language"), dict) or not isinstance(config.get("audio"), dict):
        raise OCFError("Piper configuration requires language/audio objects")
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
        "customization_method": "installed-model",
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
        _copy_verified(source, _contained(root, destination.name), sha256_of_file(source))
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


def profile_availability(profile: dict) -> dict:
    """Safe inventory status for installed, missing and unsupported profiles."""
    from .voice_capabilities import profile_capability

    result = profile_capability(profile)
    try:
        validate_profile(profile)
    except OCFError as exc:
        result["blockers"].append(str(exc))
    result["available"] = not result["blockers"]
    return result


def _redacted(value):
    if isinstance(value, dict):
        if any(_redacted(key) != key for key in value):
            raise OCFError("portable metadata keys contain private absolute paths")
        return {
            key: _redacted(item)
            for key, item in value.items()
            if key not in {"consent_record", "piper_model", "required_assets", "notes"}
        }
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r"(https?://[^\s]+)|(?:[A-Za-z]:[\\/]|(?<![A-Za-z0-9._/-])/|~[\\/]|\\\\|\$[A-Za-z_{])[^\s]+",
            lambda match: match[1] or "[redacted-path]",
            value,
        )
    return value


def _profile_assets(profile: dict) -> list[tuple[str, str]]:
    assets = []
    if profile.get("model"):
        model = profile["model"]
        assets.append((model["asset"], model["sha256"]))
        if profile["backend"] == "piper":
            if not model.get("config_sha256"):
                raise OCFError("portable Piper assets require a configuration checksum")
            assets.append((model["asset"] + ".json", model["config_sha256"]))
    if profile.get("reference_audio"):
        reference = profile["reference_audio"]
        assets.append((reference["asset"], reference["sha256"]))
        if reference.get("config_asset"):
            assets.append((reference["config_asset"], reference["config_sha256"]))
    identities = {}
    for asset, checksum in assets:
        if asset in identities and identities[asset] != checksum:
            raise OCFError("conflicting checksums declared for the same portable asset")
        identities[asset] = checksum
    return list(identities.items())


def export_profile(query: str | dict, output: Path, include_assets: bool = False) -> dict:
    """Export redacted JSON metadata; copying weights/reference audio is opt-in."""
    from .indexes import load_voice_profiles
    from .voice import _expand_model_path

    if isinstance(query, dict):
        profile = deepcopy(query)
    else:
        matches = [
            p
            for p in load_voice_profiles()
            if any(
                str(p.get(key, "")).casefold() == query.casefold() for key in ("id", "slug", "name")
            )
        ]
        if len(matches) != 1:
            raise OCFError("select one unambiguous voice profile ID, slug or name")
        profile = deepcopy(matches[0])
    validate_profile(profile, assets=False)
    sources = {}
    if profile.get("piper_model") and not profile.get("model"):
        legacy = Path(_expand_model_path(profile["piper_model"]))
        config = Path(str(legacy) + ".json")
        if not legacy.is_file() or not config.is_file():
            raise OCFError("legacy model must be installed to export a portable checksum identity")
        checksum = sha256_of_file(legacy)
        profile["model"] = {
            "asset": checksum + ".onnx",
            "sha256": checksum,
            "config_sha256": sha256_of_file(config),
            "version": "legacy-local",
        }
        sources[checksum + ".onnx"] = legacy
        sources[checksum + ".onnx.json"] = config
    elif (
        profile.get("model")
        and profile["backend"] == "piper"
        and not profile["model"].get("config_sha256")
    ):
        config = _contained(asset_root(), profile["model"]["asset"] + ".json")
        if not config.is_file():
            raise OCFError("configuration must be installed to export its checksum")
        profile["model"]["config_sha256"] = sha256_of_file(config)
    assets = _profile_assets(profile)
    reference_text = profile.get("reference_audio", {}).get("reference_text")
    if reference_text is not None and _redacted(reference_text) != reference_text:
        raise OCFError(
            "reference transcript contains private paths; export cannot rewrite source wording"
        )
    profile = _redacted(profile)
    profile.setdefault("customization_method", "installed-model")
    profile["privacy"] = "shareable-metadata"
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise OCFError("profile export destination already exists; refusing overwrite")
    directory = output.with_name(output.stem + "-assets")
    transfers = []
    if include_assets:
        if directory.exists() or directory.is_symlink():
            raise OCFError("profile asset export directory already exists")
        for asset, checksum in assets:
            source = sources.get(asset) or _contained(asset_root(), asset)
            if not source.is_file() or sha256_of_file(source) != checksum:
                raise OCFError("export asset missing or checksum mismatch")
            relative = f"{directory.name}/{asset}"
            destination = _contained(output.parent, relative)
            transfers.append((source, destination, checksum, asset, relative))
    bundle = {
        "schema_version": "1.0",
        "kind": "ocf-voice-profile",
        "profile": profile,
        "consent_records_redacted": True,
        "assets": [
            {"asset": asset, "path": relative, "sha256": checksum}
            for _, _, checksum, asset, relative in transfers
        ],
    }
    _validate_finite_json(bundle, "portable profile")
    try:
        encoded = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except (ValueError, TypeError) as exc:
        raise OCFError(f"portable profile is not valid finite JSON: {exc}") from exc
    for source, destination, checksum, _, _ in transfers:
        _copy_verified(source, destination, checksum)
    write_text_atomic(output, encoded, overwrite=False)
    return {
        "path": str(output),
        "profile": profile,
        "assets_included": len(transfers),
        "inference_verified": False,
        "consent_records_redacted": True,
    }


def import_profile(
    path: Path,
    *,
    include_assets: bool = False,
    voice_id: str | None = None,
    consent_record: str | None = None,
) -> dict:
    """Import portable metadata and optionally verified assets into the private store.

    Private consent paths are never transferred: reattach a local consent reference
    explicitly for cloned/reference/trained profiles. Existing profiles are not replaced.
    """
    from .indexes import load_voice_profiles
    from .validators import _load_schema, validate_against_schema

    path = Path(path)
    bundle = read_json_object(path)
    _validate_finite_json(bundle, "portable profile")
    if (
        bundle.get("kind") != "ocf-voice-profile"
        or bundle.get("schema_version") != "1.0"
        or not isinstance(bundle.get("profile"), dict)
    ):
        raise OCFError("not an OCF portable voice profile bundle")
    profile = deepcopy(bundle["profile"])
    # The portable format cannot smuggle legacy absolute paths or private records.
    if profile != _redacted(profile):
        raise OCFError("portable profile contains private paths or nonportable fields")
    if voice_id:
        profile["id"] = voice_id
        profile["slug"] = voice_id.lower()
    errors = validate_against_schema(profile, _load_schema("voice-profile.schema.json"))
    if errors:
        raise OCFError("portable profile schema: " + " | ".join(errors))
    if consent_record:
        profile["consent_record"] = consent_record
        if profile.get("reference_audio"):
            profile["reference_audio"]["consent_record"] = consent_record
    profile["privacy"] = "private"
    validate_profile(profile, assets=False)
    if any(p["id"] == profile["id"] for p in load_voice_profiles()):
        raise OCFError("voice ID already exists; refusing replacement")
    destination = work_path("cache", "voices", "profiles", profile["id"] + ".yaml")
    if destination.exists() or destination.is_symlink():
        raise OCFError("private voice profile already exists")
    expected = dict(_profile_assets(profile))
    entries = bundle.get("assets", [])
    if not isinstance(entries, list):
        raise OCFError("bundle assets must be a list")
    transfers, seen = [], set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"asset", "path", "sha256"}
            or not all(isinstance(v, str) for v in entry.values())
        ):
            raise OCFError("invalid portable asset entry")
        asset, checksum = entry["asset"], entry["sha256"]
        if asset in seen or expected.get(asset) != checksum:
            raise OCFError("bundle asset identity/checksum differs from profile")
        seen.add(asset)
        _portable_relative(entry["path"])
        if include_assets:
            source = _contained(path.parent, entry["path"])
            target = _contained(asset_root(), asset)
            if not source.is_file() or sha256_of_file(source) != checksum:
                raise OCFError("bundle asset missing or checksum mismatch")
            if target.exists() and (not target.is_file() or sha256_of_file(target) != checksum):
                raise OCFError("existing model asset differs; refusing replacement")
            transfers.append((source, target, checksum))
    if include_assets and seen != set(expected):
        raise OCFError("asset copy requested but bundle does not contain every required asset")
    copied = 0
    if include_assets:
        for source, target, checksum in transfers:
            copied += _copy_verified(source, target, checksum)
        validate_profile(profile)
    write_text_atomic(destination, yaml_safe_dump(profile), overwrite=False)
    return {
        "path": str(destination),
        "profile": profile,
        "assets_copied": copied,
        "assets_reused": len(transfers) - copied if include_assets else 0,
        "availability": profile_availability(profile),
        "inference_verified": False,
    }


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
