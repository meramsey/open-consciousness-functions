"""Path-free hash invariants for the approved single-source migration."""

import pytest
from ocf_tools.canonical_integrity import verify

pytestmark = pytest.mark.integration


def test_all_58_functions_preserve_approved_structure_and_narration():
    assert verify() == []


def test_identity_set_drift_fails_closed_before_per_function_projection(monkeypatch, tmp_path):
    from ocf_tools import canonical_integrity

    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"functions": {}}', encoding="utf-8")
    monkeypatch.setattr(canonical_integrity, "resources", lambda root: [])
    monkeypatch.setattr(canonical_integrity, "load_all_functions", lambda **kwargs: [])

    assert canonical_integrity.verify(tmp_path, baseline) == [
        "canonical semantic baseline identity set differs from the 58-function catalog"
    ]


def test_canonical_semantic_hash_drift_is_reported(monkeypatch, tmp_path):
    from ocf_tools import canonical_integrity

    current = verify()
    assert current == []
    import json

    baseline = json.loads(canonical_integrity.BASELINE.read_text(encoding="utf-8"))
    identity = next(iter(baseline["functions"]))
    baseline["functions"][identity]["commands_sha256"] = "0" * 64
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")

    assert canonical_integrity.verify(baseline_path=path) == [
        f"{identity}: canonical commands_sha256 differs from the approved baseline"
    ]


@pytest.fixture(scope="module")
def current_resources():
    from ocf_tools import canonical_integrity
    from ocf_tools.paths import REPO_ROOT

    return canonical_integrity.resources(REPO_ROOT)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-link",
        "removed-link",
        "changed-target",
        "wording",
        "missing-approval",
        "narration",
        "command",
        "lifecycle",
        "presentation",
    ],
)
def test_successor_never_authorizes_unreviewed_semantic_changes(
    monkeypatch, current_resources, mutation
):
    from copy import deepcopy

    from ocf_tools import canonical_integrity
    from ocf_tools.function_catalog import project
    from ocf_tools.paths import REPO_ROOT

    rows = deepcopy(current_resources)
    data = next(data for _, data in rows if data["function_id"] == "OCF-BOD-001")
    links = data["relationships"]["related_functions"]
    if mutation == "extra-link":
        extra = deepcopy(links[-1])
        extra["function_id"] = "OCF-BOD-004"
        links.append(extra)
    elif mutation == "removed-link":
        links.pop()
    elif mutation == "changed-target":
        links[-1]["function_id"] = "OCF-BOD-004"
    elif mutation == "wording":
        links[-1]["description"]["text"] += " unapproved claim"
    elif mutation == "missing-approval":
        data["record_metadata"]["editorial_decisions"] = [
            row
            for row in data["record_metadata"]["editorial_decisions"]
            if row.get("kind") != "approved-relationship"
        ]
    elif mutation == "narration":
        next(iter(data["entries"].values()))["text"] += " unapproved speech"
    elif mutation == "command":
        data["activation"]["control"]["designation"] = "secondary"
    elif mutation == "lifecycle":
        data["lifecycle"]["unapproved"] = True
    else:
        data["title"]["text"] = "Unapproved title"
    monkeypatch.setattr(canonical_integrity, "resources", lambda root: rows)
    monkeypatch.setattr(
        canonical_integrity,
        "load_all_functions",
        lambda **kwargs: [project(data, path, REPO_ROOT) for path, data in rows],
    )
    assert canonical_integrity.verify()


@pytest.mark.parametrize(
    "mutation",
    [
        "predecessor",
        "unknown-identity",
        "protected-field",
        "prior-hash",
        "approval",
        "contract",
        "wording",
        "locale-entry",
        "projection",
        "schema",
    ],
)
def test_successor_receipt_is_bound_and_field_limited(
    monkeypatch, tmp_path, current_resources, mutation
):
    import json

    from ocf_tools import guide_review
    from ocf_tools.utils import OCFError

    receipt = json.loads(guide_review.SUCCESSOR.read_text())
    identity = next(iter(receipt["functions"]))
    row = receipt["functions"][identity]
    if mutation == "predecessor":
        receipt["predecessor_sha256"]["semantic"] = "0" * 64
    elif mutation == "unknown-identity":
        receipt["functions"]["OCF-FAKE-001"] = receipt["functions"].pop(identity)
    elif mutation == "protected-field":
        row["narration_sha256"] = "0" * 64
    elif mutation == "prior-hash":
        row["previous_contract_sha256"] = "0" * 64
    elif mutation == "approval":
        row["approved_decisions_sha256"] = "0" * 64
    elif mutation == "contract":
        row["contract_sha256"] = "0" * 64
    elif mutation == "wording":
        row["reviewed_relationships_sha256"] = "0" * 64
    elif mutation == "projection":
        row["record_without_bindings_sha256"] = "0" * 64
    elif mutation == "locale-entry":
        next(iter(receipt["added_canonical_entries"].values()))["raw_sha256"] = "0" * 64
    else:
        receipt["schema_version"] = "unsupported"
    path = tmp_path / "successor.json"
    path.write_text(json.dumps(receipt))
    monkeypatch.setattr(guide_review, "SUCCESSOR", path)
    with pytest.raises(OCFError):
        guide_review.approved_successor(
            snapshot={data["function_id"]: data for _, data in current_resources}
        )
