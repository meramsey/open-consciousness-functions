"""Descriptive lifecycle scopes; no trigger evaluation or runtime automation."""

from copy import deepcopy

from .utils import OCFError

KINDS = ("capability", "baseline", "application", "episode")
PERSISTENCE = {"temporary", "permanent", "persistent", "conditional"}
ACTIVATION = {"manual", "automatic", "conditional", "continuous"}


def scoped(owner, reference, *, invocation=False):
    allowed = (
        {"lifecycle.scopes.application": "application"}
        if invocation
        else {f"lifecycle.scopes.{kind}.persistence": kind for kind in KINDS}
    )
    kind = allowed.get(reference) if isinstance(reference, str) else None
    if kind is None:
        raise OCFError(f"unknown lifecycle scope reference: {reference!r}")
    lifecycle = owner.data.get("lifecycle")
    scopes = lifecycle.get("scopes") if isinstance(lifecycle, dict) else None
    scope = scopes.get(kind) if isinstance(scopes, dict) else None
    if not isinstance(scope, dict) or scope.get("persistence") not in PERSISTENCE:
        raise OCFError(f"missing or invalid lifecycle scope: {reference}")
    if invocation and scope.get("activation") != "manual":
        raise OCFError("command invocation scope must explicitly remain manual")
    return deepcopy(scope)


def validate_scopes(owner):
    lifecycle = owner.data.get("lifecycle", {})
    if not isinstance(lifecycle, dict):
        return ["lifecycle must be a mapping"]
    scopes = lifecycle.get("scopes", {})
    if not isinstance(scopes, dict):
        return ["lifecycle.scopes must be a mapping"]
    errors = []
    for kind, scope in scopes.items():
        if kind not in KINDS or not isinstance(scope, dict):
            errors.append(f"unknown or invalid lifecycle scope: {kind}")
            continue
        if scope.get("persistence") not in PERSISTENCE:
            errors.append(f"{kind}: invalid scope persistence")
        if "activation" in scope and scope["activation"] not in ACTIVATION:
            errors.append(f"{kind}: invalid scope activation")
        if not scope.get("description") or not scope.get("description_key"):
            errors.append(f"{kind}: scope requires source description and stable locale key")
        trigger_ref = scope.get("trigger_conditions_ref")
        if trigger_ref is not None and (
            trigger_ref != "lifecycle.trigger_conditions" or not lifecycle.get("trigger_conditions")
        ):
            errors.append(f"{kind}: missing or invalid trigger-conditions reference")
    for command in owner.command_records:
        for field, invocation in (("effect_scope_ref", False), ("invocation_scope_ref", True)):
            reference = command.data.get(field)
            if field not in command.data or (
                not invocation and reference == "lifecycle.persistence"
            ):
                continue
            try:
                scoped(owner, reference, invocation=invocation)
            except OCFError as exc:
                errors.append(f"{command.id}: {exc}")
    return errors


def validate_scope_descriptions(owner, catalog):
    scopes = owner.data.get("lifecycle", {}).get("scopes", {})
    if not isinstance(scopes, dict):
        return []  # Structural validation reports the malformed scope collection.
    errors = []
    for kind, scope in scopes.items():
        if not isinstance(scope, dict):
            continue
        key = scope.get("description_key")
        entry = catalog.canonical.get(key) if catalog.canonical and isinstance(key, str) else None
        if entry is None or entry.domain != "ui" or entry.text != scope.get("description"):
            errors.append(
                f"{kind}: source-English scope description must match function YAML at {key!r}"
            )
    return errors
