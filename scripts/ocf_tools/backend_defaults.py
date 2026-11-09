"""Versioned new-session defaults for an explicitly selected backend pair."""

from copy import deepcopy

POLICY_ID = "OCF-BACKEND-NANO-FARFIELD-001"
MIX = {
    "schema_version": "1.0",
    "profile_id": "OCF-MIX-NANO-FARFIELD-A6-001",
    "profile_version": "1.0.0",
    "semantic_state_gains_db": {"focus-10": -3.0, "focus-11": -14.0},
}


def eligible(backend, dsp, *, enabled=True):
    """Inspect declared engines, never filenames, voice identity or frequencies.

    A custom state normalization is an explicit level override. Only the
    established original -18 dBFS baseline receives the fixed A6 gains.
    """
    if not enabled or backend != "chatterbox-nano" or dsp.get("target_state_rms_dbfs") != -18:
        return False
    from .audio_build import _resolve_background_manifest

    states = dsp.get("states", {})
    if not {"focus-10", "focus-11"} <= states.keys():
        return False
    if any(states[state].get("mode") != "preset" for state in ("focus-10", "focus-11")):
        return False
    active = [row for row in states.values() if row.get("mode") != "disabled"]
    return bool(active) and all(
        row.get("mode") == "preset"
        and (_resolve_background_manifest(row["preset"]) or {}).get("engine") == "farfield"
        for row in active
    )


def mix_profile():
    """Return detached schema-valid values; never accumulate attenuation."""
    from .mix_profiles import load_mix_profile

    return load_mix_profile(deepcopy(MIX))


def pacing_id(*, learning=False):
    return "OCF-PACING-NANO-FARFIELD-" + ("LEARNING" if learning else "SESSION") + "-001"


def declared_backend(query):
    """Metadata-only lookup for dry runs; does not certify installed inference."""
    from .indexes import load_voice_profiles

    query = str(query or "").casefold()
    for profile in load_voice_profiles():
        if any(str(profile.get(key, "")).casefold() == query for key in ("id", "slug", "name")):
            return profile.get("backend", "piper")
    return None
