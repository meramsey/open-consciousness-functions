"""Current reports distinguish implemented, tentative, rejected and pending decisions."""

import json

import pytest
from tools import current_title_cues as reports


@pytest.mark.unit
def test_current_report_keeps_tentative_title_and_rejected_names_out_of_active_values(
    monkeypatch, tmp_path, capsys
):
    data = {
        "decision_id": "fixture",
        "predecessor_commit": "source",
        "source_scope": "Explicit successor",
        "counts": {"functions": 1},
        "functions": [
            {
                "function_id": "OCF-BOD-006",
                "current_title": "Heart: Repairs & Maintenance",
                "display_cue": "PLUS-HEART-BETTER",
                "spoken_teaching": "Plus Heart Better",
                "decision_status": "APPROVED AND IMPLEMENTED",
                "title_status": "TENTATIVE TITLE",
                "current_purpose": "Retained purpose.",
                "previous_values": {
                    "title": "Former title",
                    "display_cue": "PLUS-OLD",
                    "spoken_cue": "Plus Old",
                },
                "pending_title": "Heart Flow",
                "unselected_proposal": None,
                "metadata_teaching_consistent": True,
                "teaching_source": "Approved exact delta",
                "changed_keys": ["body"],
                "cue_presentation": {"command_id": "primary"},
                "context": "Better once; no new mechanism.",
                "historical_lookup": [{"text": "Plus Heart Better Better"}],
            }
        ],
        "rejected_or_superseded": ["Heart Renewal"],
        "pending": ["Heart Flow final title"],
    }
    monkeypatch.setattr(reports, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(reports, "build", lambda: data)
    outputs = reports.render(data)
    parsed = json.loads(outputs["OCF_TITLE_CUE_CURRENT.json"])
    assert parsed["functions"][0]["current_title"] != "Heart Flow"
    assert "TENTATIVE TITLE" in outputs["OCF_EN_US_TERMINOLOGY.md"]
    assert "Rejected or superseded" in outputs["OCF_TITLE_CUE_CURRENT.md"]
    assert "Previous values: Former title" in outputs["OCF_TITLE_CUE_CURRENT.md"]

    data["rejected_or_superseded"] = []
    without_rejections = reports.render(data)["OCF_TITLE_CUE_CURRENT.md"]
    assert "## Rejected or superseded proposals\n\n## Still pending" in without_rejections
    data["rejected_or_superseded"] = ["Heart Renewal"]
    assert reports.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().err
    assert reports.main([]) == 0 and reports.main(["--check"]) == 0
    assert (tmp_path / "docs/releases/OCF_TITLE_CUE_CURRENT.json").read_text(
        encoding="utf-8"
    ) == outputs["OCF_TITLE_CUE_CURRENT.json"]


@pytest.mark.unit
def test_current_report_refuses_integrity_drift_before_writing(monkeypatch, tmp_path, capsys):
    from ocf_tools import editorial_candidates

    monkeypatch.setattr(reports, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(editorial_candidates, "verify_approvals", lambda: ["unapproved text"])
    assert reports.main([]) == 1
    assert "unapproved text" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
def test_current_report_checks_protected_narration_before_building(monkeypatch):
    from ocf_tools import editorial_candidates
    from ocf_tools.utils import OCFError
    from tools import check_hplus_narration_integrity

    monkeypatch.setattr(editorial_candidates, "verify_approvals", lambda: [])
    monkeypatch.setattr(
        check_hplus_narration_integrity, "check", lambda: ["protected narration drift"]
    )

    with pytest.raises(OCFError, match="canonical narration integrity drift"):
        reports.build()


@pytest.mark.unit
def test_report_main_prints_operational_errors(monkeypatch, capsys):

    def unavailable(*_args):
        raise OSError("synthetic report I/O error")

    monkeypatch.setattr(reports, "_run", unavailable)

    assert reports.main([]) == 1
    assert "synthetic report I/O error" in capsys.readouterr().err


@pytest.mark.unit
def test_module_entrypoint_runs_the_current_report_check(monkeypatch):
    import runpy
    from pathlib import Path

    monkeypatch.setattr(reports.sys, "argv", ["current_title_cues", "--check"])

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(Path(reports.__file__)), run_name="__main__")
    assert exc.value.code == 0


@pytest.mark.unit
def test_current_report_rejects_narration_integrity_drift(monkeypatch):
    from ocf_tools import editorial_candidates
    from ocf_tools.utils import OCFError
    from tools import check_hplus_narration_integrity

    monkeypatch.setattr(editorial_candidates, "verify_approvals", lambda: [])
    monkeypatch.setattr(
        check_hplus_narration_integrity, "check", lambda: ["protected narration drift"]
    )

    with pytest.raises(OCFError, match="canonical narration integrity drift"):
        reports.build()


@pytest.mark.integration
def test_current_catalog_report_is_fresh_complete_and_collision_scoped():
    data = reports.build()
    assert data["counts"]["resolved_active_spoken_cues"] == 73
    assert data["counts"]["active_records"] == 83
    assert data["counts"]["historical_only_command_records"] == 19
    assert data["counts"]["stable_primary_identities"] == 58
    heart = next(row for row in data["functions"] if row["function_id"] == "OCF-BOD-006")
    assert heart["pending_title"] is None
    assert heart["current_title"] == "Heart Flow"
    assert heart["spoken_teaching"] == "Plus Heart Flow"
    for group in data["collision_groups"]:
        assert sum(owner["role"] == "activation" for owner in group["owners"]) <= 1
    assert reports.main(["--check"]) == 0
