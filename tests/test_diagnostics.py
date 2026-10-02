"""Optional dependencies affect selected workflows, never basic metadata health."""

import pytest
from ocf_tools.diagnostics import diagnose
from ocf_tools.validators import _load_schema, validate_against_schema


def healthy(**kwargs):
    return diagnose(
        which=lambda name: None,
        version=(3, 12),
        module_available=lambda name: True,
        schemas=True,
        functions=True,
        **kwargs,
    )


def test_missing_optional_tools_do_not_fail_core_and_schema_is_stable():
    data = healthy()
    assert data["ok"] and not data["failures"]
    assert all(
        row["requirement"] == "optional" for row in data["checks"] if row["id"] == "farfield"
    )
    assert validate_against_schema(data, _load_schema("doctor.schema.json")) == []


def test_selected_workflow_and_required_runtime_fail_correctly():
    assert healthy(workflow="encode")["failures"] == ["ffmpeg", "ffprobe"]
    data = diagnose(
        which=lambda name: "/available/" + name,
        version=(3, 9),
        module_available=lambda name: name != "yaml",
        schemas=False,
        functions=True,
    )
    assert data["failures"] == ["python", "yaml", "schemas"]
    with pytest.raises(ValueError, match="unknown"):
        healthy(workflow="invented")
