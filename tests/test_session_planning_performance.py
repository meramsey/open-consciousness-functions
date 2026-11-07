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
    # Public canonical baseline at b45f1fd; includes all expanded narration,
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
        == "4ae638609dec2e47938c5989017a5ffe3a2d4003fe63373dd50e626dc225993d"
    )
