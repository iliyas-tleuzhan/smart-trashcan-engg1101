"""High-level controller that orchestrates the smart bin subsystem."""

from __future__ import annotations

import statistics
import time
from gpiozero import Servo

from smart_bin import config
from smart_bin import db_logger
from smart_bin.oled_display import OledDisplay
from smart_bin.sensor_presence import UltrasonicPresenceSensor
from smart_bin.speaker_output import SpeakerOutput
from smart_bin.hx711_sensor import HX711Sensor


class SmartBinController:
    STATE_IDLE = "IDLE"
    STATE_OPEN = "OPEN"

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

        self.servo = Servo(
            config.SERVO_PIN,
            min_pulse_width=0.0005,
            max_pulse_width=0.0024,
        )

        self.scale = HX711Sensor(
            dt_pin=config.HX711_DT_PIN,
            sck_pin=config.HX711_SCK_PIN,
        )

        self.state = self.STATE_IDLE
        self.open_time = 0.0
        self.baseline_weight = 0.0
        self.current_session_id: str | None = None
        self.pending_deposit_started_at = 0.0
        self.pending_weight_before: float | None = None

    def _reset_pending_deposit(self) -> None:
        self.pending_deposit_started_at = 0.0
        self.pending_weight_before = None

    def _read_weight(self, samples: int) -> float | None:
        try:
            return self.scale.get_value(samples=samples)
        except Exception as exc:
            print(f"[WARN] HX711 read failed: {exc}")
            return None

    def _read_baseline_weight(self) -> float:
        weight = self._read_weight(samples=config.BASELINE_READ_SAMPLES)
        return weight if weight is not None else self.baseline_weight

    def _close_active_session(self, distance_cm: float | None, notes: str | None = None) -> None:
        if not self.current_session_id:
            return

        try:
            db_logger.end_session(
                self.current_session_id,
                distance_cm=distance_cm,
                notes=notes,
            )
        except Exception as exc:
            print(f"[WARN] Failed to end session {self.current_session_id}: {exc}")
        finally:
            self.current_session_id = None

    def _start_session(self, distance_cm: float | None) -> None:
        self._close_active_session(distance_cm=distance_cm, notes="session_replaced")
        try:
            self.current_session_id = db_logger.start_session(distance_cm=distance_cm)
            print(f"[INFO] Started session {self.current_session_id}")
        except Exception as exc:
            self.current_session_id = None
            print(f"[WARN] Failed to start session: {exc}")

    def _confirm_stable_deposit(self, weight_before: float) -> tuple[bool, float | None, list[float]]:
        samples: list[float] = []

        for _ in range(config.STABLE_SAMPLE_COUNT):
            weight_sample = self._read_weight(samples=config.STABLE_READ_SAMPLES)
            if weight_sample is None:
                return False, None, samples

            samples.append(weight_sample)
            time.sleep(self.measurement_interval_sec)

        if not samples:
            return False, None, samples

        min_delta = min(sample - weight_before for sample in samples)
        confirmed = min_delta >= config.WEIGHT_CHANGE_THRESHOLD
        stabilized_weight = statistics.mean(samples)
        return confirmed, stabilized_weight, samples

    def _close_lid_and_reset(self) -> None:
        self.display.show_message(
            config.CLOSING_LINE_1,
            config.CLOSING_LINE_2,
            config.CLOSING_LINE_3,
        )
        self.close_lid()
        time.sleep(config.LID_SETTLE_SEC)
        self.state = self.STATE_IDLE
        self._reset_pending_deposit()
        self.show_idle()

    def _handle_confirmed_deposit(
        self,
        weight_before: float,
        weight_after: float,
        distance_cm: float | None,
        person_present: bool,
        stable_samples: list[float],
    ) -> None:
        weight_delta = weight_after - weight_before
        print(f"[INFO] Deposit confirmed: before={weight_before:.1f}, after={weight_after:.1f}, delta={weight_delta:.1f}")

        try:
            row_id = db_logger.log_deposit_event(
                session_id=self.current_session_id,
                weight_before=weight_before,
                weight_after=weight_after,
                weight_delta=weight_delta,
                ultrasonic_distance_cm=distance_cm,
                person_present=person_present,
                event_type="trash_detected",
                notes="stable_weight_increase",
                debug_info={
                    "stable_samples": [round(sample, 2) for sample in stable_samples],
                    "threshold": config.WEIGHT_CHANGE_THRESHOLD,
                    "stable_time_sec": config.STABLE_TIME_SEC,
                },
            )
            print(f"[INFO] Deposit event logged with id={row_id}")
        except Exception as exc:
            print(f"[WARN] Failed to log deposit event: {exc}")

        self.baseline_weight = weight_after
        self._reset_pending_deposit()

        if config.LID_CLOSE_DELAY_SEC > 0:
            time.sleep(config.LID_CLOSE_DELAY_SEC)

        self._close_lid_and_reset()

    def open_lid(self) -> None:
        self.servo.value = config.SERVO_OPEN_VALUE

    def close_lid(self) -> None:
        self.servo.value = config.SERVO_CLOSED_VALUE

    def show_idle(self) -> None:
        self.display.show_message(
            config.IDLE_LINE_1,
            config.IDLE_LINE_2,
            config.IDLE_LINE_3,
        )

    def show_open(self, distance_cm: float | None = None) -> None:
        line3 = f"Dist: {distance_cm:.1f} cm" if distance_cm is not None else ""
        self.display.show_message(
            config.OPEN_LINE_1,
            config.OPEN_LINE_2,
            line3,
        )

    def run(self) -> None:
        print("[INFO] Starting smart bin...")
        print("[INFO] Taring load cell. Keep bin still and empty.")
        time.sleep(2)
        self.scale.tare(samples=20)
        print("[INFO] Tare complete.")

        try:
            db_logger.init_db()
            print("[INFO] Event logger initialization finished.")
        except Exception as exc:
            print(f"[WARN] Database init failed: {exc}")

        self.close_lid()
        time.sleep(1)
        self.show_idle()

        while True:
            self.process_cycle()
            time.sleep(self.measurement_interval_sec)

    def process_cycle(self) -> None:
        status = self.sensor.update_presence_state()
        distance_cm = status["smoothed_distance_cm"]
        event = status["event"]
        person_present = status["person_present"]

        weight_now = self._read_weight(samples=config.WEIGHT_READ_SAMPLES)

        print(
            f"[DEBUG] state={self.state} | distance={distance_cm} | "
            f"weight={weight_now} | baseline={self.baseline_weight}"
        )

        if event == "left":
            print("[INFO] Person left the bin area")
            self.speaker.speak("bye", force=True)
            self._close_active_session(distance_cm=distance_cm, notes="person_left")

        elif event == "arrived":
            print("[INFO] Person arrived at the bin")

        if self.state == self.STATE_IDLE:
            self.show_idle()

            if event == "arrived":
                print("[STATE] Object detected near bin -> opening lid")
                self._start_session(distance_cm=distance_cm)
                self.open_lid()
                self.state = self.STATE_OPEN
                self.open_time = time.time()

                self.display.show_message(
                    config.DETECTED_LINE_1,
                    config.DETECTED_LINE_2,
                    config.DETECTED_LINE_3,
                )

                self.speaker.announce_person_detected()
                time.sleep(config.LID_SETTLE_SEC)

                self.baseline_weight = self._read_baseline_weight()
                self._reset_pending_deposit()
                print(f"[INFO] Session baseline weight set to {self.baseline_weight:.1f}")

                return

        elif self.state == self.STATE_OPEN:
            self.show_open(distance_cm)

            elapsed = time.time() - self.open_time
            delta = (weight_now - self.baseline_weight) if weight_now is not None else 0.0

            if elapsed >= config.MIN_OPEN_TIME_SEC and weight_now is not None:
                if delta >= config.WEIGHT_CHANGE_THRESHOLD:
                    if not self.pending_deposit_started_at:
                        self.pending_deposit_started_at = time.monotonic()
                        self.pending_weight_before = self.baseline_weight
                        print(f"[INFO] Possible deposit detected: delta={delta:.1f}")
                    elif time.monotonic() - self.pending_deposit_started_at >= config.STABLE_TIME_SEC:
                        weight_before = self.pending_weight_before or self.baseline_weight
                        confirmed, stabilized_weight, stable_samples = self._confirm_stable_deposit(
                            weight_before=weight_before
                        )

                        if confirmed and stabilized_weight is not None:
                            self._handle_confirmed_deposit(
                                weight_before=weight_before,
                                weight_after=stabilized_weight,
                                distance_cm=distance_cm,
                                person_present=person_present,
                                stable_samples=stable_samples,
                            )
                            return

                        print("[INFO] Deposit candidate rejected after stability check")
                        self._reset_pending_deposit()
                else:
                    self._reset_pending_deposit()

            if elapsed >= config.AUTO_CLOSE_TIME_SEC:
                print("[STATE] Timeout -> closing lid")
                self._close_lid_and_reset()

    def cleanup(self) -> None:
        print("[INFO] Cleaning up controller resources...")
        self._close_active_session(distance_cm=None, notes="cleanup")

        try:
            self.close_lid()
            time.sleep(0.5)
            self.servo.detach()
        except Exception as exc:
            print(f"[WARN] Servo cleanup issue: {exc}")

        try:
            self.scale.close()
        except Exception as exc:
            print(f"[WARN] HX711 cleanup issue: {exc}")

        try:
            self.display.clear()
        except Exception as exc:
            print(f"[WARN] OLED cleanup issue: {exc}")

        try:
            self.sensor.close()
        except Exception as exc:
            print(f"[WARN] Sensor cleanup issue: {exc}")
