"""Pure structured preflight: agents choose intent, OCF validates declarative choices."""

from __future__ import annotations

from pathlib import Path

from .indexes import load_yaml_file
from .locale import iter_events, resolve_document
from .session import compose, load_template
from .utils import OCFError
from .validators import _load_schema, validate_against_schema


def plan(request: dict, base: Path = Path(".")) -> dict:
    errors = validate_against_schema(request, _load_schema("authoring-plan.schema.json"))
    if errors:
        raise OCFError("authoring plan: " + " | ".join(errors))
    template = load_template(request["template"])
    if (
        request.get("function_id")
        and template.get("function_id")
        and request["function_id"] != template["function_id"]
    ):
        raise OCFError("authoring plan function does not own the selected fixed-function template")
    if request.get("voice"):
        from .voice import resolve_backend

        resolve_backend(request["voice"], locale=request["locale"])
    slots = {
        key: (base / path).read_text(encoding="utf-8")
        for key, path in request.get("slots", {}).items()
    }
    doc = compose(
        template,
        slots,
        title=template["name"],
        function_id=request.get("function_id"),
        enabled_stages=request.get("enabled_stages", []),
        affirmation=request.get("affirmation"),
        custom_affirmation_locale=request.get("custom_affirmation_locale"),
        locale=request["locale"],
    )
    resolved = resolve_document(doc, request["locale"], strict=True)
    events = list(iter_events(resolved))
    if request.get("dsp_profile"):
        from .semantic_dsp import load_profile

        profile = load_profile(request["dsp_profile"])
        required = {profile["initial_state"]}
        for event in events:
            directive = (event.get("dsp") or {}).get("state")
            if isinstance(directive, str):
                required.add(directive)
            elif isinstance(directive, dict):
                required.update(value for key, value in directive.items() if key in ("from", "to"))
        if required - profile["states"].keys():
            raise OCFError(
                "authoring DSP profile lacks required state bindings: "
                + ", ".join(sorted(required - profile["states"].keys()))
            )
    if request["narration_source"] != "tts":
        package = load_yaml_file(base / request["recordings"])
        problems = validate_against_schema(package, _load_schema("narration-package.schema.json"))
        if problems or package["locale"] != request["locale"]:
            raise OCFError("recording package schema/locale does not match the authoring plan")
        wanted = {event["id"] for event in events if event.get("text", "").strip()}
        if wanted != set(package["recordings"]):
            raise OCFError(
                "recording package does not match this session's spoken event occurrences"
            )
    return {
        "schema_version": "1.0",
        "valid": True,
        "dry_run": True,
        "template_id": template["id"],
        "template_version": template.get("version"),
        "content_status": template.get("content_status", "unknown"),
        "human_review": "required"
        if template.get("content_status") != "reviewed"
        else "recorded template status; no new approval",
        "locale": request["locale"],
        "function_id": doc.get("function_id"),
        "narration_source": request["narration_source"],
        "spoken_events": sum(bool(event.get("text", "").strip()) for event in events),
        "semantic_events": [
            {
                "id": event["id"],
                "semantic": event.get("semantic"),
                "narration_key": event.get("narration_key"),
            }
            for event in events
        ],
        "target_duration_s": request.get("target_duration_s"),
        "duration_status": "requires measured speech and explicit timing design; no automatic stretching",
        "effects": "no audio, files, model download, cue playback or wording generation",
    }
