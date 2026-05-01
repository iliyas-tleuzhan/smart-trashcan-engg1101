"""Configuration constants for the smart bin user-detection subsystem."""

# GPIO pins for HC-SR04
TRIG_PIN = 23
ECHO_PIN = 24

# OLED display settings
OLED_I2C_ADDRESS = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_RESET_PIN = None

# Distance / presence detection settings
# Keep the repo's more permissive user-detection settings while limiting this
# file to the user-detection subsystem only.
DISTANCE_THRESHOLD_CM = 20.0
MEASUREMENT_INTERVAL_SEC = 0.2
SMOOTHING_WINDOW = 5
PRESENT_CONFIRM_COUNT = 1
ABSENT_CONFIRM_COUNT = 2
MAX_VALID_DISTANCE_CM = 400.0

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

DETECTED_LINE_1 = "Hello master"
DETECTED_LINE_2 = ""
DETECTED_LINE_3 = ""

# Spoken messages
PERSON_DETECTED_SPOKEN_TEXT = "Hi"
