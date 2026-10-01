"""Reusable semantic stages and replaceable auditory-cue bindings.

No listener prose, carrier values, cue generation or playback lives here.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .indexes import load_yaml_file
from .locale import iter_events
from .paths import REPO_ROOT
from .utils import OCFError
from .validators import _load_schema, validate_against_schema

STAGES_DIR = REPO_ROOT / "audio" / "templates" / "stages"
CUE_PROFILES_DIR = REPO_ROOT / "audio" / "cues" / "profiles"
DEFAULT_CUE_PROFILE = "OCF-CUE-PROFILE-DEFAULT"


def _load_record(reference: str, directory: Path, schema: str) -> dict:
    candidate = Path(reference).expanduser()
    path = candidate if candidate.is_file() else directory / f"{reference}.yaml"
    if not path.is_file():
        raise OCFError(f"record not found: {reference} (looked in {directory})")
    data = load_yaml_file(path)
    problems = validate_against_schema(data, _load_schema(schema))
    if problems:
        raise OCFError(f"{path}: " + "; ".join(problems))
    return data


def load_stage(reference: str) -> dict:
    stage = _load_record(reference, STAGES_DIR, "session-stage.schema.json")
    ids = [event.get("id") for event in stage["events"]]
    if any(not identifier for identifier in ids) or len(ids) != len(set(ids)):
        raise OCFError(f"stage {stage['id']} needs unique local event ids")
    return stage


def stage_events(stage: dict, instance: str, *, start: float = 0,
                 after: str | None = None, previous: str | None = None) -> list[dict]:
    """Namespace local IDs/references; attach a stage to a semantic anchor."""
    events = []
    local_ids = {event["id"] for event in stage["events"]}
    for original in stage["events"]:
        event = deepcopy(original)
        event["id"] = f"{instance}.{original['id']}"
        if "after" in event:
            target = event["after"]
            if target not in local_ids:
                raise OCFError(f"stage {stage['id']}: unknown local anchor {target}")
            event["after"] = f"{instance}.{target}"
            event.setdefault("offset", 0)
        elif after is not None:
            target = previous if after == "$previous" else after
            if not target:
                raise OCFError(f"stage {instance}: no previous semantic anchor")
            event["after"] = target
            event["offset"] = float(event.pop("at", 0))
            event.setdefault("timing", {}).setdefault("anchor", "event-end")
        else:
            event["at"] = start + float(event.get("at", 0))
        events.append(event)
    return events


def load_cue_profile(reference: str = DEFAULT_CUE_PROFILE) -> dict:
    return _load_record(reference, CUE_PROFILES_DIR, "cue-profile.schema.json")


def bind_document_cues(doc: dict, profile: dict | None = None) -> list[dict]:
    """Return bindings, not audio. Unconfigured identities are explicit errors."""
    profile = profile or load_cue_profile(doc.get("cue_profile") or DEFAULT_CUE_PROFILE)
    bindings = []
    for event in iter_events(doc):
        identity = event.get("auditory_cue")
        if not identity:
            continue
        if identity not in profile["bindings"]:
            raise OCFError(f"event {event['id']}: auditory cue {identity!r} is unbound")
        binding = deepcopy(profile["bindings"][identity])
        if binding["mode"] == "asset" and not (REPO_ROOT / binding["file"]).is_file():
            raise OCFError(f"cue {identity}: asset not found: {binding['file']}")
        bindings.append({"event_id": event["id"], "semantic": event.get("semantic"),
                         "identity": identity, "profile": profile["id"], "binding": binding})
    return bindings
