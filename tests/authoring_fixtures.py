"""Small, original editor workspace fixtures; no speech engines or private assets."""

import json
from copy import deepcopy

from ocf_tools import artwork, session
from ocf_tools.indexes import load_function_by_id, load_yaml_file
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import yaml_safe_dump


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2)
        if path.suffix == ".json"
        else yaml_safe_dump(data),
        encoding="utf-8",
    )
    return path


def seed(root):
    record = deepcopy(load_function_by_id("OCF-FND-002").data)
    write(root / "functions/foundation/focus.yaml", record)
    write(
        root / "locales/en-US/manifest.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "language_name": "English",
            "status": "canonical",
            "semantic_version": "1.0.0",
            "resources": [
                {"file": "narration.yaml", "domain": "narration"},
                {"file": "ui.yaml", "domain": "ui"},
            ],
        },
    )
    write(
        root / "locales/en-US/narration.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "narration",
            "entries": {
                "test.guidance": {
                    "text": "Observe {count}.",
                    "variables": ["count"],
                    "status": "draft",
                    "version": "1.0.0",
                }
            },
        },
    )
    write(
        root / "locales/en-US/ui.yaml",
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "ui",
            "entries": {"test.label": "Original fixture label"},
        },
    )
    write(
        root / "audio/voices/profiles/fixture.yaml",
        {
            "schema_version": "1.0",
            "id": "OCF-VOICE-0001",
            "slug": "fixture",
            "name": "Fixture metadata only",
            "backend": "espeak-ng",
        },
    )
    pacing = session.load_pacing_profile("OCF-PACING-HPLUS-LOCKED-001")
    pacing.update(id="OCF-PACING-TEST-001")
    pacing.pop("extends", None)
    write(root / "audio/templates/pacing/fixture.yaml", pacing)
    template = session.load_template("OCF-TPL-SESSION-HPLUS-LOCKED-001")
    template.update(id="OCF-TPL-SESSION-TEST-001", pacing_profile=pacing["id"])
    template.pop("extends", None)
    write(root / "audio/templates/sessions/base.yaml", template)
    profile = load_yaml_file(
        REPO_ROOT / "audio/background/state-profiles/OCF-DSP-HPLUS-LOCKED-001.yaml"
    )
    profile.update(id="OCF-DSP-TEST-001")
    write(root / "audio/background/state-profiles/fixture.yaml", profile)
    theme = artwork.load_theme("ocf-cosmic-dark")
    theme.update(id="ocf-fixture-dark")
    theme.pop("extends", None)
    write(root / "brand/themes/base.json", theme)
    document = {
        "schema_version": "1.0",
        "id": "editor-fixture",
        "title": "Original editor fixture",
        "locale": "en-US",
        "function_id": "OCF-FND-002",
        "source": {"format": "manual", "filename": "original-editor-fixture"},
        "timeline": [
            {
                "id": "speak",
                "at": "0:00.000",
                "narration_key": "test.guidance",
                "variables": {"count": 2},
            }
        ],
    }
    return write(root / "audio/scripts/fixture.yaml", document)
