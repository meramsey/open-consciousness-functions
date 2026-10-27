"""Passive process-existence probes for durable job and lock coordination."""

from __future__ import annotations

import os


def _windows_process_is_alive(pid, *, kernel32=None, last_error=None):
    """Query process state without sending CTRL_C_EVENT or terminating it."""
    import ctypes
    from ctypes import wintypes

    if kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        error = (last_error or ctypes.get_last_error)()
        if error == 5:  # ERROR_ACCESS_DENIED: conservatively regard the PID as live.
            return True
        if error in {87, 1168}:  # ERROR_INVALID_PARAMETER / ERROR_NOT_FOUND
            return False
        if hasattr(ctypes, "WinError"):
            raise ctypes.WinError(error)
        raise OSError(error, "OpenProcess failed")
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            error = (last_error or ctypes.get_last_error)()
            if hasattr(ctypes, "WinError"):
                raise ctypes.WinError(error)
            raise OSError(error, "GetExitCodeProcess failed")
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(process)


def process_is_alive(pid: int | None) -> bool:
    """Return whether a PID is alive, using a non-signalling Windows query."""
    if type(pid) is not int or pid < 1:
        return False
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
