"""Complete with investigated unknowns differs from a skipped analytical field."""

from ocf_tools.content import validate_layers
from test_content import layers


def test_complete_status_requires_all_questions_and_locator_provenance():
    data = layers()
    data["specifications"]["extraction_status"] = "complete"
    assert validate_layers(data, "OCF-FND-004")
    data["specifications"]["extraction_status"] = "partial"
    assert validate_layers(data, "OCF-FND-004") == []
