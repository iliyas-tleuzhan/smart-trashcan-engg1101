"""HX711 load cell helper."""

from __future__ import annotations

import time
from statistics import median
from gpiozero import DigitalInputDevice, DigitalOutputDevice


class HX711Sensor:
    def __init__(self, dt_pin: int, sck_pin: int, gain: int = 128) -> None:
        self.dt = DigitalInputDevice(dt_pin, pull_up=False)
        self.sck = DigitalOutputDevice(sck_pin, initial_value=False)
        self.offset = 0.0

        if gain == 128:
            self.gain_pulses = 1
        elif gain == 64:
            self.gain_pulses = 3
        elif gain == 32:
            self.gain_pulses = 2
        else:
            raise ValueError("gain must be 128, 64, or 32")

        self._prime_gain()

    def _prime_gain(self) -> None:
        for _ in range(self.gain_pulses):
            self.sck.on()
            time.sleep(0.000001)
            self.sck.off()
            time.sleep(0.000001)

    def is_ready(self) -> bool:
        return self.dt.value == 0

    def read_raw(self, timeout: float = 1.0) -> int:
        start = time.time()
        while not self.is_ready():
            if time.time() - start > timeout:
                raise TimeoutError("HX711 not ready")
            time.sleep(0.001)

        value = 0
        for _ in range(24):
            self.sck.on()
            value = (value << 1) | int(self.dt.value)
            self.sck.off()

        for _ in range(self.gain_pulses):
            self.sck.on()
            self.sck.off()

        if value & 0x800000:
            value -= 0x1000000

        return value

    def read_median(self, samples: int = 7) -> float:
        vals = []
        for _ in range(samples):
            vals.append(self.read_raw())
            time.sleep(0.01)
        return float(median(vals))

    def tare(self, samples: int = 20) -> None:
        vals = []
        for _ in range(samples):
            vals.append(self.read_raw())
            time.sleep(0.01)
        self.offset = sum(vals) / len(vals)

    def get_value(self, samples: int = 7) -> float:
        return self.read_median(samples=samples) - self.offset

    def close(self) -> None:
        self.dt.close()
        self.sck.close()
