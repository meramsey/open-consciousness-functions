"""Fingerprint the installed runtime, not the checkout in direct_url.json."""

import importlib.metadata
import json
import os
import py_compile
import sys

import pytest
from ocf_tools import farfield


@pytest.fixture
def installed(monkeypatch, tmp_path):
    site = tmp_path / "site"
    for name, requirements in (("farfield", "Requires-Dist: dspdep\n"), ("dspdep", "")):
        package = site / name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("VERSION = 1\n")
        (package / "cli.py").write_text("def main(): pass\n")
        dist = site / f"{name}-1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(f"Name: {name}\nVersion: 1.0\n{requirements}")
        (dist / "entry_points.txt").write_text(f"[console_scripts]\n{name} = {name}.cli:main\n")
        (dist / "RECORD").write_text(
            "\n".join(
                [
                    f"{name}/__init__.py,,",
                    f"{name}/cli.py,,",
                    f"{name}-1.0.dist-info/METADATA,,",
                    f"{name}-1.0.dist-info/entry_points.txt,,",
                    f"{name}-1.0.dist-info/RECORD,,",
                ]
            )
        )
    checkout = tmp_path / "unrelated-checkout/farfield"
    checkout.mkdir(parents=True)
    (checkout / "__init__.py").write_text("VERSION = 9\n")
    (site / "farfield-1.0.dist-info/direct_url.json").write_text(
        json.dumps({"url": checkout.parent.as_uri(), "dir_info": {"editable": False}})
    )
    binary = tmp_path / "bin/farfield"
    binary.parent.mkdir()
    binary.write_text(f'#!"{sys.executable}"\nfrom farfield.cli import main\nmain()\n')
    monkeypatch.setenv("PYTHONPATH", str(site))
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(
        farfield, "check_farfield", lambda: farfield.FarfieldStatus(True, str(binary), "1.0")
    )
    return site, checkout, binary


@pytest.mark.integration
def test_actual_installed_code_and_dependency_bytes_determine_identity(installed):
    site, checkout, _ = installed
    first = farfield.engine_identity()
    assert first is not None
    (checkout / "__init__.py").write_text("VERSION = 10\n")
    assert farfield.engine_identity() == first
    (site / "farfield/cli.py").write_text("def main(): return 2\n")
    changed_engine = farfield.engine_identity()
    assert changed_engine != first and changed_engine is not None
    # A native dependency change must be detected even with unchanged RECORD.
    (site / "dspdep/native-fixture.so").write_bytes(b"native implementation 1")
    native_first = farfield.engine_identity()
    (site / "dspdep/native-fixture.so").write_bytes(b"native implementation 2")
    assert farfield.engine_identity() not in (native_first, None)


@pytest.mark.integration
def test_editable_or_shadowed_actual_import_is_fingerprinted(installed, monkeypatch):
    site, checkout, _ = installed
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join((str(checkout.parent), str(site))))
    first = farfield.engine_identity()
    assert first is not None
    (checkout / "__init__.py").write_text("VERSION = 11\n")
    assert farfield.engine_identity() not in (first, None)


@pytest.mark.integration
def test_importable_required_dependency_without_metadata_is_unverified(installed):
    site, _, _ = installed
    metadata = site / "dspdep-1.0.dist-info"
    metadata.rename(site / "unregistered-dependency")
    assert (site / "dspdep/__init__.py").is_file()
    assert farfield.engine_identity() is None


@pytest.mark.integration
def test_missing_recorded_implementation_file_cannot_authorize_reuse(installed):
    site, _, _ = installed
    (site / "farfield/cli.py").unlink()
    assert farfield.engine_identity() is None


@pytest.mark.integration
def test_inactive_optional_requirement_does_not_disable_identity(installed):
    site, _, _ = installed
    metadata = site / "farfield-1.0.dist-info/METADATA"
    with metadata.open("a") as stream:
        stream.write('Requires-Dist: deliberately-absent-test-dependency; extra == "dev"\n')
    assert farfield.engine_identity() is not None


@pytest.mark.integration
def test_selected_dependency_extras_are_required_and_verified(installed):
    site, _, _ = installed
    metadata = site / "farfield-1.0.dist-info/METADATA"
    metadata.write_text(metadata.read_text().replace("dspdep\n", "dspdep[selected]\n"))
    with (site / "dspdep-1.0.dist-info/METADATA").open("a") as stream:
        stream.write('Requires-Dist: deliberately-absent-test-dependency; extra == "selected"\n')
    assert farfield.engine_identity() is None


