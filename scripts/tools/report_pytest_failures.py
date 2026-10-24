"""Expose JUnit failures as actionable GitHub annotations; never alter test results."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def report_failures(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for case in ET.parse(path).iter("testcase"):
        for failure in [*case.findall("failure"), *case.findall("error")]:
            message = (
                f"{case.get('classname')}::{case.get('name')}\n"
                f"{(failure.text or failure.get('message', ''))[-15000:]}"
            )
            message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error title=Pytest failure::{message}")
            count += 1
    return count


if __name__ == "__main__":
    report_failures(Path(sys.argv[1]))
