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
    # The approved relationship successor changes only the three declared
    # baseline references. Retain the complete older declaration hash as well.
    text = serialize({"plan": plan, "shared": shared, "expanded": expanded})
    assert (
        hashlib.sha256(text.encode()).hexdigest()
        == "ae27430581c07530080850eeee87d1189ae018cdb23992a0baf33ca84cde00bc"
    )
    # Source-only editorial021 changes only default identity/shared fingerprints
    # for this unaffected function. Prove exact020 semantics before older checks.
    editorial_replacements = {
        "OCF-AUDIO-DEFAULTS-HPLUS-021": "OCF-AUDIO-DEFAULTS-HPLUS-020",
        "a5a8e37be856cc890d4ec8f3f352569d1974b5e45b91920751cbf7b827673c5b": "339ff152899937803c91808ac0d12e306d87930296c4c71790c0e5282e418ac2",
        "d7499758c2203e77ab85682d2caf44ebe8d41b9dfa2efa399c9237662a9a1705": "4e93f381960d57172c6fe231cc6a55ce815da2ab88f97da25178e80ac744d50e",
    }
    for current, previous in editorial_replacements.items():
        assert text.count(current) == 1
        text = text.replace(current, previous)
    assert (
        hashlib.sha256(text.encode()).hexdigest()
        == "705025d71f79c91279f3be92559b0370dac30b3f98ddcfdf0be28cd28c0946f1"
    )
    replacements = {
        "OCF-AUDIO-DEFAULTS-HPLUS-020": "OCF-AUDIO-DEFAULTS-HPLUS-018",
        "339ff152899937803c91808ac0d12e306d87930296c4c71790c0e5282e418ac2": "e90b27d729273f913939cda8275ad5dd3533f35f613bc6a610f1122bde7e668e",
        "4e93f381960d57172c6fe231cc6a55ce815da2ab88f97da25178e80ac744d50e": "bcdc6389258d1b78e2ca626c73b5bf5e6bddc41c213e443df534bc6bbb68a28d",
    }
    for current, previous in replacements.items():
        assert text.count(current) == 1
        text = text.replace(current, previous)
    assert (
        hashlib.sha256(text.encode()).hexdigest()
        == "fdd3db96ceed4a37628d488d466a090629561d50a307f267bea92c56c3a75240"
    )
