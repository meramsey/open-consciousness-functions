"""Build hook; runtime data remains authoritative in the source directories."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts/tools"))
from build_package_data import BuildWithData  # noqa: E402
from setuptools import setup  # noqa: E402

setup(cmdclass={"build_py": BuildWithData})
