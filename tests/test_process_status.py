import os

import pytest
from ocf_tools import process_status


@pytest.mark.unit
def test_posix_pid_probe_distinguishes_missing_and_permission_denied(monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX signal-zero semantics are not used on Windows")
    calls = []

    def kill(pid, sig):
        calls.append((pid, sig))
        if pid == 22:
            raise ProcessLookupError(pid)
        if pid == 33:
            raise PermissionError(pid)

    monkeypatch.setattr(process_status.os, "kill", kill)
    assert process_status.process_is_alive(None) is False
    assert process_status.process_is_alive(0) is False
    assert process_status.process_is_alive(11) is True
    assert process_status.process_is_alive(22) is False
    assert process_status.process_is_alive(33) is True
    assert calls == [(11, 0), (22, 0), (33, 0)]


@pytest.mark.unit
def test_windows_pid_probe_uses_query_only_handle_and_never_sends_a_signal():
    calls = []

    class Kernel:
        def OpenProcess(self, access, inherit, pid):
            calls.append(("open", access, inherit, pid))
            return {41: 101, 42: 102}.get(pid)

        @staticmethod
        def GetExitCodeProcess(process, result):
            result._obj.value = 259 if process == 101 else 0
            return 1

        @staticmethod
        def CloseHandle(process):
            calls.append(("close", process))
            return 1

    errors = {7: 87, 8: 5}

    def probe(pid):
        return process_status._windows_process_is_alive(
            pid, kernel32=Kernel(), last_error=lambda: errors[pid]
        )

    assert (
        process_status._windows_process_is_alive(41, kernel32=Kernel(), last_error=lambda: 0)
        is True
    )
    assert (
        process_status._windows_process_is_alive(42, kernel32=Kernel(), last_error=lambda: 0)
        is False
    )
    assert probe(7) is False
    assert probe(8) is True
    assert calls[:4] == [
        ("open", 0x1000, False, 41),
        ("close", 101),
        ("open", 0x1000, False, 42),
        ("close", 102),
    ]
