"""Render, export and privately package one versioned reference-V4 collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ocf_tools.audio_quality import measure_ebur128
from ocf_tools.audition_exports import export_audition
from ocf_tools.build_provenance import attach_audio_quality, attach_build_provenance
from ocf_tools.bulk_render import render_many
from ocf_tools.environment import discover_environment
from ocf_tools.indexes import load_voice_profiles
from ocf_tools.listener_packages import package_auditions, verify_package
from ocf_tools.paths import work_root
from ocf_tools.private_collection_index import build_private_collection_index
from ocf_tools.utils import OCFError, sha256_of_file


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _verified_export(path: Path, session_report: Path) -> bool:
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("kind") != "private-audition-export":
            return False
        if manifest["source_report"]["sha256"] != sha256_of_file(session_report):
            return False
        receipts = list(manifest["artifacts"].values())
        if manifest.get("cover"):
            receipts.append(manifest["cover"])
        listener_text = manifest.get("listener_text") or {}
        receipts.extend(listener_text.get("artifacts", {}).values())
        if listener_text.get("timing_receipt"):
            receipts.append(listener_text["timing_receipt"])
        for item in receipts:
            artifact = path / item["path"]
            if (
                not artifact.is_relative_to(path.resolve())
                or not artifact.is_file()
                or artifact.stat().st_size != item["size_bytes"]
            ):
                return False
            if sha256_of_file(artifact) != item["sha256"]:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run_collection(
    function_ids: list[str],
    *,
    voice: str,
    profile: str,
    version: str = "0.3.0",
    locale: str = "en-US",
    workers: int = 2,
    fresh_synthesis: bool = False,
) -> dict:
    root = work_root()
    status_path = (
        root / "agent-continuity" / f"REFERENCE_V4_V{version.replace('.', '_')}_STATUS.json"
    )
    status = json.loads(status_path.read_text(encoding="utf-8"))
    by_id = {row["function_id"]: row for row in status["functions"]}
    unknown = set(function_ids) - set(by_id)
    if unknown:
        raise OCFError(
            "requested function IDs are not in the durable edition inventory: "
            + ", ".join(sorted(unknown))
        )

    def progress(event):
        row = by_id.get(event.get("function_id"))
        if row is None:
            return
        phase = event["phase"]
        if phase == "function-start":
            row["status"] = "RENDERING"
        elif phase in {"function-blocked", "function-failed"}:
            row["status"] = "BLOCKED" if phase.endswith("blocked") else "FAILED"
            row["error"] = event.get("detail")
        elif phase == "function-skipped-verified":
            row["status"] = "SESSION_RENDER_VERIFIED"
        elif phase == "function-rendered":
            row["status"] = "SESSION_RENDER_VERIFIED"
        elif not phase.startswith("function-"):
            row["render_phase"] = phase
            return
        row["last_phase"] = phase
        status["active_function"] = event.get("function_id")
        status["updated_at"] = datetime.now(UTC).isoformat()
        _atomic_json(status_path, status)

    rendered = render_many(
        function_ids,
        voice=voice,
        locale=locale,
        pacing="sleep",
        resume=True,
        fresh_synthesis=fresh_synthesis,
        workers=workers,
        dsp_profile=profile,
        progress_callback=progress,
    )
    latest_by_id = {row["function_id"]: row for row in rendered["results"]}
    exports = []
    for function_id in function_ids:
        result = latest_by_id.get(function_id, {})
        row = by_id[function_id]
        if result.get("status") not in {"rendered", "skipped-verified"}:
            row["status"] = result.get("status", "BLOCKED").upper()
            row["technical_verification"] = result.get("error", "session renderer did not complete")
            continue
        session = Path(result["output_directory"]).resolve()
        session_report_path = session / "session-report.json"
        session_report = json.loads(session_report_path.read_text(encoding="utf-8"))
        export_path = (
            root
            / "renders"
            / f"amy-reference-v4-v{version}"
            / "verified-exports-locked-004"
            / function_id
        )
        if export_path.exists():
            if not _verified_export(export_path, session_report_path):
                row["status"] = "FAILED"
                row["technical_verification"] = (
                    "existing export is not a checksum-matching receipt; preserved without overwrite"
                )
                continue
        else:
            master_path = session / session_report["artifacts"]["wav"]["path"]
            edition_path = (
                root
                / "agent-continuity"
                / "reference-v4-config"
                / f"{function_id}-edition-{version}.json"
            )
            _atomic_json(
                edition_path,
                {
                    "schema_version": "1.0",
                    "kind": "private-audition",
                    "function_id": function_id,
                    "locale": locale,
                    "version": version,
                    "voice_profile_id": voice,
                    "master_sha256": sha256_of_file(master_path),
                    "session_report_sha256": sha256_of_file(session_report_path),
                    "publication_approval": False,
                    "human_listening_approval": None,
                    "background_variant": session_report["background_variant"],
                },
            )
            exported = export_audition(
                session,
                edition=edition_path,
                output=export_path,
                artwork_resolution=2400,
                lyrics=True,
            )
            master_info = session_report["artifacts"]["wav"]
            master = Path(master_info["path"])
            if not master.is_absolute():
                master = session / master
            quality = {
                "schema_version": "1.0",
                "function_id": function_id,
                "edition": version,
                "audio_sha256": master_info["sha256"],
                "media_duration_seconds": session_report["measurements"]["duration_seconds"],
                "sample_rate": session_report["measurements"]["sample_rate"],
                "channels": session_report["measurements"]["channels"],
                "sample_clipped_count": session_report["measurements"]["clipped_sample_count"],
                "rms_left_dbfs": session_report["measurements"]["left_rms_dbfs"],
                "rms_right_dbfs": session_report["measurements"]["right_rms_dbfs"],
                "background_continuity": session_report["background_continuity"],
                "ebur128": measure_ebur128(master),
                "transitions": session_report["state_transitions"],
                "ending_fade_seconds": session_report["mix"]["ending_fade_seconds"],
                "sleep_reinforcement_gain_db": -24,
                "mastering_target_applied": False,
                "human_listening_approval": None,
                "publication_authorized": False,
            }
            attach_audio_quality(export_path, quality)
            profiles = load_voice_profiles()
            voice_profile = next(item for item in profiles if item["id"] == voice)
            model = voice_profile.get("model", {})
            piper_runtime = discover_environment(voice_profile=voice_profile)["tools"]["piper"].get(
                "runtime", {}
            )
            source_files = (
                "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-014.json",
                "audio/templates/sessions/OCF-TPL-SESSION-HPLUS-LOCKED-004.yaml",
                "audio/templates/pacing/OCF-PACING-HPLUS-LOCKED-004.yaml",
                "audio/background/state-profiles/OCF-DSP-HPLUS-LOCKED-002.yaml",
                "scripts/ocf_tools/complete_session.py",
                "scripts/ocf_tools/voice.py",
                "scripts/ocf_tools/listener_text.py",
                "scripts/ocf_tools/audition_exports.py",
                "scripts/ocf_tools/bulk_render.py",
                "scripts/ocf_tools/environment.py",
                "scripts/ocf_tools/build_provenance.py",
                "scripts/ocf_tools/private_collection_index.py",
                "scripts/tools/render_private_reference_v4.py",
            )
            source_hashes = {
                name: sha256_of_file(Path(__file__).resolve().parents[2] / name)
                for name in source_files
            }
            attach_build_provenance(
                export_path,
                {
                    "schema_version": "1.0",
                    "edition": version,
                    "function_id": function_id,
                    "function_title": session_report["title"],
                    "locale": locale,
                    "activation_cue": exported["manifest"]["function_content"].get(
                        "primary_command"
                    ),
                    "versioned_template": session_report["template"],
                    "versioned_pacing_profile": session_report.get("session_pacing_profile"),
                    "dsp_profile": {
                        key: session_report.get("dsp_profile", {}).get(key)
                        for key in (
                            "profile_id",
                            "profile_version",
                            "curve",
                            "default_background_state",
                            "ending_fade_seconds",
                        )
                    }
                    | {"measured_transitions": session_report["state_transitions"]},
                    "voice_profile_id": voice,
                    "voice_model_identifier": model.get("identifier"),
                    "voice_model_revision": model.get("version"),
                    "voice_model_sha256": model.get("sha256"),
                    "voice_config_sha256": model.get("config_sha256"),
                    "voice_backend_version": {
                        "python": piper_runtime.get("python_version"),
                        "piper_tts": piper_runtime.get("package_version"),
                    },
                    "fresh_synthesis": True,
                    "reference_background_variant": session_report["background_variant"],
                    "reference_background_source_sha256": {
                        "focus10": "18c71de3fa72e3252147fc9d3cae2f360304fcc4ef45ce5f96cca4590a4bb02a",
                        "focus11": "6d0feff8c0e02282b8d8098d1eda126029159a56f8b1b447527a7e80f8c3312e",
                    },
                    "narration_resources": [
                        {
                            key: item.get(key)
                            for key in ("key", "locale", "version", "status", "text_sha256")
                        }
                        for item in session_report.get("narration_resources", [])
                    ],
                    "listener_timing_receipt_sha256": exported["manifest"]["listener_text"][
                        "timing_receipt"
                    ]["sha256"],
                    "session_report_sha256": sha256_of_file(session_report_path),
                    "git_base_sha": "dc01ecc9bc4dd93ef05bbd4c1a8cdd35f035b815",
                    "git_worktree_branch": "engineering/reference-v4-cp-20261025",
                    "source_component_sha256": source_hashes,
                    "artifacts": {
                        fmt: item["sha256"]
                        for fmt, item in exported["manifest"]["artifacts"].items()
                        if fmt in {"flac", "mp3"}
                    },
                    "publication_authorized": False,
                    "human_listening_approval": None,
                },
            )
        row.update(
            {
                "title": session_report["title"],
                "status": "EXPORTED_PENDING_PACKAGE",
                "technical_verification": "FLAC/MP3/lyrics/artwork checksummed export verified",
                "session_report": str(session_report_path),
                "session_report_sha256": sha256_of_file(session_report_path),
                "export_manifest_sha256": sha256_of_file(export_path / "manifest.json"),
                "duration_seconds": session_report["measurements"]["duration_seconds"],
                "human_listening": "PENDING",
                "publication": "NOT_AUTHORIZED",
            }
        )
        status["updated_at"] = datetime.now(UTC).isoformat()
        _atomic_json(status_path, status)

    export_root = root / "renders" / f"amy-reference-v4-v{version}" / "verified-exports-locked-004"
    exports = []
    for function_id, row in by_id.items():
        source_report = Path(row["session_report"]) if row.get("session_report") else None
        export_path = export_root / function_id
        if source_report and _verified_export(export_path, source_report):
            exports.append(export_path)

    package_doc = None
    if exports:
        export_manifests = [sha256_of_file(path / "manifest.json") for path in exports]
        collection_id = hashlib.sha256("\n".join(sorted(export_manifests)).encode()).hexdigest()[
            :12
        ]
        package_root = (
            root / "renders" / f"amy-reference-v4-v{version}" / "packages" / collection_id
        )
        package_doc = package_auditions(exports, package_root, resume=package_root.exists())
        verified = verify_package(package_root)
        package_receipt = {
            "package_path": str(package_root),
            "package_manifest_sha256": sha256_of_file(package_root / "package.json"),
            "artifact_count": len(verified["artifacts"]),
            "function_ids": [row["function_id"] for row in verified["sessions"]],
            "human_listening_approval": None,
            "publication_authorized": False,
        }
        _atomic_json(
            root / "agent-continuity" / f"REFERENCE_V4_V{version.replace('.', '_')}_PACKAGE.json",
            package_receipt,
        )
        index_root = root / "renders" / f"amy-reference-v4-v{version}" / "indexes" / collection_id
        build_private_collection_index(package_root, index_root, progress=status_path)
        for function_id in package_receipt["function_ids"]:
            by_id[function_id]["status"] = "TECHNICALLY_VERIFIED_IN_PRIVATE_PACKAGE"
            by_id[function_id]["technical_verification"] = (
                "package manifest and every artifact checksum verified"
            )
            by_id[function_id]["package_manifest_sha256"] = package_receipt[
                "package_manifest_sha256"
            ]
        status["active_function"] = None
        status["package_path"] = str(package_root)
        status["dashboard_path"] = str(index_root / "index.html")
        status["verified_count"] = len(package_receipt["function_ids"])
        status["human_listening_approval"] = None
        status["publication_authorized"] = False
        status["updated_at"] = datetime.now(UTC).isoformat()
        _atomic_json(status_path, status)
    return {"render": rendered, "export_count": len(exports), "package": package_doc}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("function_ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--voice", default="OCF-VOICE-9003")
    parser.add_argument(
        "--profile", required=True, help="explicit private F10/F11 DSP profile YAML"
    )
    parser.add_argument("--version", default="0.3.0")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--fresh-synthesis", action="store_true")
    args = parser.parse_args(argv)
    ids = args.function_ids
    if args.all:
        if ids:
            parser.error("--all cannot be combined with explicit IDs")
        from ocf_tools.indexes import load_all_functions

        status_path = (
            work_root()
            / "agent-continuity"
            / f"REFERENCE_V4_V{args.version.replace('.', '_')}_STATUS.json"
        )
        status = json.loads(status_path.read_text(encoding="utf-8"))
        completed = {
            row["function_id"]
            for row in status["functions"]
            if row.get("status") == "TECHNICALLY_VERIFIED_IN_PRIVATE_PACKAGE"
        }
        ids = [record.id for record in load_all_functions() if record.id not in completed]
    if not ids:
        if args.all:
            print("All functions are already technically verified in this private edition.")
            return 0
        parser.error("supply function IDs or --all")
    result = run_collection(
        ids,
        voice=args.voice,
        profile=args.profile,
        version=args.version,
        workers=args.workers,
        fresh_synthesis=args.fresh_synthesis,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["render"]["failed"] or result["render"].get("blocked", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
