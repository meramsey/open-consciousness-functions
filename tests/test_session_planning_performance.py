"""Reuse preflight catalogs without changing complete-session declarations."""

import hashlib

import pytest
from ocf_tools import complete_session
from ocf_tools.session_plans import serialize, source_plan

pytestmark = pytest.mark.integration


def test_plan_reuses_completeness_catalog_and_retains_exact_baseline(monkeypatch):
    original = complete_session.LocaleCatalog
    created = []

    def counted():
        catalog = original()
        created.append(catalog)
        return catalog

    monkeypatch.setattr(complete_session, "LocaleCatalog", counted)
    plan, shared, expanded = source_plan("OCF-FND-002")
    assert len(created) == 1
    # Approved shared-session v3 baseline (018); includes all expanded narration,
    # timing, transition, approval and source-declaration metadata, not audio.
    assert (
        hashlib.sha256(
            serialize(
                {
                    "plan": plan,
                    "shared": shared,
                    "expanded": expanded,
                }
            ).encode()
        ).hexdigest()
        == "fdd3db96ceed4a37628d488d466a090629561d50a307f267bea92c56c3a75240"
    )
