"""L4 atomic manifest switch and historical logical-path safety on fixtures."""

import pytest
import yaml
from ocf_tools import locale_history
from ocf_tools.locale import LocaleCatalog, resource_filename_valid
from ocf_tools.localized_filenames import LEDGER, apply_filenames, filename_plan
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError
from test_localized_field_sources import literal_resource
from test_localized_function_resources import write_pack

pytestmark = pytest.mark.unit


def setup_source(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    resource = literal_resource()
    resource["title"]["text"] = "Café"
    folder = write_pack(tmp_path / "locales", resource)
    old = folder / "hplus-OCF-EMO-003.yaml"
    (folder / "OCF-EMO-003-Empathize.yaml").rename(old)
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text())
    manifest["resources"][0]["file"] = old.name
    (folder / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8", newline="\n")
    function = tmp_path / "functions/emotion/empathizing.yaml"
    function.parent.mkdir(parents=True)
    function.write_bytes((REPO_ROOT / "functions/emotion/empathizing.yaml").read_bytes())
    return folder, old


def test_apply_keeps_exact_content_id_and_legacy_bytes(tmp_path, monkeypatch):
    folder, old = setup_source(tmp_path, monkeypatch)
    original = old.read_bytes()
    before = (
        LocaleCatalog(tmp_path / "locales")
        .resource("hplus.function.ocf-emo-003.opener", "en-US", domain="narration", fallback=False)[
            0
        ]
        .text
    )
    receipt = apply_filenames(tmp_path)
    assert receipt["count"] == 1
    target = folder / "OCF-EMO-003-Café.yaml"
    assert target.read_bytes() == original
    assert yaml.safe_load(old.read_text())["kind"] == "immutable-historical-locale-reference"
    catalog = LocaleCatalog(tmp_path / "locales")
    assert catalog.problems == []
    assert catalog.require("en-US").localized_function_files == {"OCF-EMO-003": target.name}
    assert (
        catalog.resource(
            "hplus.function.ocf-emo-003.opener", "en-US", domain="narration", fallback=False
        )[0].text
        == before
    )
    monkeypatch.setattr(locale_history, "FILENAMES_SHA256", receipt["ledger_sha256"])
    assert (
        locale_history.before_structural(
            tmp_path, old.relative_to(tmp_path).as_posix(), old.read_text()
        )
        == original.decode()
    )
    assert apply_filenames(tmp_path)["status"] == "already-renamed; no writes"
    target.write_text("unknown human edit; preserve")
    with pytest.raises(OCFError, match="changed; preserve"):
        apply_filenames(tmp_path)
    assert target.read_text() == "unknown human edit; preserve"


def test_unlisted_casefold_collision_never_overwrites_operator_data(tmp_path, monkeypatch):
    folder, old = setup_source(tmp_path, monkeypatch)
    collision = folder / "ocf-emo-003-CAFÉ.YAML"
    collision.write_text("operator data", encoding="utf-8")
    assert filename_plan(tmp_path)["blockers"]
    with pytest.raises(OCFError, match="destinations require reconciliation"):
        apply_filenames(tmp_path)
    assert collision.read_text() == "operator data"
    assert not (tmp_path / LEDGER).exists()


@pytest.mark.parametrize(
    "name,valid",
    [
        ("OCF-EMO-003-Café.yaml", True),
        ("OCF-EMO-003-世界.yaml", True),
        ("CON.yaml", False),
        ("../escape.yaml", False),
        ("OCF-EMO-003-Cafe\u0301.yaml", False),
        ("bad:name.yaml", False),
    ],
)
def test_resource_filename_contract_supports_portable_unicode(name, valid):
    assert resource_filename_valid(name) is valid
    if valid:
        from ocf_tools.validators import _load_schema, validate_against_schema

        file_schema = _load_schema("locale-manifest.schema.json")["properties"]["resources"][
            "items"
        ]["properties"]["file"]
        assert validate_against_schema(name, file_schema) == []
