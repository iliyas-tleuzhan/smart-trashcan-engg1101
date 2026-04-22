# smart-trashcan-engg1101

Raspberry Pi smart-bin software for sorting trash with a YOLOv8 camera model,
ultrasonic presence detection, an HX711 weight sensor, OLED status messages,
speaker prompts, and servo-controlled bin lids.

## Current Behavior

1. Waits for a person using the ultrasonic presence sensor.
2. Shows and speaks:
   `please show your trash to the camera and wait while the trash is scanned`
3. Runs YOLOv8 detection over a short confirmation window.
4. Opens the matching working bin for confirmed `plastic`, `paper`, or `metal`.
5. Shows and speaks:
   `please put the <type> trash in the open bin`
6. Closes the open lid when the HX711 detects confirmed added weight or when the
   person leaves.
7. Logs confirmed deposits to Baserow when Baserow credentials are configured.

The `general_waste` class is recognized in software, but its motor is disabled
until the replacement motor is installed.

## Hardware Mapping

The motor wiring notes use physical Raspberry Pi BOARD pins. `gpiozero` uses BCM
numbering, so the config preserves both meanings:

| Bin | BOARD pin | BCM pin | Status |
| --- | ---: | ---: | --- |
| Plastic | 12 | 18 | Enabled |
| Paper | 35 | 19 | Enabled |
| Metal | 38 | 20 | Enabled |
| General waste | 40 | 21 | Disabled |

Servo positions are configured per bin in `config.py`, with shared starting
defaults. Tune these constants during lid calibration:

- `PLASTIC_SERVO_OPEN_VALUE`
- `PLASTIC_SERVO_CLOSED_VALUE`
- `PAPER_SERVO_OPEN_VALUE`
- `PAPER_SERVO_CLOSED_VALUE`
- `METAL_SERVO_OPEN_VALUE`
- `METAL_SERVO_CLOSED_VALUE`
- `GENERAL_WASTE_SERVO_OPEN_VALUE`
- `GENERAL_WASTE_SERVO_CLOSED_VALUE`

The controller moves each servo once and then detaches it to reduce jitter.

## YOLO Model

The deployed model is expected at:

```text
yolo/best.pt
```

`config.py` points `YOLO_MODEL_PATH` to that project-local file. The original
Windows training/export location was only used as the source for copying the
model into the project.

The detector returns one of:

- `plastic`
- `paper`
- `metal`
- `general_waste`
- `None`

Detection is confirmed over multiple frames before any lid opens. The confirmation
settings are in `config.py`:

- `YOLO_DETECTION_FRAMES`
- `YOLO_FRAME_DELAY_SEC`
- `YOLO_MIN_CONFIRMATIONS`
- `YOLO_CONFIDENCE_THRESHOLD`

## Baserow Logging

Confirmed deposits are posted to Baserow only when credentials are configured.
The token is intentionally not committed.

Set these environment variables on the Raspberry Pi:

```bash
export BASEROW_API_URL="https://api.baserow.io"
export BASEROW_DATABASE_ID="423532"
export BASEROW_TABLE_ID="942811"
export BASEROW_TOKEN="your-baserow-token"
```

If `BASEROW_TOKEN` is not set, the bin still runs and logging is skipped.

## Running

Install the Raspberry Pi hardware dependencies and Python packages required by
the modules:

- `gpiozero`
- `adafruit-circuitpython-ssd1306`
- `Pillow`
- `ultralytics`
- `opencv-python` or the Pi camera stack used by deployment
- `espeak-ng`

Run from the parent directory of the `smart_bin` package:

```bash
python -m smart_bin.main
```

On shutdown, press `Ctrl+C`; the controller attempts to close the active lid and
release sensor/display resources.

## Main Files

- `main.py` - entrypoint
- `controller.py` - multi-bin state machine
- `trash_detector.py` - YOLOv8 detector adapter
- `db_logger.py` - Baserow event logging
- `config.py` - hardware pins, thresholds, servo tuning, YOLO, and Baserow config
- `sensor_presence.py` - ultrasonic presence state
- `hx711_sensor.py` - load-cell readings
- `oled_display.py` - OLED messages
- `speaker_output.py` - blocking and async speech output
