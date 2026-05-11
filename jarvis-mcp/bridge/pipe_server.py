"""
Windows Named Pipe IPC bridge.

Runs as daemon threads alongside the MCP stdio server.
Provides a singleton `pipe_server` for pushing JSON events to the Unity HUD.

Protocol: newline-delimited JSON (\n-terminated), single line per message.
"""

import json
import logging
import os
import queue
import threading
import time
from typing import Callable, Optional

import psutil

logger = logging.getLogger(__name__)

PIPE_NAME    = r"\\.\pipe\JarvisMCP"
BUFFER_SIZE  = 65536          # 64 KB per message frame
CONNECT_TIMEOUT_MS = 5000
STATS_INTERVAL_S   = 5.0
SEND_QUEUE_MAX      = 50      # drop oldest on overflow — stale stats are worthless


class PipeServer:
    """
    Named Pipe server singleton.

    Usage:
        pipe_server.start()                    — start accept + stats threads
        pipe_server.send({"type": "..."})      — enqueue JSON event to Unity
        pipe_server.register_command_handler(fn) — called when Unity sends a command
        pipe_server.is_connected               — True while Unity is connected
    """

    def __init__(self, pipe_name: str = PIPE_NAME):
        self.pipe_name = pipe_name
        self._send_queue: queue.Queue[Optional[dict]] = queue.Queue(maxsize=SEND_QUEUE_MAX)
        self._command_handlers: list[Callable[[dict], None]] = []
        self._connected = False

    def start(self) -> None:
        threading.Thread(target=self._accept_loop, name="PipeAccept", daemon=True).start()
        threading.Thread(target=self._stats_loop,  name="PipeStats",  daemon=True).start()
        logger.info("Named Pipe server started: %s", self.pipe_name)

    def send(self, event: dict) -> None:
        """Thread-safe: enqueue a JSON event for Unity. Drops silently if queue is full."""
        try:
            self._send_queue.put_nowait(event)
        except queue.Full:
            # Drop the oldest item and retry once
            try:
                self._send_queue.get_nowait()
                self._send_queue.put_nowait(event)
            except (queue.Empty, queue.Full):
                pass

    def register_command_handler(self, fn: Callable[[dict], None]) -> None:
        self._command_handlers.append(fn)

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Internal threads ────────────────────────────────────────────────────

    def _accept_loop(self) -> None:
        """Outer loop: create a pipe instance, wait for Unity, handle one client at a time."""
        try:
            import win32pipe, win32file  # type: ignore[import]
        except ImportError:
            logger.warning("pywin32 not installed — Named Pipe bridge disabled. Install with: pip install pywin32")
            return

        while True:
            handle = None
            try:
                handle = win32pipe.CreateNamedPipe(
                    self.pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    BUFFER_SIZE, BUFFER_SIZE,
                    CONNECT_TIMEOUT_MS,
                    None,
                )
                logger.info("Pipe ready, waiting for Unity client...")
                win32pipe.ConnectNamedPipe(handle, None)  # blocks until Unity connects
                logger.info("Unity client connected.")
                self._connected = True
                self._handle_client(handle)
            except Exception as e:
                logger.error("Pipe accept error: %s", e)
                time.sleep(1.0)
            finally:
                self._connected = False
                if handle:
                    try:
                        import win32file
                        win32file.CloseHandle(handle)
                    except Exception:
                        pass
                # Drain queue so it doesn't fill up while disconnected
                while not self._send_queue.empty():
                    try:
                        self._send_queue.get_nowait()
                    except queue.Empty:
                        break

    def _handle_client(self, handle) -> None:
        """Manage one connected Unity client: writer thread + read loop."""
        import win32file  # type: ignore[import]

        writer = threading.Thread(
            target=self._writer_loop, args=(handle,), name="PipeWriter", daemon=True
        )
        writer.start()

        try:
            while True:
                try:
                    _, data = win32file.ReadFile(handle, BUFFER_SIZE)
                    if not data:
                        break
                    raw = data.decode("utf-8").strip()
                    if not raw:
                        continue
                    msg = json.loads(raw)
                    self._dispatch_command(msg)
                except Exception as e:
                    logger.warning("Pipe read error (client disconnected?): %s", e)
                    break
        finally:
            self._connected = False
            self._send_queue.put(None)  # sentinel — tells writer to exit
            writer.join(timeout=2.0)
            logger.info("Unity client disconnected.")

    def _writer_loop(self, handle) -> None:
        """Drain _send_queue and write newline-delimited JSON to the pipe."""
        import win32file  # type: ignore[import]

        while True:
            item = self._send_queue.get()
            if item is None:
                break  # sentinel — exit cleanly
            if item.get("type") == "ping":
                # Expect pong back — handled in read loop; just send
                pass
            try:
                payload = (json.dumps(item) + "\n").encode("utf-8")
                win32file.WriteFile(handle, payload)
            except Exception as e:
                logger.warning("Pipe write error: %s", e)
                break

    def _dispatch_command(self, msg: dict) -> None:
        """Route a command received from Unity to registered handlers."""
        msg_type = msg.get("type", "")

        # Built-in ping/pong keepalive
        if msg_type == "ping":
            self.send({"type": "pong"})
            return

        for fn in self._command_handlers:
            try:
                fn(msg)
            except Exception as e:
                logger.error("Command handler error: %s", e)

    def _stats_loop(self) -> None:
        """Send system_stats heartbeat every STATS_INTERVAL_S while Unity is connected."""
        while True:
            time.sleep(STATS_INTERVAL_S)
            if self._connected:
                try:
                    self.send({
                        "type":    "system_stats",
                        "cpu_pct": psutil.cpu_percent(),
                        "ram_pct": psutil.virtual_memory().percent,
                    })
                except Exception as e:
                    logger.warning("Stats collection error: %s", e)


# Module-level singleton
pipe_server = PipeServer()
