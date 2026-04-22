"""High-level multi-bin controller that orchestrates the smart bin subsystem."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from gpiozero import Servo

from smart_bin import config
from smart_bin import db_logger
from smart_bin.hx711_sensor import HX711Sensor
from smart_bin.oled_display import OledDisplay
from smart_bin.sensor_presence import UltrasonicPresenceSensor
from smart_bin.speaker_output import SpeakerOutput
from smart_bin.trash_detector import YoloTrashDetector


@dataclass(frozen=True)
class BinConfig:
    trash_type: str
    label: str
    board_pin: int
    gpiozero_pin: int
    open_value: float
    closed_value: float
    enabled: bool = True


class SmartBinController:
    STATE_IDLE = "IDLE"
    STATE_SCANNING = "SCANNING"
    STATE_BIN_OPEN = "BIN_OPEN"
    STATE_WAITING_FOR_DROP = "WAITING_FOR_DROP"
    STATE_CLOSING = "CLOSING"

    BIN_CONFIGS = {
        "plastic": BinConfig(
            "plastic",
            "plastic",
            12,
            config.PLASTIC_SERVO_PIN,
            config.PLASTIC_SERVO_OPEN_VALUE,
            config.PLASTIC_SERVO_CLOSED_VALUE,
        ),
        "paper": BinConfig(
            "paper",
            "paper",
            35,
            config.PAPER_SERVO_PIN,
            config.PAPER_SERVO_OPEN_VALUE,
            config.PAPER_SERVO_CLOSED_VALUE,
        ),
        "metal": BinConfig(
            "metal",
            "metal",
            38,
            config.METAL_SERVO_PIN,
            config.METAL_SERVO_OPEN_VALUE,
            config.METAL_SERVO_CLOSED_VALUE,
        ),
        "general_waste": BinConfig(
            "general_waste",
            "general waste",
            40,
            config.GENERAL_WASTE_SERVO_PIN,
            config.GENERAL_WASTE_SERVO_OPEN_VALUE,
            config.GENERAL_WASTE_SERVO_CLOSED_VALUE,
            enabled=config.GENERAL_WASTE_SERVO_ENABLED,
        ),
    }

    def __init__(
        self,
        sensor: UltrasonicPresenceSensor | None = None,
        display: OledDisplay | None = None,
        speaker: SpeakerOutput | None = None,
        detector: YoloTrashDetector | None = None,
        measurement_interval_sec: float = config.MEASUREMENT_INTERVAL_SEC,
    ) -> None:
        self.sensor = sensor or UltrasonicPresenceSensor()
        self.display = display or OledDisplay()
        self.speaker = speaker or SpeakerOutput()
        self.detector = detector or YoloTrashDetector()
        self.measurement_interval_sec = measurement_interval_sec

        self.scale = HX711Sensor(
            dt_pin=config.HX711_DT_PIN,
            sck_pin=config.HX711_SCK_PIN,
        )

        self.state = self.STATE_IDLE
        self.open_time = 0.0
        self.baseline_weight = 0.0
        self.weight_confirm_counter = 0
        self.open_bin: BinConfig | None = None
        self.current_session_id: str | None = None

    def run(self) -> None:
        print("[INFO] Starting smart bin.")
        time.sleep(2)
        self.scale.tare(samples=20)
        db_logger.init_db()
        self.show_idle()

        while True:
            self.process_cycle()
            time.sleep(self.measurement_interval_sec)

    def process_cycle(self) -> None:
        status = self.sensor.update_presence_state()
        distance_cm = status["smoothed_distance_cm"]
        event = status["event"]

        if self.state == self.STATE_IDLE:
            self.show_idle()
            if event == "arrived":
                self.start_scanning(distance_cm)
            return

        if self.state == self.STATE_WAITING_FOR_DROP:
            self.check_for_close(status)

    def start_scanning(self, distance_cm: float | None = None) -> None:
        self.start_session(distance_cm)
        self.state = self.STATE_SCANNING
        self.display_stage_message(config.SCANNING_MESSAGE)
        self.speaker.speak_blocking(config.SCANNING_MESSAGE, force=True)

        trash_type = self.scan_confirmed_trash_type()
        if trash_type is None:
            self.display_stage_message(config.UNKNOWN_TRASH_MESSAGE)
            self.speaker.speak_blocking(config.UNKNOWN_TRASH_MESSAGE, force=True)
            self.close_session(distance_cm, notes="unknown_trash")
            self.state = self.STATE_IDLE
            return

        bin_config = self.BIN_CONFIGS.get(trash_type)
        if bin_config is None:
            self.display_stage_message(config.UNKNOWN_TRASH_MESSAGE)
            self.speaker.speak_blocking(config.UNKNOWN_TRASH_MESSAGE, force=True)
            self.close_session(distance_cm, notes="unsupported_trash_type")
            self.state = self.STATE_IDLE
            return

        if not bin_config.enabled:
            self.handle_disabled_bin(bin_config)
            return

        self.open_selected_bin(bin_config)

    def scan_confirmed_trash_type(self) -> str | None:
        detections: Counter[str] = Counter()
        frame_count = max(1, config.YOLO_DETECTION_FRAMES)
        min_confirmations = min(max(1, config.YOLO_MIN_CONFIRMATIONS), frame_count)
        warning_reported = False

        for frame_index in range(frame_count):
            try:
                trash_type = self.detector.detect_trash_type()
            except Exception as exc:
                if not warning_reported:
                    print(f"[WARN] YOLO detection failed: {exc}")
                    warning_reported = True
                trash_type = None

            if trash_type in self.BIN_CONFIGS:
                detections[trash_type] += 1

            if frame_index < frame_count - 1:
                time.sleep(config.YOLO_FRAME_DELAY_SEC)

        if not detections:
            return None

        ranked = detections.most_common(2)
        best_label, best_count = ranked[0]
        if best_count < min_confirmations:
            return None

        if len(ranked) > 1 and best_count == ranked[1][1]:
            return None

        return best_label

    def start_session(self, distance_cm: float | None) -> None:
        self.close_session(distance_cm, notes="session_replaced")
        try:
            self.current_session_id = db_logger.start_session(distance_cm=distance_cm)
        except Exception as exc:
            self.current_session_id = None
            print(f"[WARN] Failed to start Baserow session: {exc}")

    def close_session(
        self,
        distance_cm: float | None = None,
        notes: str | None = None,
    ) -> None:
        if not self.current_session_id:
            return

        try:
            db_logger.end_session(
                self.current_session_id,
                distance_cm=distance_cm,
                notes=notes,
            )
        except Exception as exc:
            print(f"[WARN] Failed to close Baserow session: {exc}")
        finally:
            self.current_session_id = None

    def open_selected_bin(self, bin_config: BinConfig) -> None:
        self.state = self.STATE_BIN_OPEN
        self.open_bin = bin_config
        self.move_servo_once(bin_config.gpiozero_pin, bin_config.open_value)
        self.open_time = time.time()
        self.baseline_weight = self.read_weight_or_default(samples=10)
        self.weight_confirm_counter = 0

        message = f"please put the {bin_config.label} trash in the open bin"
        self.display_stage_message(message)
        self.speaker.speak_blocking(message, force=True)
        self.state = self.STATE_WAITING_FOR_DROP

    def check_for_close(self, status: dict) -> None:
        distance_cm = status["smoothed_distance_cm"]
        person_present = status["person_present"]
        weight_now = self.read_weight_or_default(samples=5, default=None)
        if weight_now is not None:
            delta = weight_now - self.baseline_weight
        else:
            delta = 0.0

        elapsed = time.time() - self.open_time
        weight_increased = (
            elapsed >= config.MIN_OPEN_TIME_SEC
            and delta > config.WEIGHT_DELTA_THRESHOLD
        )

        if weight_increased:
            self.weight_confirm_counter += 1
        else:
            self.weight_confirm_counter = 0

        if self.weight_confirm_counter >= config.WEIGHT_CONFIRM_COUNT:
            self.log_deposit_event(
                weight_after=weight_now,
                weight_delta=delta,
                distance_cm=distance_cm,
                person_present=person_present,
            )
            self.close_open_bin(distance_cm=distance_cm, session_notes="deposit_logged")
            return

        if status["event"] == "left" or not person_present:
            self.close_open_bin(distance_cm=distance_cm, session_notes="person_left")
            return

        if elapsed >= config.AUTO_CLOSE_TIME_SEC:
            self.close_open_bin(distance_cm=distance_cm, session_notes="timeout")

    def log_deposit_event(
        self,
        weight_after: float | None,
        weight_delta: float,
        distance_cm: float | None,
        person_present: bool,
    ) -> None:
        if self.open_bin is None or weight_after is None:
            return

        try:
            db_logger.log_deposit_event(
                session_id=self.current_session_id,
                weight_before=self.baseline_weight,
                weight_after=weight_after,
                weight_delta=weight_delta,
                ultrasonic_distance_cm=distance_cm,
                person_present=person_present,
                event_type="trash_detected",
                notes="weight_increase_confirmed",
                debug_info={
                    "trash_type": self.open_bin.trash_type,
                    "bin_label": self.open_bin.label,
                    "threshold": config.WEIGHT_DELTA_THRESHOLD,
                },
            )
        except Exception as exc:
            print(f"[WARN] Failed to log Baserow deposit event: {exc}")

    def close_open_bin(
        self,
        distance_cm: float | None = None,
        session_notes: str | None = None,
    ) -> None:
        if self.open_bin is None:
            self.close_session(distance_cm, notes=session_notes)
            self.state = self.STATE_IDLE
            return

        self.state = self.STATE_CLOSING
        self.display.show_message(
            config.CLOSING_LINE_1,
            config.CLOSING_LINE_2,
            config.CLOSING_LINE_3,
        )
        self.move_servo_once(
            self.open_bin.gpiozero_pin,
            self.open_bin.closed_value,
        )
        self.open_bin = None
        self.weight_confirm_counter = 0
        self.close_session(distance_cm, notes=session_notes)
        self.state = self.STATE_IDLE
        self.show_idle()

    def handle_disabled_bin(self, bin_config: BinConfig) -> None:
        message = config.GENERAL_WASTE_DISABLED_MESSAGE
        self.display_stage_message(message)
        self.speaker.speak_blocking(message, force=True)
        self.open_bin = None
        self.weight_confirm_counter = 0
        self.close_session(notes=f"{bin_config.trash_type}_disabled")
        self.state = self.STATE_IDLE

    def move_servo_once(self, pin: int, value: float) -> None:
        servo = Servo(
            pin,
            min_pulse_width=0.0004,
            max_pulse_width=0.0030,
        )
        try:
            servo.value = value
            time.sleep(config.SERVO_MOVE_SETTLE_SEC)
        finally:
            servo.detach()
            servo.close()

    def read_weight_or_default(
        self,
        samples: int,
        default: float | None = 0.0,
    ) -> float | None:
        try:
            return self.scale.get_value(samples=samples)
        except Exception as exc:
            print(f"[WARN] HX711 read failed: {exc}")
            return default

    def display_stage_message(self, message: str) -> None:
        self.display.show_message(
            message[:21],
            message[21:42],
            message[42:63],
        )

    def show_idle(self) -> None:
        self.display.show_message(
            config.IDLE_LINE_1,
            config.IDLE_LINE_2,
            config.IDLE_LINE_3,
        )

    def cleanup(self) -> None:
        print("[INFO] Cleaning up controller resources.")
        self.close_session(notes="cleanup")

        if self.open_bin is not None:
            try:
                self.move_servo_once(
                    self.open_bin.gpiozero_pin,
                    self.open_bin.closed_value,
                )
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
