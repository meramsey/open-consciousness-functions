"""Complete with investigated unknowns differs from a skipped analytical field."""

import pytest
from ocf_tools.content import validate_layers
from test_content import layers


def test_complete_status_requires_all_questions_and_locator_provenance():
    data = layers()
    data["specifications"]["extraction_status"] = "complete"
    assert validate_layers(data, "OCF-FND-004")
    data["specifications"]["extraction_status"] = "partial"
    assert validate_layers(data, "OCF-FND-004") == []


@pytest.mark.unit
def test_complete_review_can_retain_investigated_unknowns_but_not_missing_answers():
    data = layers()
    locator = {"source_sha256": "a" * 64, "file": "mockup.txt", "start_line": 1, "end_line": 3}
    sections = (
        "identity",
        "purpose",
        "preparation",
        "state",
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
        "conversion",
        "provenance",
    )
    review = {
        "method": "complete-available-source-content-review",
        "family": "synthetic-fixture",
        "source_extent": locator,
        "scope": "documentary extraction; not narration approval, historical authentication or runtime state binding",
        "claim_categories": [],
        "sections": {
            name: {
                "status": "unknown",
                "summary": "Available fixture reviewed; no supported historical value.",
                "locators": [dict(locator)],
            }
            for name in sections
        },
    }
    data["specifications"].update(extraction_status="complete", analysis_review=review)
    assert validate_layers(data, "OCF-FND-004") == []
    del review["sections"]["main"]
    assert validate_layers(data, "OCF-FND-004")
    review["sections"]["main"] = {
        "status": "unknown",
        "summary": "Investigated",
        "locators": [dict(locator, end_line=0)],
    }
    assert validate_layers(data, "OCF-FND-004")
