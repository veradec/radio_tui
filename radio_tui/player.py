from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlayerState:
    station_name: str = ""
    stream_url: str = ""
    media_title: str = ""
    volume: int = 50
    muted: bool = False
    playing: bool = False
    offline: bool = False


class MpvPlayer:
    def __init__(self, socket_path: Path | None = None) -> None:
        self.socket_path = socket_path or Path("/tmp/radio_tui_mpvsocket")
        self.state = PlayerState()
        self._process: subprocess.Popen[bytes] | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_polling = threading.Event()
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return shutil.which("mpv") is not None and shutil.which("socat") is not None

    def _ipc(self, command: list[str]) -> dict | None:
        if not self.socket_path.exists():
            return None
        payload = json.dumps({"command": command}) + "\n"
        try:
            result = subprocess.run(
                ["socat", "-", str(self.socket_path)],
                input=payload.encode(),
                capture_output=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if not result.stdout:
            return None
        try:
            return json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return None

    def _ensure_mpv(self, stream_url: str, volume: int) -> None:
        if self._process and self._process.poll() is None:
            return
        self._stop_polling.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=1)
        self._stop_polling.clear()
        if self.socket_path.exists():
            self.socket_path.unlink(missing_ok=True)
        self._process = subprocess.Popen(
            [
                "mpv",
                f"--volume={volume}",
                f"--input-ipc-server={self.socket_path}",
                "--idle=yes",
                "--no-terminal",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if self.socket_path.exists():
                break
            time.sleep(0.1)

    def play(self, station_name: str, stream_url: str) -> None:
        with self._lock:
            volume = self.state.volume
            self._ensure_mpv(stream_url, volume)
            if self._process and self._process.poll() is None and self.socket_path.exists():
                self._ipc(["loadfile", stream_url])
            self.state.station_name = station_name
            self.state.stream_url = stream_url
            self.state.media_title = "Connecting..."
            self.state.playing = True
            self.state.offline = False
            self._start_poll()

    def stop(self) -> None:
        with self._lock:
            self._stop_polling.set()
            if self._poll_thread:
                self._poll_thread.join(timeout=1)
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None
            self.socket_path.unlink(missing_ok=True)
            self.state = PlayerState(volume=self.state.volume)

    def adjust_volume(self, delta: int) -> None:
        with self._lock:
            self._ipc(["add", "volume", delta])
            response = self._ipc(["get_property", "volume"])
            if response and "data" in response:
                self.state.volume = int(response["data"])

    def toggle_mute(self) -> None:
        with self._lock:
            self._ipc(["cycle", "mute"])
            response = self._ipc(["get_property", "mute"])
            if response and "data" in response:
                self.state.muted = bool(response["data"])

    def _start_poll(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            self._stop_polling.set()
            self._poll_thread.join(timeout=1)
        self._stop_polling.clear()

        def poll() -> None:
            misses = 0
            while not self._stop_polling.is_set():
                response = self._ipc(["get_property", "media-title"])
                title = ""
                if response and response.get("data"):
                    title = str(response["data"])
                if title:
                    misses = 0
                    with self._lock:
                        self.state.media_title = title
                        self.state.offline = title == "Station Offline"
                else:
                    misses += 1
                    if misses >= 3:
                        with self._lock:
                            self.state.media_title = "Station Offline"
                            self.state.offline = True
                self._stop_polling.wait(3)

        self._poll_thread = threading.Thread(target=poll, daemon=True)
        self._poll_thread.start()

    def snapshot(self) -> PlayerState:
        with self._lock:
            return PlayerState(
                station_name=self.state.station_name,
                stream_url=self.state.stream_url,
                media_title=self.state.media_title,
                volume=self.state.volume,
                muted=self.state.muted,
                playing=self.state.playing,
                offline=self.state.offline,
            )
