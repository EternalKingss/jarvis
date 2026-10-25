"""
One dedicated thread for COM work (UI Automation, the audio API).

COM must be initialised on the thread that uses it, and the MCP SDK runs tool
handlers on arbitrary worker threads. Everything that touches pywinauto or
pycaw goes through run_com(), which runs it on a single thread that
initialised COM once at startup.
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor


def _init_com() -> None:
    if sys.platform == "win32":
        try:
            import pythoncom  # shipped with pywin32, a pywinauto dependency
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except ImportError:
            pass


_COM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="com", initializer=_init_com)


async def run_com(fn):
    """Run fn() on the COM thread and return its result."""
    return await asyncio.get_running_loop().run_in_executor(_COM_EXECUTOR, fn)
