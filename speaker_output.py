"""Reusable speaker / text-to-speech logic."""

from __future__ import annotations

import subprocess
import threading
import time

from smart_bin import config


class SpeakerOutput:
    """Simple asynchronous text-to-speech wrapper around espeak-ng."""

    def __init__(
        self,
        command: str = config.ESPEAK_COMMAND,
        speed_wpm: int = config.ESPEAK_SPEED_WPM,
        voice: str = config.ESPEAK_VOICE,
        cooldown_sec: float = config.SPEECH_COOLDOWN_SEC,
    ) -> None:
        self.command = command
        self.speed_wpm = speed_wpm
        self.voice = voice
        self.cooldown_sec = cooldown_sec

        self._lock = threading.Lock()
        self._speaking = False
        self._last_spoken_at = 0.0

    def can_speak(self) -> bool:
        """Return True if speech is allowed right now."""
        with self._lock:
            return (
                not self._speaking
                and (time.monotonic() - self._last_spoken_at) >= self.cooldown_sec
            )

    def speak(self, text: str, force: bool = False) -> bool:
        """
        Speak text asynchronously.

        Returns True if playback was started, False if blocked by cooldown
        or current playback.
        """
        with self._lock:
            now = time.monotonic()
            if not force:
                if self._speaking or (now - self._last_spoken_at) < self.cooldown_sec:
                    return False

            self._speaking = True
            self._last_spoken_at = now

        thread = threading.Thread(target=self._run_speech, args=(text,), daemon=True)
        thread.start()
        return True

    def announce_person_detected(self) -> bool:
        """Play the default announcement for a newly detected person."""
        return self.speak(config.PERSON_DETECTED_SPOKEN_TEXT)

    def _run_speech(self, text: str) -> None:
        try:
            subprocess.run(
                [
                    self.command,
                    "-s",
                    str(self.speed_wpm),
                    "-v",
                    self.voice,
                    text,
                ],
                check=False,
            )
            print("[INFO] Spoken message played.")
        except FileNotFoundError:
            print(f"[ERROR] '{self.command}' not found. Install espeak-ng first.")
        finally:
            with self._lock:
                self._speaking = False
