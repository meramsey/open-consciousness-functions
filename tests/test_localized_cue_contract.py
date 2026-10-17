"""Spoken cue identity is explicit, Unicode-preserving and distinct from a label."""

from types import SimpleNamespace

import pytest
from ocf_tools.commands import cue_presentation, localized_cue, validate_command_records
from ocf_tools.locale import LocalizationError
from ocf_tools.models import FunctionCommand, FunctionRecord

pytestmark = pytest.mark.unit


def owner_and_command(tmp_path, localization=None):
    data = {
        "id": "OCF-CMD-EXP-001-PRIMARY",
        "function_id": "OCF-EXP-001",
        "phrase_ref": {"source": "canonical-primary"},
        "role": "activation",
        "designation": "primary",
        "localization": localization or {},
    }
    owner = FunctionRecord(
        "OCF-EXP-001",
        "example",
        tmp_path / "example.yaml",
        {"canonical": {"command": {"primary": "PLUS-MANIFEST", "modes": []}}, "commands": [data]},
    )
    return owner, FunctionCommand.from_dict(data)


@pytest.mark.parametrize(
    "speech,locale", [("顯現", "zh-Hant"), ("प्रकट हो", "hi"), ("Plus Manifest", "en-US")]
)
def test_complete_locale_native_cue_is_never_tokenized_or_built_from_label(
    tmp_path, speech, locale
):
    owner, command = owner_and_command(
        tmp_path,
        {
            "label_key": "role.label",
            "display_cue_key": "cue.display",
            "spoken_cue_key": "cue.spoken",
        },
    )
    seen = []

    def resource(key, target, *, domain, fallback):
        seen.append((key, domain, fallback))
        return SimpleNamespace(
            text="Native display" if domain == "ui" else speech, version="2.0.0", status="reviewed"
        ), SimpleNamespace(origin_locale=locale, fallback=False)

    catalog = SimpleNamespace(canonical_locale="en-US", resource=resource)
    result = localized_cue(owner, command, locale, catalog=catalog, strict=True)
    assert result["spoken_cue"] == speech and result["display_cue"] == "Native display"
    assert seen == [("cue.display", "ui", True), ("cue.spoken", "narration", False)]
    assert "role.label" not in [row[0] for row in seen]


def test_missing_binding_is_unbound_not_a_label_or_canonical_speech_fallback(tmp_path):
    owner, command = owner_and_command(tmp_path, {"label_key": "role.label"})
    catalog = SimpleNamespace(
        canonical_locale="en-US", resource=lambda *a, **k: pytest.fail("label must never be spoken")
    )
    result = localized_cue(owner, command, "en-US", catalog=catalog)
    assert result["binding_status"] == "unbound" and result["spoken_cue"] is None


@pytest.mark.parametrize("strict", [True, False])
def test_declared_missing_or_wrong_domain_binding_never_borrows_english(tmp_path, strict):
    owner, command = owner_and_command(tmp_path, {"spoken_cue_key": "cue.spoken"})

    def missing(*args, **kwargs):
        raise LocalizationError("not available as narration in requested language")

    catalog = SimpleNamespace(canonical_locale="en-US", resource=missing)
    if strict:
        with pytest.raises(LocalizationError):
            localized_cue(owner, command, "es", catalog=catalog, strict=True)
    else:
        result = localized_cue(owner, command, "es", catalog=catalog)
        assert result["binding_status"] == "requires-locale-review" and result["spoken_cue"] is None


def test_operational_command_cannot_be_demoted_as_historical(tmp_path):
    owner, command = owner_and_command(tmp_path)
    owner.data["commands"][0]["availability"] = "historical-lookup"
    assert any("operational command" in error for error in validate_command_records(owner))
    owner.data["commands"] = []
    assert cue_presentation(owner, catalog=SimpleNamespace()) is None


@pytest.mark.parametrize("strict", [True, False])
def test_draft_terminology_is_not_promoted_to_reviewed_spoken_vocabulary(tmp_path, strict):
    owner, command = owner_and_command(tmp_path, {"spoken_cue_key": "cue.spoken"})
    catalog = SimpleNamespace(
        canonical_locale="en-US",
        resource=lambda *a, **k: (
            SimpleNamespace(text="Unreviewed candidate", status="draft", version="1.0.0"),
            SimpleNamespace(origin_locale="en-US", fallback=False),
        ),
    )
    if strict:
        with pytest.raises(LocalizationError, match="terminology review"):
            localized_cue(owner, command, catalog=catalog, strict=True)
    else:
        result = localized_cue(owner, command, catalog=catalog)
        assert result["binding_status"] == "requires-locale-review" and result["spoken_cue"] is None
