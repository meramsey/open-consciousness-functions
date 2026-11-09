"""Standalone reviewed Preparation Learning, without a function identity.

Callers must supervise production renders independently. This module only owns
composition, output reservation, verification and atomic publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from . import audio_build, semantic_dsp
from .locale import iter_events, resolve_document
from .mix_profiles import load_mix_profile
from .session import compose, load_template
from .utils import OCFError, sha256_of_file

TEMPLATE = "OCF-TPL-SESSION-PREP-LEARN-002"


def plan(
    *, locale="en-US", enabled_stages=(), affirmation=None, native_speed=False, pacing_profile=None
):
    template = load_template(TEMPLATE)
    document = compose(
        template,
        {},
        title=template["name"],
        locale=locale,
        enabled_stages=list(enabled_stages),
        affirmation=affirmation,
        pacing_profile=pacing_profile,
    )
    document = resolve_document(document, locale, strict=True)
    if native_speed:
        for pacing in document.get("narration_pacing", {}).get("profiles", {}).values():
            pacing["rate_scale"] = 1.0
            if "countdown_rate_scale_end" in pacing:
                pacing["countdown_rate_scale_end"] = 1.0
    if document.get("function_id"):
        raise OCFError("standalone Learning must not own a function")
    events = {event["id"]: event for event in iter_events(document)}
    waits = [events["learning-intro.speech"]["timing"]["pause_after"]]
    waits += [events[f"ten-rest-{i}.hold"]["timing"]["pause_after"] for i in range(1, 4)]
    waits += [events[f"open-{i}.ready"]["timing"]["pause_after"] for i in range(1, 4)]
    if waits != [60] * 4 + [90] * 3:
        raise OCFError("Learning practice allocation changed")
    return {
        "document": document,
        "dsp": semantic_dsp.load_profile(template["dsp_profile"]),
        "practice_seconds": sum(waits),
        "locale": locale,
    }


def verify_timing(document, rendered):
    """Require all composed events, three complete visits and measured holds."""
    expected = {event["id"]: event for event in iter_events(document)}
    rows = rendered.get("event_timing", [])
    actual = {row["id"]: row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise OCFError("Learning measured event ledger differs from its composition")
    from .timing import schedule_timeline

    recomputed = schedule_timeline(
        document, {key: row["speech_duration"] for key, row in actual.items()}
    )
    for row in recomputed:
        if any(
            abs(float(row[field]) - float(actual[row["id"]][field])) > 0.002
            for field in ("at", "end")
        ):
            raise OCFError("Learning measured anchors or practice holds differ from composition")
    transitions = rendered.get("semantic_dsp", {}).get("transitions", [])
    if [row["to"] for row in transitions] != ["focus-11", "focus-10"] * 3:
        raise OCFError("Learning requires exactly three complete Eleven visits")
    cues = rendered.get("narration_timing", {}).get("cues", [])
    if not rendered.get("narration_timing", {}).get("measured") or not cues:
        raise OCFError("Learning requires measured narration")
    covered = {}
    for cue in cues:
        source_ids = cue.get("source_ids", [cue["id"]])
        if len(source_ids) != 1 or source_ids[0] in covered:
            raise OCFError("Learning narration identity is ambiguous")
        covered[source_ids[0]] = " ".join(cue["spoken_text"].split())
    spoken = {
        key: " ".join(event.get("text", "").split())
        for key, event in expected.items()
        if event.get("text", "").strip()
    }
    if covered != spoken:
        raise OCFError("Learning rendered wording differs from resolved composition")
    return {
        "event_count": len(actual),
        "visits": 3,
        "practice_seconds": 510,
        "measured": True,
        "human_listening_approved": False,
    }


def render(
    *,
    output,
    voice,
    mix_profile=None,
    locale="en-US",
    enabled_stages=(),
    affirmation=None,
    dry_run=False,
    native_speed=False,
    pacing_profile=None,
    backend_defaults=True,
):
    """Render using existing OCF APIs; retain failed staging and refuse overwrite."""
    from . import backend_defaults as defaults
    from .complete_session import _probe_audio, _stereo_metrics, _verify_decode
    from .dev_jobs import lock
    from .listener_text import write_listener_text
    from .paths import REPO_ROOT, workspace_temp_directory
    from .voice import resolve_backend
    from .voice_packs import persistent_worker

    resolved_voice = resolve_backend(voice, locale=locale)
    dsp = semantic_dsp.load_profile(load_template(TEMPLATE)["dsp_profile"])
    use_defaults = defaults.eligible(resolved_voice.get("name"), dsp, enabled=backend_defaults)
    if use_defaults and pacing_profile is None:
        pacing_profile = defaults.pacing_id(learning=True)
    if use_defaults and mix_profile is None:
        mix_profile = defaults.mix_profile()
    planned = plan(
        locale=locale,
        enabled_stages=enabled_stages,
        affirmation=affirmation,
        native_speed=native_speed,
        pacing_profile=pacing_profile,
    )
    profile = load_mix_profile({} if mix_profile is None else mix_profile)
    target = Path(output).expanduser().resolve()
    from .speech_cache import voice_identity

    identity = {
        "plan": planned,
        "mix_profile": profile,
        "voice": voice_identity(resolved_voice),
        "dsp_dependencies": semantic_dsp.dependency_identity(planned["dsp"]),
        "source_sha256": {
            str(path.relative_to(REPO_ROOT)): sha256_of_file(path)
            for root in (REPO_ROOT / "audio/templates", REPO_ROOT / "locales" / locale)
            for path in root.rglob("*.yaml")
        },
        "implementation_sha256": {
            path.name: sha256_of_file(path) for path in Path(__file__).parent.glob("*.py")
        },
    }
    identity_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if dry_run:
        return {
            "dry_run": True,
            "identity_sha256": identity_hash,
            "mix_profile": profile,
            **planned,
        }
    lock_id = hashlib.sha256(str(target).encode()).hexdigest()
    with lock("standalone-learning-" + lock_id, wait=False) as acquired:
        if not acquired or target.exists() or target.is_symlink():
            raise OCFError("Learning output is reserved or already exists")
        stage = workspace_temp_directory(prefix="ocf-learning-")
        document = planned["document"]
        with persistent_worker(voice):
            built = audio_build.build(
                "preparation-learning",
                document_override=document,
                manifest_override={
                    "title": "Preparation Learning",
                    "language": locale,
                    "background_audio": {"strategy": "none", "preset": None},
                },
                render_label="preparation-learning",
                out_root=stage,
                formats=["wav", "mp3"],
                voice=voice,
                background_gain=1.0,
                sample_rate=44100,
                locale=locale,
                strict=True,
                overwrite=False,
                dsp_profile=planned["dsp"],
                mix_profile=profile,
                retain_background_stem=True,
            )
        timing = verify_timing(document, built)
        master = stage / built["master"]["file"]
        probe = _probe_audio(master)
        if (probe["sample_rate"], probe["channels"]) != (44100, 2):
            raise OCFError("Learning master must be 44.1 kHz stereo")
        metrics = _stereo_metrics(master, sample_rate=44100)
        if metrics["clipped_sample_count"]:
            raise OCFError("Learning master contains clipped samples")
        _verify_decode(master)
        write_listener_text(built, built["master"]["duration"], stage / "transcript.txt")
        (stage / "source-identity.json").write_text(json.dumps(identity, indent=2))
        (stage / "plan.json").write_text(json.dumps(planned, indent=2))
        (stage / "render.json").write_text(json.dumps(built, indent=2))
        artifacts = {
            p.name: {"path": p.name, "size_bytes": p.stat().st_size, "sha256": sha256_of_file(p)}
            for p in stage.iterdir()
            if p.is_file() and not p.name.startswith(".")
        }
        receipt = {
            "status": "completed",
            "render_type": "standalone-preparation-learning",
            "render_identity_sha256": identity_hash,
            "timing": timing,
            "measurements": {**probe, **metrics},
            "artifacts": artifacts,
            "human_listening_approved": False,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        publication = target.parent / (".learning-publish-" + uuid4().hex)
        publication.mkdir(mode=0o700)
        for item in artifacts.values():
            destination = publication / item["path"]
            shutil.copyfile(stage / item["path"], destination)
            destination.chmod(0o600)
            if sha256_of_file(destination) != item["sha256"]:
                raise OCFError("Learning publication copy failed integrity verification")
        completion = publication / "completion.json"
        with completion.open("x") as stream:
            json.dump(receipt, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            raise OCFError("Learning publication destination became occupied")
        publication.rename(target)
        return receipt
