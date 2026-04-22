"""Reusable ultrasonic distance and presence detection logic."""

from __future__ import annotations

import statistics
from collections import deque
from typing import Deque, Optional

from gpiozero import DistanceSensor

from smart_bin import config


class UltrasonicPresenceSensor:
    """
    Reusable HC-SR04 wrapper with smoothing and debounced presence detection.

    Important hardware note:
    The HC-SR04 ECHO pin outputs 5V. Raspberry Pi GPIO is 3.3V only.
    Use a voltage divider or level shifter before connecting ECHO to the Pi.
    """

    def __init__(
        self,
        trigger_pin: int = config.TRIG_PIN,
        echo_pin: int = config.ECHO_PIN,
        threshold_cm: float = config.DISTANCE_THRESHOLD_CM,
        max_distance_cm: float = config.DISTANCE_SENSOR_MAX_CM,
        smoothing_window: int = config.SMOOTHING_WINDOW,
        present_confirm_count: int = config.PRESENT_CONFIRM_COUNT,
        absent_confirm_count: int = config.ABSENT_CONFIRM_COUNT,
        max_valid_distance_cm: float = config.MAX_VALID_DISTANCE_CM,
    ) -> None:
        self.threshold_cm = threshold_cm
        self.present_confirm_count = present_confirm_count
        self.absent_confirm_count = absent_confirm_count
        self.max_valid_distance_cm = max_valid_distance_cm

        # Keep the same simple DistanceSensor style as your working test script.
        self.sensor = DistanceSensor(echo=echo_pin, trigger=trigger_pin)

        self._samples: Deque[float] = deque(maxlen=smoothing_window)
        self._presence_counter = 0
        self._absence_counter = 0
        self._person_present = False
        self._last_raw_distance_cm: Optional[float] = None
        self._last_smoothed_distance_cm: Optional[float] = None

    def get_distance_cm(self) -> Optional[float]:
        """Return the latest raw distance in cm, or None if invalid."""
        try:
            distance_cm = self.sensor.distance * 100.0
        except Exception as exc:
            print(f"[WARN] Distance read error: {exc}")
            return None

        if distance_cm <= 0 or distance_cm > self.max_valid_distance_cm:
            return None

        self._last_raw_distance_cm = distance_cm
        return distance_cm

    def get_smoothed_distance_cm(self, new_distance_cm: Optional[float]) -> Optional[float]:
        """Update the smoothing buffer and return median-smoothed distance."""
        if new_distance_cm is not None:
            self._samples.append(new_distance_cm)

        if not self._samples:
            self._last_smoothed_distance_cm = None
            return None

        self._last_smoothed_distance_cm = statistics.median(self._samples)
        return self._last_smoothed_distance_cm

    def is_person_present(self, distance_cm: Optional[float]) -> bool:
        """Check if a distance reading counts as person present."""
        return distance_cm is not None and distance_cm < self.threshold_cm

    def update_presence_state(self) -> dict:
        """
        Read sensor, update debounced presence state, and return status details.

        Returned dictionary fields:
        - raw_distance_cm
        - smoothed_distance_cm
        - person_present
        - state_changed
        - event: 'arrived', 'left', or None
        - presence_counter
        - absence_counter
        """
        raw_distance_cm = self.get_distance_cm()
        smoothed_distance_cm = self.get_smoothed_distance_cm(raw_distance_cm)
        candidate_present = self.is_person_present(smoothed_distance_cm)

        previous_state = self._person_present

        if candidate_present:
            self._presence_counter += 1
            self._absence_counter = 0
        else:
            self._absence_counter += 1
            self._presence_counter = 0

        event = None

        if not self._person_present and self._presence_counter >= self.present_confirm_count:
            self._person_present = True
            event = "arrived"
        elif self._person_present and self._absence_counter >= self.absent_confirm_count:
            self._person_present = False
            event = "left"

        return {
            "raw_distance_cm": raw_distance_cm,
            "smoothed_distance_cm": smoothed_distance_cm,
            "person_present": self._person_present,
            "state_changed": previous_state != self._person_present,
            "event": event,
            "presence_counter": self._presence_counter,
            "absence_counter": self._absence_counter,
        }

    def close(self) -> None:
        """Release GPIO resources used by the distance sensor."""
        self.sensor.close()
