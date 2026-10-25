"""
Send files and folders to the Windows Recycle Bin (SHFileOperationW).

Only fixed local drives have a Recycle Bin. On network shares and most
removable drives Windows would silently delete permanently instead, so
send_to_recycle_bin refuses those paths rather than lose data unexpectedly.
"""

import ctypes
import os
import sys

_FO_DELETE = 0x0003
_FOF_SILENT = 0x0004
_FOF_NOCONFIRMATION = 0x0010
_FOF_ALLOWUNDO = 0x0040
_FOF_NOERRORUI = 0x0400
_DRIVE_FIXED = 3


if sys.platform == "win32":
    from ctypes import wintypes

    class _SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]


def has_recycle_bin(path: str) -> bool:
    """True when the path is on a fixed local drive (the only kind with a Recycle Bin)."""
    if sys.platform != "win32":
        return False
    drive = os.path.splitdrive(os.path.abspath(path))[0]
    if not drive or drive.startswith("\\\\"):
        return False
    return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == _DRIVE_FIXED


def send_to_recycle_bin(path: str) -> None:
    """Move a file or folder to the Recycle Bin. Raises OSError on failure."""
    path = os.path.abspath(path)
    if not has_recycle_bin(path):
        raise OSError(f"{path} is not on a local fixed drive, so it has no Recycle Bin.")
    op = _SHFILEOPSTRUCTW()
    op.wFunc = _FO_DELETE
    op.pFrom = path + "\0"  # the API wants a double-NUL-terminated list
    op.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_NOERRORUI | _FOF_SILENT
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise OSError(f"Recycle Bin move failed (code {rc:#x}). The file may be open in another program.")
    if os.path.exists(path):
        raise OSError("Recycle Bin move reported success but the item is still there.")
