"""Separated evidence/specification/design/binding records with no source runtime dependency."""

from __future__ import annotations

from pathlib import Path

from .indexes import load_all_functions, load_yaml_file
from .paths import REPO_ROOT
from .utils import OCFError

CONTENT_DIR = REPO_ROOT / "function-content"
LAYERS = {
    "evidence": "function-evidence",
    "specifications": "function-specification",
    "decisions": "function-decisions",
    "bindings": "function-binding",
}
BLOCKS = (
    "purpose",
    "opener",
    "main",
    "association",
    "rehearsal",
    "future_use",
    "suspend_cancel_reset",
    "closer",
    "consolidation",
    "handoff",
    "safety_claims",
)


def validate_layers(layers: dict, function_id: str) -> list[str]:
    from .validators import _load_schema, validate_against_schema

    errors = []
    for layer, data in layers.items():
        if layer not in LAYERS:
            errors.append(f"unknown content layer: {layer}")
            continue
        errors += [
            f"{layer}: {error}"
            for error in validate_against_schema(data, _load_schema(LAYERS[layer] + ".schema.json"))
        ]
        if data.get("function_id") != function_id:
            errors.append(f"{layer}: function identity mismatch")
    if errors:
        return errors
    evidence = layers.get("evidence", {})
    sources = {source["sha256"]: source for source in evidence.get("sources", [])}
    observations = evidence.get("observations", [])
    identifiers = [item["id"] for item in observations]
    if len(set(identifiers)) != len(identifiers):
        errors.append("duplicate observation identity")
    for observation in observations:
        source = sources.get(observation["source_sha256"])
        if source is None:
            errors.append("observation refers to unknown source fingerprint")
        elif observation["scope"] == "historical" and (
            source["evidence_class"] not in ("source_transcript", "partial_source_transcript")
            or source["authentication"] != "authenticated"
        ):
            errors.append(
                "historical assertion requires authenticated source evidence; a mockup/design choice cannot establish it"
            )
    for block in layers.get("specifications", {}).get("blocks", {}).values():
        if set(block["evidence_refs"]) - set(identifiers):
            errors.append("specification references unknown evidence observation")
    review = layers.get("specifications", {}).get("analysis_review")
    if review:
        extent = review["source_extent"]
        locators = [extent] + [
            locator for answer in review["sections"].values() for locator in answer["locators"]
        ]
        for locator in locators:
            source = sources.get(locator["source_sha256"])
            if source is None or source["path"] != locator["file"]:
                errors.append("review locator references unknown/mismatched source identity")
            if "start_line" in locator and (
                locator["end_line"] < locator["start_line"]
                or locator["end_line"] > extent["end_line"]
            ):
                errors.append("review locator has invalid/incomplete source range")
        if extent["start_line"] != 1:
            errors.append("completed review must inspect the full available source from line1")
    binding = layers.get("bindings", {})
    if binding.get("session_templates"):
        from .session import load_template

        for reference in binding["session_templates"]:
            try:
                template = load_template(reference)
                if template.get("function_id") != function_id:
                    errors.append("template binding has a different function identity")
            except OCFError as exc:
                errors.append(str(exc))
    if binding.get("narration_resources"):
        from .locale import LocaleCatalog

        catalog = LocaleCatalog()
        for resource in binding["narration_resources"]:
            pack = catalog.packs.get(resource["locale"])
            if pack is None or pack.get(resource["key"]) is None:
                errors.append("binding refers to an unavailable locale resource")
    return errors


def load_layers(function_id: str, root: Path | None = None) -> dict:
    layers = {}
    for layer in LAYERS:
        path = (root or CONTENT_DIR) / layer / f"{function_id}.yaml"
        if path.is_file():
            layers[layer] = load_yaml_file(path)
    errors = validate_layers(layers, function_id)
    if errors:
        raise OCFError("function content: " + " | ".join(errors))
    return layers


def discover(record) -> dict:
    layers = load_layers(record.id)
    spec = layers.get("specifications")
    bindings = layers.get("bindings", {})
    return {
        "function_id": record.id,
        "title": record.canonical_name,
        "purpose": record.data["purpose"]["summary"],
        "activation": record.data["canonical"]["command"],
        "status": record.data["status"],
        "content_maturity": spec["maturity"] if spec else None,
        "human_review": spec["human_review"] if spec else "unknown",
        "extraction_status": spec["extraction_status"] if spec else "unknown",
        "states": spec["states"] if spec else None,
        "preparation": spec["preparation"] if spec else None,
        "session_templates": bindings.get("session_templates", []),
        "locales": sorted({item["locale"] for item in bindings.get("narration_resources", [])}),
        "narration_resources": bindings.get("narration_resources", []),
        "duration": bindings.get("duration"),
        "voice_sources": bindings.get("voice_sources"),
        "background": record.data["audio"]["background_audio"],
        "source_availability": record.source_availability,
        "evidence_classes": sorted(
            {item["evidence_class"] for item in layers.get("evidence", {}).get("sources", [])}
        ),
        "safety": record.data["safety"],
        "claim_review": "pending-source-review",
        "layers": list(layers),
    }


def validate_library() -> list[str]:
    errors = []
    known = {record.id for record in load_all_functions()}
    for layer in LAYERS:
        for path in (CONTENT_DIR / layer).glob("*.yaml"):
            if path.stem not in known:
                errors.append(f"unknown function content: {path.stem}")
    for function_id in sorted(known):
        try:
            load_layers(function_id)
        except OCFError as exc:
            errors.append(str(exc))
    return errors
