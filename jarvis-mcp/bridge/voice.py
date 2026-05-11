"""
Jarvis Voice Engine.

Pipeline:
  sounddevice (mic) → Vosk (transcription only) → Claude API (reasoning + tool use)
  → ElevenLabs TTS → speakers + Unity HUD via Named Pipe

States: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE

Vosk does speech-to-text only. Claude handles all intent, reasoning,
conversation memory, and Windows control via tool_use.
"""

import json
import logging
import os
import queue
import re
import threading
import time
from enum import Enum, auto
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)

# ── Audio settings ────────────────────────────────────────────────────────────
SAMPLE_RATE          = 16000
BLOCK_SIZE           = 512            # frames per sounddevice callback (~32ms)
SILENCE_RMS          = 150            # below this = silence (tune to environment)
SILENCE_FRAMES_STOP  = 25            # ~800ms silence ends recording
MAX_COMMAND_FRAMES   = 750            # ~24s max before forced end

# ── Conversation settings ─────────────────────────────────────────────────────
MAX_HISTORY_PAIRS    = 20             # max turns kept (40 total messages)
SESSION_TIMEOUT_S    = 600            # 10 min idle → clear history
PROCESSING_TIMEOUT_S = 60            # watchdog: stuck in PROCESSING → reset
MAX_TOOL_ITERATIONS  = 8             # prevent infinite tool-call loops

# ── Claude settings ───────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-opus-4-5"

JARVIS_SYSTEM_PROMPT = """You are Jarvis, an AI assistant controlling a Windows PC via a cinematic HUD interface.

Personality: calm, precise, slightly formal — like the movie Jarvis. Concise responses. No filler phrases.

Capabilities: You have direct access to the user's Windows machine via tools. Use run_command freely \
to open applications, manage files, control media, check system status, search the web, run scripts — \
anything the user asks. You also control the visual HUD directly via send_hud_message and trigger_hud_animation.

Conversation context: You maintain full memory of this voice session. Reference prior turns naturally. \
If the user says "and what about RAM?" after asking about CPU, you know the context.

Response style: Keep spoken responses short (1-3 sentences). The user hears this via speakers — \
don't write essays. For complex results (long file lists, etc.), summarize and offer to show more."""

VOICE_TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Execute any PowerShell or CMD command on the Windows machine. "
            "Use this to open apps, check system state, manage files, control media, "
            "search the web, run scripts — anything terminal-related."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The PowerShell or CMD command to run"},
                "shell":   {"type": "string", "enum": ["powershell", "cmd"], "default": "powershell"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_system_info",
        "description": "Get CPU usage, RAM usage, disk space, battery, and uptime stats.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_hud_message",
        "description": "Display a message on the Jarvis Unity HUD overlay.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message":      {"type": "string"},
                "message_type": {"type": "string", "enum": ["info", "warning", "alert", "success"]},
            },
            "required": ["message"],
        },
    },
    {
        "name": "trigger_hud_animation",
        "description": "Trigger a visual animation on the Jarvis HUD arc reactor ring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "animation": {"type": "string", "enum": ["pulse", "alert_flash", "scan"]},
                "intensity": {"type": "number", "default": 1.0},
            },
            "required": ["animation"],
        },
    },
]


class VoiceState(Enum):
    IDLE       = auto()
    LISTENING  = auto()
    PROCESSING = auto()
    SPEAKING   = auto()


