"""Bounded function metadata contract for the explicitly reviewed naming batch."""

import hashlib
import json
from copy import deepcopy

from .utils import OCFError

BATCH_ID = "OCF-EDITORIAL-TITLE-CUES-004"
# Pins the complete authorization, including prior wording and exact substitutions.
BATCH_DIGEST = "b4421a21db490e9bd4c5f15adc1c4921976bc26e647d3fde29b463350a4d1bb0"


def check_record(data):
    digest = hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if data["id"] != BATCH_ID or digest != BATCH_DIGEST:
        raise OCFError("batch differs from the explicit reviewed authorization")


def approved_function(before, decision):
    """Permit only selected naming, bindings, review and historical lookup edits."""
    new = deepcopy(before)
    new["canonical"]["name"] = decision["current_title"]
    new["canonical"]["command"]["primary"] = decision["display_cue"]
    primary = next(row for row in new["commands"] if row["id"] == decision["primary_command_id"])
    primary["spoken"] = decision["spoken_cue"]
    primary["spoken_review"] = "reviewed"
    if decision["previous"]["spoken_cue"] != decision["spoken_cue"]:
        primary["observed_phrase"] = {
            "text": decision["spoken_cue"],
            "narration_key": f"hplus.function.{new['id'].lower()}.function-body",
            "relationship": "canonical-match",
        }
    for suffix in ("display", "spoken"):
        primary["localization"][suffix + "_cue_key"] = (
            "commands." + primary["id"].lower() + "." + suffix + "-cue"
        )
    retired = set(decision["historical_command_ids"])
    for command in new["commands"]:
        if command["id"] in retired:
            if command["role"] != "legacy-alias":
                raise OCFError("batch cannot retire a control command")
            command["availability"] = "historical-lookup"
            command["documentation"]["visible"] = False
    aliases = new["aliases"]
    retained = [
        (text, identity)
        for text, identity in zip(
            aliases.get("commands", []), aliases.get("command_ids", []), strict=True
        )
        if identity not in retired
    ]
    aliases["commands"] = [text for text, _ in retained]
    aliases["command_ids"] = [identity for _, identity in retained]
    new["ocf"]["command_review"] = "approved"
    history = new.setdefault("historical_lookup", [])
    for key, current, kind in (
        ("title", "current_title", "former-title"),
        ("display_cue", "display_cue", "former-primary"),
        ("spoken_cue", "spoken_cue", "former-teaching"),
    ):
        if decision["previous"][key] != decision[current]:
            entry = {"text": decision["previous"][key], "kind": kind, "decision": BATCH_ID}
            if key != "title":
                entry["command_id"] = primary["id"]
            history.append(entry)
    if decision["previous"]["spoken_cue"] != decision["spoken_cue"]:
        new["compatibility"]["state"] = "historical-lookup"
        new["compatibility"]["rationale"] = (
            "Primary wording approved in "
            + BATCH_ID
            + "; superseded primary wording is historical lookup. Existing controls remain unchanged."
        )
    return new
