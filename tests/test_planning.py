"""Plans validate concrete capability choices without generating editorial content."""

from copy import deepcopy

import pytest
from ocf_tools.planning import plan
from ocf_tools.utils import OCFError

REQUEST = {
    "schema_version": "1.0",
    "template": "OCF-TPL-SESSION-PILOT-RELAX-001",
    "locale": "en-US",
    "narration_source": "tts",
    "target_duration_s": 1200,
}


def test_plan_does_not_promote_pilot_or_claim_target_duration():
    original = deepcopy(REQUEST)
    result = plan(REQUEST)
    assert REQUEST == original
    assert (
        result["dry_run"]
        and result["content_status"] == "draft"
        and result["human_review"] == "required"
    )
    assert result["spoken_events"] == 6 and result["target_duration_s"] == 1200
    assert "no automatic stretching" in result["duration_status"]


def test_plan_rejects_missing_translation_wrong_owner_and_missing_dsp():
    with pytest.raises(OCFError):
        plan({**REQUEST, "locale": "es"})
    with pytest.raises(OCFError):
        plan({**REQUEST, "function_id": "OCF-FND-002"})
    with pytest.raises(OCFError, match="lacks required"):
        plan(
            {
                **REQUEST,
                "template": "OCF-TPL-SESSION-PREP-LEARN-001",
                "dsp_profile": "OCF-DSP-DEFAULT-001",
            }
        )
    with pytest.raises(OCFError):
        plan({**REQUEST, "narration_source": "prerecorded-user"})