class VoiceEngine:
    def __init__(self):
        self.state             = VoiceState.IDLE
        self.is_muted          = False
        self._state_lock       = threading.Lock()
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        self._conversation_history: list[dict] = []
        self._last_wake_time   = 0.0
        self._watchdog_timer: Optional[threading.Timer] = None
        self._session_timer: Optional[threading.Timer]  = None

    def start(self) -> None:
        threading.Thread(target=self._stream_audio, name="VoiceCapture", daemon=True).start()
        threading.Thread(target=self._audio_worker, name="VoiceWorker",  daemon=True).start()
        logger.info("Voice engine started.")

    def get_state(self) -> VoiceState:
        with self._state_lock:
            return self.state

    def clear_history(self) -> None:
        self._conversation_history.clear()
        from bridge.pipe_server import pipe_server
        pipe_server.send({"type": "conversation_cleared"})
        logger.info("Conversation history cleared.")

    # ── Audio capture ─────────────────────────────────────────────────────────

    def _stream_audio(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            logger.warning("sounddevice not installed — voice capture disabled.")
            return

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug("sounddevice status: %s", status)
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass  # drop block — acceptable during PROCESSING

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                threading.Event().wait()  # keep stream alive forever
        except Exception as e:
            logger.error("sounddevice stream error: %s", e)

    # ── Audio processing ──────────────────────────────────────────────────────

    def _audio_worker(self) -> None:
        try:
            from vosk import Model, KaldiRecognizer  # type: ignore[import]
            import numpy as np
        except ImportError:
            logger.warning("vosk or numpy not installed — wake word detection disabled.")
            return

        model_path = os.environ.get("VOSK_MODEL_PATH", "").strip()
        try:
            model = Model(model_path) if model_path else Model(model_name="vosk-model-small-en-us-0.15")
        except Exception as e:
            logger.error("Failed to load Vosk model: %s", e)
            return

        kw_grammar = json.dumps(["hey jarvis", "jarvis", "[unk]"])
        kw_rec = KaldiRecognizer(model, SAMPLE_RATE, kw_grammar)
        full_rec: Optional[KaldiRecognizer] = None
        command_frames: list[bytes] = []
        silence_count = 0

        while True:
            block = self._audio_queue.get()
            state = self.get_state()

            if state == VoiceState.IDLE:
                if kw_rec.AcceptWaveform(block):
                    result = json.loads(kw_rec.Result())
                    text = result.get("text", "").lower()
                    if "jarvis" in text:
                        logger.info("Wake word detected: %r", text)
                        self._on_wake_word()
                        full_rec = KaldiRecognizer(model, SAMPLE_RATE)
                        command_frames = []
                        silence_count = 0
                        # Reset keyword recognizer for next wake word
                        kw_rec = KaldiRecognizer(model, SAMPLE_RATE, kw_grammar)

            elif state == VoiceState.LISTENING:
                command_frames.append(block)
                if full_rec:
                    full_rec.AcceptWaveform(block)

                arr = np.frombuffer(block, dtype=np.int16)
                rms = int(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                silence_count = silence_count + 1 if rms < SILENCE_RMS else 0

                if silence_count >= SILENCE_FRAMES_STOP or len(command_frames) >= MAX_COMMAND_FRAMES:
                    transcript = ""
                    if full_rec:
                        final = json.loads(full_rec.FinalResult())
                        transcript = final.get("text", "").strip()
                    logger.info("Transcribed: %r", transcript)
                    self._on_command_ready(transcript)
                    full_rec = None

            # PROCESSING / SPEAKING: audio worker idles intentionally

    # ── State transitions ─────────────────────────────────────────────────────

    def _set_state(self, new_state: VoiceState) -> None:
        with self._state_lock:
            self.state = new_state
        from bridge.pipe_server import pipe_server
        pipe_server.send({"type": "voice_state", "state": new_state.name})
        logger.debug("Voice state → %s", new_state.name)

    def _on_wake_word(self) -> None:
        if self.is_muted:
            return
        self._last_wake_time = time.time()
        self._reset_session_timer()
        from bridge.pipe_server import pipe_server
        pipe_server.send({"type": "wake_word_detected", "timestamp": time.time()})
        self._set_state(VoiceState.LISTENING)

    def _on_command_ready(self, transcript: str) -> None:
        from bridge.pipe_server import pipe_server
        pipe_server.send({"type": "listening_stop", "transcript": transcript})
        self._set_state(VoiceState.PROCESSING)
        threading.Thread(
            target=self._call_claude,
            args=(transcript,),
            name="ClaudeCall",
            daemon=True,
        ).start()

    # ── Conversation history management ───────────────────────────────────────

    def _trim_history(self) -> None:
        """Keep at most MAX_HISTORY_PAIRS turns (2 messages per turn)."""
        max_msgs = MAX_HISTORY_PAIRS * 2
        if len(self._conversation_history) > max_msgs:
            # Drop oldest 2 messages (one user+assistant pair)
            self._conversation_history = self._conversation_history[2:]

    def _reset_session_timer(self) -> None:
        if self._session_timer:
            self._session_timer.cancel()
        self._session_timer = threading.Timer(SESSION_TIMEOUT_S, self._on_session_timeout)
        self._session_timer.daemon = True
        self._session_timer.start()

    def _on_session_timeout(self) -> None:
        if self._conversation_history:
            self.clear_history()
            from bridge.pipe_server import pipe_server
            pipe_server.send({"type": "hud_message", "message": "Session timeout — memory cleared.",
                              "message_type": "info", "duration_ms": 4000})
            logger.info("Session timed out, conversation cleared.")

    # ── Claude API call ───────────────────────────────────────────────────────

    def _start_watchdog(self) -> None:
        def _fire():
            logger.warning("Watchdog fired — PROCESSING timeout.")
            from bridge.pipe_server import pipe_server
            pipe_server.send({"type": "error", "message": "Response timed out.", "recoverable": True})
            self._set_state(VoiceState.IDLE)

        self._watchdog_timer = threading.Timer(PROCESSING_TIMEOUT_S, _fire)
        self._watchdog_timer.daemon = True
        self._watchdog_timer.start()

    def _cancel_watchdog(self) -> None:
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None

    def _call_claude(self, user_text: str) -> None:
        from bridge.pipe_server import pipe_server
        import anthropic

        # Clear short/empty transcripts
        if not user_text or len(user_text) < 2:
            pipe_server.send({"type": "error", "message": "Didn't catch that.", "recoverable": True})
            self._set_state(VoiceState.IDLE)
            return

        # Check for manual clear keywords
        clear_keywords = ["clear", "start over", "forget that", "new conversation", "reset"]
        if any(kw in user_text.lower() for kw in clear_keywords):
            self.clear_history()
            self._set_state(VoiceState.IDLE)
            return

        self._conversation_history.append({"role": "user", "content": user_text})
        self._trim_history()
        pipe_server.send({"type": "response_start", "command": user_text})
        self._start_watchdog()

        client = anthropic.Anthropic()
        messages = list(self._conversation_history)
        iterations = 0
        final_text = ""

        try:
            while iterations < MAX_TOOL_ITERATIONS:
                iterations += 1
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=1024,
                    system=JARVIS_SYSTEM_PROMPT,
                    tools=VOICE_TOOLS,
                    messages=messages,
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            pipe_server.send({
                                "type":  "tool_call",
                                "tool":  block.name,
                                "input": block.input,
                            })
                            result_text = self._execute_tool(block.name, block.input)
                            tool_results.append({
                                "type":        "tool_result",
                                "tool_use_id": block.id,
                                "content":     result_text,
                            })
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user",      "content": tool_results})

                else:
                    # Final answer
                    final_text = "".join(
                        b.text for b in response.content if hasattr(b, "text")
                    )
                    self._conversation_history.append({
                        "role":    "assistant",
                        "content": response.content,
                    })
                    break

            if iterations >= MAX_TOOL_ITERATIONS and not final_text:
                final_text = "I reached my tool iteration limit. Please try a simpler request."

        except Exception as e:
            logger.error("Claude API error: %s", e)
            pipe_server.send({"type": "error", "message": str(e), "recoverable": True})
            self._set_state(VoiceState.IDLE)
            self._cancel_watchdog()
            return

        self._cancel_watchdog()
        pipe_server.send({"type": "response_end", "text": final_text})
        self._set_state(VoiceState.SPEAKING)

        # Speak the response via ElevenLabs
        self._stream_speech(final_text)
        self._set_state(VoiceState.IDLE)

    # ── Tool execution ────────────────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        from bridge.pipe_server import pipe_server

        if tool_name == "run_command":
            from utils.shell import run_command, format_result
            result = run_command(
                command=tool_input.get("command", ""),
                shell=tool_input.get("shell", "powershell"),
                timeout=tool_input.get("timeout", 30),
            )
            return format_result(result)

        elif tool_name == "get_system_info":
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()
                disks = []
                for part in psutil.disk_partitions():
                    try:
                        u = psutil.disk_usage(part.mountpoint)
                        disks.append(f"{part.device}: {u.used/1e9:.1f}/{u.total/1e9:.1f} GB ({u.percent}%)")
                    except PermissionError:
                        pass
                bat_line = ""
                try:
                    bat = psutil.sensors_battery()
                    if bat:
                        bat_line = f"\nBattery: {bat.percent:.0f}% ({'charging' if bat.power_plugged else 'on battery'})"
                except Exception:
                    pass
                return (
                    f"CPU: {cpu}%  |  RAM: {mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB ({mem.percent}%)"
                    f"  |  Swap: {swap.used/1e9:.1f} GB{bat_line}"
                    f"\nDisks: {', '.join(disks) or 'none'}"
                )
            except Exception as e:
                return f"System info error: {e}"

        elif tool_name == "send_hud_message":
            pipe_server.send({
                "type":         "hud_message",
                "message":      tool_input.get("message", ""),
                "message_type": tool_input.get("message_type", "info"),
                "duration_ms":  5000,
            })
            return "HUD message sent."

        elif tool_name == "trigger_hud_animation":
            pipe_server.send({
                "type":      "hud_animation",
                "animation": tool_input.get("animation", "pulse"),
                "intensity": tool_input.get("intensity", 1.0),
            })
            return "Animation triggered."

        return f"Unknown tool: {tool_name}"

    # ── ElevenLabs TTS ────────────────────────────────────────────────────────

    def _stream_speech(self, text: str) -> None:
        """Split on sentence boundaries and speak each sentence via ElevenLabs."""
        if not text.strip():
            return
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sentence in sentences:
            if sentence.strip():
                self._speak_sentence(sentence.strip())

    def _speak_sentence(self, text: str) -> None:
        from bridge.pipe_server import pipe_server

        api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not api_key:
            logger.warning("ELEVENLABS_API_KEY not set — skipping TTS.")
            return

        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
        pipe_server.send({"type": "speaking_start"})

        try:
            from elevenlabs.client import ElevenLabs  # type: ignore[import]
            from elevenlabs import stream as el_stream  # type: ignore[import]

            client = ElevenLabs(api_key=api_key)
            audio_stream = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128",
            )
            el_stream(audio_stream)

        except ImportError:
            logger.warning("elevenlabs package not installed — skipping TTS.")
        except Exception as e:
            logger.error("ElevenLabs TTS error: %s", e)
        finally:
            pipe_server.send({"type": "speaking_end"})

    # ── Command handler (from Unity) ──────────────────────────────────────────

    def handle_pipe_command(self, msg: dict) -> None:
        msg_type = msg.get("type", "")

        if msg_type == "mute_voice":
            self.is_muted = msg.get("muted", True)
            logger.info("Voice muted: %s", self.is_muted)

        elif msg_type == "force_listen":
            if not self.is_muted and self.get_state() == VoiceState.IDLE:
                logger.info("Force listen triggered from Unity.")
                self._on_wake_word()

        elif msg_type == "clear_memory":
            self.clear_history()


# Module-level singleton — started on import
voice_engine = VoiceEngine()
voice_engine.start()

# Register Unity command handler with the pipe server
from bridge.pipe_server import pipe_server
pipe_server.register_command_handler(voice_engine.handle_pipe_command)
