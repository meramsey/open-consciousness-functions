import copy
from dataclasses import replace

import pytest
from ocf_tools import cue_templates, shared_state_cues
from ocf_tools.cli import main
from ocf_tools.locale import LocaleCatalog
from ocf_tools.utils import OCFError, yaml_safe_dump, yaml_safe_load

pytestmark = pytest.mark.integration
REVISION = "OCF-SHARED-SESSION-003"


@pytest.fixture(scope="module")
def catalog():
    return LocaleCatalog().with_revision(REVISION, "en-US")


def test_shared_reference_has_two_stable_localized_identities_and_preserved_legacy(catalog):
    data = shared_state_cues.describe(catalog=catalog)
    assert data["application_commands"] is False and data["release_ready"] is False
    assert [(r["id"], r["spoken"], r["display"]) for r in data["cues"]] == [
        ("OCF-SHARED-CUE-ACCESS-OPEN", "Plus Eleven Access", "Plus Eleven Access"),
        ("OCF-SHARED-CUE-ACCESS-CLOSE", "Plus Release Eleven Access", "Plus Release Eleven Access"),
    ]
    assert data["cues"][1]["legacy_compatibility"]["spoken"] == "plus, release, eleven, access"
    assert all("AWAKE" not in r["id"] for r in data["cues"])


def test_shared_symbol_resolution_preserves_exact_quotes_and_explicit_ownership(catalog):
    for key in (
        "hplus.shared.focus11.open.prepare",
        "hplus.shared.focus11.close",
        "preparation.learning.v3.open-2",
        "preparation.learning.v3.open-3",
    ):
        entry, _ = catalog.resource(key, "en-US", domain="narration", fallback=False)
        assert "{{" in entry.raw_template and "{{" not in entry.text
        assert entry.cue_provenance and all(
            r["provenance"]["shared_state_id"] == "OCF-SHARED-STATE-CUES-001"
            for r in entry.cue_provenance
        )
    a = catalog.resource(
        "hplus.shared.focus11.open.prepare", "en-US", domain="narration", fallback=False
    )[0]
    b = catalog.resource(
        "preparation.learning.v3.open-2", "en-US", domain="narration", fallback=False
    )[0]
    assert '"Plus Eleven Access."' in a.text
    assert "“Plus Eleven Access.”" in b.text


@pytest.mark.parametrize(
    "change",
    [
        "owner",
        "key",
        "domain",
        "variables",
        "draft",
        "duplicate",
        "missing",
        "function-symbol",
        "literal-only",
    ],
)
def test_shared_contract_fails_closed_without_relaxing_function_ownership(catalog, change):
    entry = catalog.raw_resource(
        "hplus.shared.focus11.open.prepare", "en-US", domain="narration", fallback=False
    )[0]
    contract = copy.deepcopy(entry.cue_template)
    if change == "owner":
        contract["shared_state"] = "UNKNOWN"
    elif change == "key":
        entry = replace(entry, key="hplus.function.ocf-sen-001.function-body")
    elif change == "domain":
        entry = replace(entry, domain="ui")
    elif change == "variables":
        entry = replace(entry, variables=("injected",))
    elif change == "draft":
        entry = replace(entry, status="draft")
    elif change == "duplicate":
        contract["allowed"] *= 2
    elif change == "missing":
        contract["allowed"] = []
    elif change == "function-symbol":
        contract["allowed"] = ["cue.primary"]
        entry = replace(entry, text="{{ cue.primary }}")
    else:
        contract["allowed"] = []
        entry = replace(entry, text="Literal unowned text.")
    with pytest.raises(OCFError):
        cue_templates.expand(replace(entry, cue_template=contract), "en-US", catalog)


def test_function_contract_cannot_borrow_shared_owner(catalog):
    entry = catalog.raw_resource(
        "hplus.function.ocf-sen-001.function-body", "en-US", domain="narration", fallback=False
    )[0]
    forged = replace(
        entry,
        text="{{ state.access.open }}",
        cue_template={"function_id": "OCF-SEN-001", "allowed": ["state.access.open"]},
    )
    with pytest.raises(OCFError, match="unsupported cue selector"):
        cue_templates.expand(forged, "en-US", catalog)


@pytest.mark.parametrize("change", ["unreviewed", "recursive", "empty", "braces"])
def test_shared_value_must_be_literal_reviewed_nonrecursive(catalog, change):
    entry, resolution = catalog.raw_resource(
        "hplus.shared.state-cue.access-open", "en-US", domain="narration", fallback=False
    )
    changes = {
        "unreviewed": {"status": "machine"},
        "recursive": {"cue_template": {"allowed": []}},
        "empty": {"text": " "},
        "braces": {"text": "{{ cue.primary }}"},
    }

    class Fake:
        def raw_resource(self, *args, **kwargs):
            return replace(entry, **changes[change]), resolution

    with pytest.raises(OCFError, match="reviewed nonrecursive"):
        shared_state_cues.cue("state.access.open", "en-US", Fake())
    with pytest.raises(OCFError, match="unsupported"):
        shared_state_cues.cue("cue.primary", "en-US", catalog)


@pytest.mark.parametrize("change", ["schema", "role", "id", "display"])
def test_structured_identity_table_is_validated_not_an_alias_fallback(tmp_path, change):
    data = shared_state_cues.load()
    if change == "schema":
        data["extra"] = True
    elif change == "role":
        data["cues"]["state.access.open"]["role"] = "close"
    elif change == "id":
        data["cues"]["state.access.open"]["id"] = "OCF-SHARED-CUE-ACCESS-CLOSE"
    else:
        data["cues"]["state.access.open"]["display_key"] = "another.key"
    path = tmp_path / "function-content/shared-state-cues.yaml"
    path.parent.mkdir()
    path.write_text(yaml_safe_dump(data))
    with pytest.raises(OCFError):
        shared_state_cues.load(tmp_path)


def test_shared_contract_mixed_owners_and_duplicate_yaml_are_rejected():
    from ocf_tools.locale import _entry_from_value

    with pytest.raises(OCFError):
        _entry_from_value(
            "fixture",
            {
                "text": "{{ state.access.open }}",
                "cue_template": {
                    "function_id": "OCF-SEN-001",
                    "shared_state": "OCF-SHARED-STATE-CUES-001",
                    "allowed": ["state.access.open"],
                },
            },
            "en-US",
            "narration",
            "fixture.yaml",
        )
    with pytest.raises(Exception, match="duplicate"):
        yaml_safe_load("id: first\nid: second\n")


def test_cli_is_generated_from_records_and_missing_spoken_locale_fails(capsys):
    import json

    assert main(["commands", "shared-state", "--locale", "en-US"]) == 0
    assert len(json.loads(capsys.readouterr().out)["cues"]) == 2
    assert main(["commands", "shared-state", "--locale", "es"]) == 1
    assert capsys.readouterr().err
