"""High-level controller that orchestrates the smart bin user-detection subsystem."""

from __future__ import annotations

import time

import config
from oled_display import OledDisplay
from sensor_presence import UltrasonicPresenceSensor
from speaker_output import SpeakerOutput


class SmartBinController:
    """Coordinates sensor, display, and speaker while keeping modules decoupled."""

    STATE_IDLE = "IDLE"
    STATE_PERSON_PRESENT = "PERSON_PRESENT"

    def __init__(
        self,
        sensor: UltrasonicPresenceSensor | None = None,
        display: OledDisplay | None = None,
        speaker: SpeakerOutput | None = None,
        measurement_interval_sec: float = config.MEASUREMENT_INTERVAL_SEC,
    ) -> None:
        self.sensor = sensor or UltrasonicPresenceSensor()
        self.display = display or OledDisplay()
        self.speaker = speaker or SpeakerOutput()
        self.measurement_interval_sec = measurement_interval_sec
        self.state = self.STATE_IDLE

    def handle_idle_state(self) -> None:
        self.display.show_idle()

    def handle_person_present_state(self, distance_cm: float | None = None) -> None:
        self.display.show_detected(distance=distance_cm)

    def process_cycle(self) -> None:
        status = self.sensor.update_presence_state()

        raw_distance_cm = status["raw_distance_cm"]
        smoothed_distance_cm = status["smoothed_distance_cm"]
        person_present = status["person_present"]
        event = status["event"]
        presence_counter = status["presence_counter"]
        absence_counter = status["absence_counter"]

        raw_text = f"{raw_distance_cm:6.1f} cm" if raw_distance_cm is not None else "invalid"
        smooth_text = (
            f"{smoothed_distance_cm:6.1f} cm"
            if smoothed_distance_cm is not None
            else "invalid"
        )

        print(
            f"[DEBUG] raw={raw_text} | smooth={smooth_text} | "
            f"presence_count={presence_counter} | absence_count={absence_counter} | "
            f"state={self.state}"
        )

        if event == "arrived":
            self.state = self.STATE_PERSON_PRESENT
            print("[STATE] Person became PRESENT.")
            self.handle_person_present_state(smoothed_distance_cm)
            if self.speaker.announce_person_detected():
                print("[INFO] Triggered speech.")
            else:
                print("[INFO] Speech skipped due to cooldown or active playback.")
            return

        if event == "left":
            self.state = self.STATE_IDLE
            print("[STATE] Person became ABSENT.")
            self.handle_idle_state()
            return

        if person_present:
            self.state = self.STATE_PERSON_PRESENT
            self.handle_person_present_state(smoothed_distance_cm)
        else:
            self.state = self.STATE_IDLE
            self.handle_idle_state()

    def run(self) -> None:
        print("[INFO] Smart bin controller starting...")
        print(
            "[INFO] Threshold: "
            f"{config.DISTANCE_THRESHOLD_CM:.1f} cm | "
            f"Present confirm: {config.PRESENT_CONFIRM_COUNT} | "
            f"Absent confirm: {config.ABSENT_CONFIRM_COUNT}"
        )
        print("[INFO] Press Ctrl+C to stop.")

        self.display.show_message(config.STARTUP_LINE_1, config.STARTUP_LINE_2)
        time.sleep(config.STARTUP_DISPLAY_SEC)
        self.display.clear()
        self.handle_idle_state()

        while True:
            self.process_cycle()
            time.sleep(self.measurement_interval_sec)

    def cleanup(self) -> None:
        print("[INFO] Cleaning up controller resources...")
        try:
            self.display.clear()
        except Exception as exc:
            print(f"[WARN] OLED cleanup issue: {exc}")

        try:
            self.sensor.close()
        except Exception as exc:
            print(f"[WARN] Sensor cleanup issue: {exc}")
