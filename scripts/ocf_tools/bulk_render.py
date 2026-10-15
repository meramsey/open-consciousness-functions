"""Explicit bounded bulk auditions with verified resumability and unique outputs."""

from __future__ import annotations

import json
from pathlib import Path

from .complete_session import render_complete_session
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .narration_first import _voice_profile
from .paths import work_path
from .session_plans import digest, source_plan
from .speech_cache import STATS, enabled, voice_identity
from .utils import OCFError, sha256_of_file, write_text_atomic


def verified_output(receipt: dict, key: str) -> bool:
    """Trust only the completed manifest plus every contained artifact checksum."""
    try:
        if receipt["key"] != key:
            return False
        root = Path(receipt["output_directory"]).resolve()
        manifest_path = root / "session-report.json"
        if sha256_of_file(manifest_path) != receipt["manifest_sha256"]:
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("artifacts") or "wav" not in manifest["artifacts"]:
            return False
        for artifact in manifest["artifacts"].values():
            path = (root / artifact["path"]).resolve()
            if not path.is_relative_to(root) or path.stat().st_size != artifact["size_bytes"]:
                return False
            if sha256_of_file(path) != artifact["sha256"]:
                return False
        return True
    except (OSError, KeyError, ValueError, TypeError):
        return False


def render_many(
    function_ids: list[str] | None,
    *,
    voice: str,
    locale: str = "en-US",
    pacing: str = "sleep",
    dry_run: bool = False,
    force: bool = False,
    resume: bool = True,
    sample_rate: int = 44100,
) -> dict:
    ids = sorted(
        set(function_ids if function_ids is not None else [r.id for r in load_all_functions()])
    )
    if not ids:
        raise OCFError("no functions selected")
    statuses = []
    # One full-session job at a time: full PCM sessions are memory intensive.
    # Separate invocations remain safe through unique auditions/atomic caches.
    for owner in ids:
        try:
            plan, shared, _ = source_plan(owner, locale)
            if dry_run:
                statuses.append(
                    {"function_id": owner, "status": "planned", "plan_sha256": digest(plan)}
                )
                continue
            _, spec = _voice_profile(voice, locale, LocaleCatalog())
            identity = {
                "plan": plan,
                "shared": shared,
                "voice": voice_identity(spec),
                "pacing": pacing,
                "sample_rate": sample_rate,
                "renderer": {
                    name: sha256_of_file(Path(__file__).with_name(name))
                    for name in (
                        "complete_session.py",
                        "audio_build.py",
                        "semantic_dsp.py",
                        "narration_pacing.py",
                        "narration_first.py",
                    )
                },
            }
            key = digest(identity)
            receipt_path = work_path("cache", "bulk-renders", key + ".json")
            previous = {}
            if resume and not force:
                try:
                    previous = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
                if verified_output(previous, key):
                    statuses.append(
                        {
                            "function_id": owner,
                            "status": "skipped-verified",
                            "output_directory": previous["output_directory"],
                        }
                    )
                    continue
            with enabled(not force):
                result = render_complete_session(
                    owner, locale=locale, voice=voice, pacing=pacing, sample_rate=sample_rate
                )
            root = Path(result["output_directory"])
            receipt = {
                "key": key,
                "output_directory": str(root.resolve()),
                "manifest_sha256": sha256_of_file(root / "session-report.json"),
            }
            if not verified_output(receipt, key):
                raise OCFError(f"render artifact verification failed for {owner}")
            write_text_atomic(receipt_path, json.dumps(receipt, sort_keys=True) + "\n")
            statuses.append(
                {"function_id": owner, "status": "rendered", "output_directory": str(root)}
            )
        except (OCFError, OSError, ValueError) as exc:
            statuses.append({"function_id": owner, "status": "failed", "error": str(exc)})
        # Persist after every function; interruption keeps completed receipts.
        if not dry_run:
            write_text_atomic(
                work_path("logs", "bulk-render-latest.json"), json.dumps(statuses, indent=2) + "\n"
            )
    return {
        "workers": 1,
        "speech_cache": dict(STATS),
        "dry_run": dry_run,
        "results": statuses,
        "failed": sum(row["status"] == "failed" for row in statuses),
    }
