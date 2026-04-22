"""Reusable OLED display logic for SSD1306 I2C modules."""

from __future__ import annotations

import board
import busio
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

from smart_bin import config


class OledDisplay:
    """Simple reusable SSD1306 OLED display helper."""

    def __init__(
        self,
        width: int = config.OLED_WIDTH,
        height: int = config.OLED_HEIGHT,
        i2c_address: int = config.OLED_I2C_ADDRESS,
        reset_pin: int | None = config.OLED_RESET_PIN,
    ) -> None:
        self.width = width
        self.height = height
        self.font = ImageFont.load_default()
        self._last_lines = ("", "", "")

        # Same I2C style as your working OLED test code.
        i2c = busio.I2C(board.SCL, board.SDA)

        reset = None
        if reset_pin is not None:
            reset = digitalio.DigitalInOut(getattr(board, f"D{reset_pin}"))

        self.display = adafruit_ssd1306.SSD1306_I2C(
            width,
            height,
            i2c,
            addr=i2c_address,
            reset=reset,
        )
        self.clear()

    def show_message(self, line1: str, line2: str = "", line3: str = "") -> None:
        """Show up to three short text lines on the OLED."""
        lines = (line1, line2, line3)
        if lines == self._last_lines:
            return

        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        draw.text((0, 0), line1, font=self.font, fill=255)
        draw.text((0, 20), line2, font=self.font, fill=255)
        draw.text((0, 40), line3, font=self.font, fill=255)

        self.display.image(image)
        self.display.show()
        self._last_lines = lines

    def show_idle(self) -> None:
        """Show the configured idle screen."""
        self.show_message(
            config.IDLE_LINE_1,
            config.IDLE_LINE_2,
            config.IDLE_LINE_3,
        )

    def show_detected(self, distance: float | None = None) -> None:
        """Show the configured detected screen, optionally including distance."""
        line3 = config.DETECTED_LINE_3
        if distance is not None:
            line3 = f"Dist: {distance:.1f} cm"

        self.show_message(
            config.DETECTED_LINE_1,
            config.DETECTED_LINE_2,
            line3,
        )

    def clear(self) -> None:
        """Clear the display."""
        self.display.fill(0)
        self.display.show()
        self._last_lines = ("", "", "")
