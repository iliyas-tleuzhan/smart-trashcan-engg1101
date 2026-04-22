"""Configuration constants for the smart bin subsystem."""

import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent

# GPIO pins for HC-SR04
TRIG_PIN = 23
ECHO_PIN = 24

# Servo
# Motor pin numbers from the wiring notes are physical BOARD pins.
# gpiozero uses BCM numbering, so the controller uses these BCM values.
PIN_NUMBERING_MODE = "BOARD pins documented, BCM values used by gpiozero"
PLASTIC_SERVO_BOARD_PIN = 12
PAPER_SERVO_BOARD_PIN = 35
METAL_SERVO_BOARD_PIN = 38
GENERAL_WASTE_SERVO_BOARD_PIN = 40

PLASTIC_SERVO_PIN = 18
PAPER_SERVO_PIN = 19
METAL_SERVO_PIN = 20
GENERAL_WASTE_SERVO_PIN = 21
GENERAL_WASTE_SERVO_ENABLED = False

# These servo values are hardware-tuned starting points for the current lid
# geometry. Retune each bin here if a lid does not fully open or close.
SERVO_PIN = PLASTIC_SERVO_PIN
DEFAULT_SERVO_OPEN_VALUE = 0.45
DEFAULT_SERVO_CLOSED_VALUE = -0.75

# Per-bin positions are intentionally explicit so each lid can be tuned
# independently without changing controller logic.
PLASTIC_SERVO_OPEN_VALUE = 0.45
PLASTIC_SERVO_CLOSED_VALUE = -0.75
PAPER_SERVO_OPEN_VALUE = 0.45
PAPER_SERVO_CLOSED_VALUE = -0.75
METAL_SERVO_OPEN_VALUE = 0.45
METAL_SERVO_CLOSED_VALUE = -0.75
GENERAL_WASTE_SERVO_OPEN_VALUE = 0.45
GENERAL_WASTE_SERVO_CLOSED_VALUE = -0.75

SERVO_OPEN_VALUE = DEFAULT_SERVO_OPEN_VALUE
SERVO_CLOSED_VALUE = DEFAULT_SERVO_CLOSED_VALUE
SERVO_MOVE_SETTLE_SEC = 0.5

# HX711
HX711_DT_PIN = 5
HX711_SCK_PIN = 6
WEIGHT_DELTA_THRESHOLD = 3000
WEIGHT_CONFIRM_COUNT = 3

# OLED display settings
OLED_I2C_ADDRESS = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_RESET_PIN = None

# Distance / presence detection settings
DISTANCE_THRESHOLD_CM = 20.0
MEASUREMENT_INTERVAL_SEC = 0.2
DISTANCE_SENSOR_MAX_CM = 200.0
SMOOTHING_WINDOW = 5
PRESENT_CONFIRM_COUNT = 1
ABSENT_CONFIRM_COUNT = 2
MAX_VALID_DISTANCE_CM = 400.0

# Timing
LID_SETTLE_SEC = 1.0
MIN_OPEN_TIME_SEC = 2.0
AUTO_CLOSE_TIME_SEC = 10.0

# Baserow event logging
BASEROW_API_URL = os.getenv("BASEROW_API_URL", "https://api.baserow.io")
BASEROW_DATABASE_ID = os.getenv("BASEROW_DATABASE_ID", "423532")
BASEROW_TABLE_ID = os.getenv("BASEROW_TABLE_ID", "942811")
BASEROW_TOKEN = os.getenv("BASEROW_TOKEN", "")
BASEROW_REQUEST_TIMEOUT_SEC = 5.0
BASEROW_MAX_RETRIES = 2
BASEROW_RETRY_BACKOFF_SEC = 0.5

# Speech settings
SPEECH_COOLDOWN_SEC = 10.0
ESPEAK_COMMAND = "espeak-ng"
ESPEAK_SPEED_WPM = 155
ESPEAK_VOICE = "en"

# Display messages
STARTUP_LINE_1 = "System ready"
STARTUP_LINE_2 = "Smart bin"
STARTUP_DISPLAY_SEC = 2.0

IDLE_LINE_1 = "Waiting..."
IDLE_LINE_2 = ""
IDLE_LINE_3 = ""

DETECTED_LINE_1 = "Opening lid"
DETECTED_LINE_2 = ""
DETECTED_LINE_3 = ""

SCANNING_MESSAGE = "please show your trash to the camera and wait while the trash is scanned"
UNKNOWN_TRASH_MESSAGE = "Trash type was not detected"
GENERAL_WASTE_DISABLED_MESSAGE = "general waste was detected, but that bin is not ready yet"

OPEN_LINE_1 = "Bin open"
OPEN_LINE_2 = "Drop trash"
OPEN_LINE_3 = ""

CLOSING_LINE_1 = "Closing lid"
CLOSING_LINE_2 = ""
CLOSING_LINE_3 = ""

# Spoken messages
PERSON_DETECTED_SPOKEN_TEXT = "Bin opened"

# YOLO detector
# The original Windows model path was only the source copy location:
# C:\Users\user\Downloads\best_model\runs\detect\train4\weights\best.pt
# Runtime code should use this project-local model path for deployment.
YOLO_MODEL_PATH = str(PACKAGE_DIR / "yolo" / "best.pt")
YOLO_CONFIDENCE_THRESHOLD = 0.5
YOLO_CAMERA_INDEX = 0
YOLO_CAMERA_WARMUP_FRAMES = 3
YOLO_DETECTION_FRAMES = 7
YOLO_FRAME_DELAY_SEC = 0.2
YOLO_MIN_CONFIRMATIONS = 3
TRASH_CLASSES = ("plastic", "paper", "metal", "general_waste")