@pytest.mark.integration
def test_shadowed_sourceless_implementation_cannot_authorize_reuse(installed, monkeypatch):
    site, checkout, _ = installed
    source = checkout / "__init__.py"
    py_compile.compile(str(source), cfile=str(source.with_suffix(".pyc")), doraise=True)
    source.unlink()
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join((str(checkout.parent), str(site))))
    assert farfield.engine_identity() is None


@pytest.mark.integration
def test_custom_python_launcher_setup_cannot_authorize_reuse(installed):
    _, checkout, binary = installed
    binary.write_text(
        f'#!"{sys.executable}"\nimport sys\nsys.path.insert(0, {str(checkout.parent)!r})\n'
        "from farfield.cli import main\nmain()\n"
    )
    assert farfield.engine_identity() is None


@pytest.mark.integration
def test_sourceless_submodule_under_source_package_is_unverified(installed):
    site, _, _ = installed
    source = site / "farfield/private_runtime.py"
    source.write_text("implementation = 1\n")
    py_compile.compile(str(source), cfile=str(source.with_suffix(".pyc")), doraise=True)
    source.unlink()
    assert farfield.engine_identity() is None


@pytest.mark.unit
@pytest.mark.parametrize("header", [b"unknown binary", b"#!/bin/sh\n", b"#!/usr/bin/env python\n"])
def test_unknown_launcher_cannot_authorize_reuse(monkeypatch, tmp_path, header):
    executable = tmp_path / "farfield"
    executable.write_bytes(header)
    monkeypatch.setattr(
        farfield, "check_farfield", lambda: farfield.FarfieldStatus(True, str(executable))
    )
    monkeypatch.setattr(
        farfield, "workspace_run", lambda *args, **kwargs: pytest.fail("unknown launcher probed")
    )
    assert farfield.engine_identity() is None


@pytest.mark.unit
def test_missing_engine_identity_is_explicit(monkeypatch):
    monkeypatch.setattr(farfield, "check_farfield", lambda: farfield.FarfieldStatus(False))
    assert farfield.engine_identity() is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "inactive-extra",
        "missing-metadata",
        "missing-inventory",
        "missing-file",
        "custom-import",
        "custom-call",
        "custom-assignment",
        "custom-loop",
        "wrong-entry",
        "bytecode",
    ],
)
def test_runtime_probe_fail_closed_contract_without_subprocess(installed, monkeypatch, case):
    site, _, binary = installed
    monkeypatch.setattr(sys, "argv", ["probe", str(binary)])
    monkeypatch.setattr(sys, "path", [str(binary.parent), str(site), *sys.path])
    if case == "inactive-extra":
        with (site / "farfield-1.0.dist-info/METADATA").open("a") as stream:
            stream.write('Requires-Dist: deliberately-missing; extra == "dev"\n')
    elif case == "missing-metadata":
        (site / "dspdep-1.0.dist-info").rename(site / "unregistered-dependency")
    elif case == "missing-inventory":
        (site / "farfield-1.0.dist-info/RECORD").unlink()
    elif case == "missing-file":
        (site / "farfield/cli.py").unlink()
    elif case == "bytecode":
        (site / "farfield/runtime.pyc").write_bytes(b"unverified bytecode")
    elif case.startswith("custom-"):
        setup = {
            "custom-import": "import os\n",
            "custom-call": "import sys\nsys.path.insert(0, 'other')\n",
            "custom-assignment": "import sys\nsys.path = []\n",
            "custom-loop": "while False: pass\n",
        }[case]
        binary.write_text(setup + "from farfield.cli import main\nmain()\n")
    elif case == "wrong-entry":
        binary.write_text("from dspdep.cli import main\nmain()\n")
    if case in {"valid", "inactive-extra"}:
        result = farfield._runtime_fingerprint()
        assert result["packages"] == {"farfield": "1.0", "dspdep": "1.0"}
        assert len(result["implementation_sha256"]) == 64
    else:
        with pytest.raises((ValueError, importlib.metadata.PackageNotFoundError)):
            farfield._runtime_fingerprint()
