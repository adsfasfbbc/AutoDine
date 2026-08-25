"""Modbus environmental sensor polling for the fire multi-channel chain.

A single background thread polls one Modbus-RTU slave (address 0x02, 9600
8N1) for the seven fire-relevant holding registers:

    0x0001 TVOC (ppb)        0x0002 temperature (°C, signed int16)
    0x0003 humidity (%RH)    0x0005 PM2.5 (μg/m³)
    0x0007 flame (0/1)       0x0008 light intensity
    0x0009 CO2 (ppm)

Every query carries a CRC16 checksum and every reply is CRC-verified and
decoded as a signed 16-bit integer (negative temperatures decode correctly).
A register whose round-trip fails (short reply, bad CRC) is recorded as None
for that round without aborting the rest of the round.

Graceful degradation: when the port cannot be opened (no sensor wired,
wrong COM/tty path) the monitor starts in an "all channels unread" state and
only logs a warning — the service keeps running, and the fusion then only
sees the vision channel.

Tests inject a fake `serial_factory`, so no real port is ever required.
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Dict, Optional

logger = logging.getLogger("front_vision.env_sensor")

SLAVE_ADDRESS = 0x02
REPLY_LENGTH = 7

# Channel name -> holding register address (same slave for all channels).
REGISTERS: Dict[str, int] = {
    "tvoc": 0x0001,
    "temperature": 0x0002,
    "humidity": 0x0003,
    "pm25": 0x0005,
    "flame": 0x0007,
    "light": 0x0008,
    "co2": 0x0009,
}


def default_sensor_port() -> str:
    """Platform default serial path for the sensor slave."""
    return "COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0"


def calc_crc16(data: bytes) -> int:
    """Modbus CRC16 (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x01 else crc >> 1
    return crc


def build_query(register: int, slave: int = SLAVE_ADDRESS) -> bytes:
    """Read-holding-registers query for one register, with CRC16 appended."""
    body = bytes([slave, 0x03, (register >> 8) & 0xFF, register & 0xFF, 0x00, 0x01])
    crc = calc_crc16(body)
    return body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def parse_register_reply(reply: bytes) -> Optional[int]:
    """CRC-verified decode of a 7-byte reply into a signed int16 (None if bad)."""
    if len(reply) != REPLY_LENGTH:
        return None
    payload, crc_lo, crc_hi = reply[:-2], reply[-2], reply[-1]
    if crc_lo + (crc_hi << 8) != calc_crc16(payload):
        return None
    value = (reply[3] << 8) + reply[4]
    return value - 0x10000 if value >= 0x8000 else value


class EnvSensorMonitor:
    """Background serial polling thread exposing the latest channel readings."""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        poll_seconds: float = 0.1,
        timeout_seconds: float = 0.5,
        serial_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._poll = poll_seconds
        self._timeout = timeout_seconds
        self._serial_factory = serial_factory
        self._ser = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.available = False
        # Latest signed reading per channel; None = never read or last round failed.
        self.readings: Dict[str, Optional[int]] = {name: None for name in REGISTERS}

    @property
    def flame_detected(self) -> bool:
        return self.readings["flame"] == 1

    def _open_serial(self):
        if self._serial_factory is not None:
            return self._serial_factory()
        import serial  # type: ignore  # pyserial, imported lazily

        return serial.Serial(self._port, baudrate=self._baudrate, timeout=self._timeout)

    def start(self) -> bool:
        """Open the port and start polling; returns False (degraded) on failure."""
        try:
            self._ser = self._open_serial()
        except Exception as exc:
            logger.warning(
                "env sensor port %s unavailable (%s); sensor channels disabled", self._port, exc
            )
            self._ser = None
            return False
        self.available = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="front-vision-env-sensor", daemon=True)
        self._thread.start()
        logger.info(
            "env sensor monitor started (port=%s, baudrate=%d, channels=%d)",
            self._port, self._baudrate, len(REGISTERS),
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                logger.debug("env sensor close failed", exc_info=True)
            self._ser = None
        self.available = False

    def _flush(self) -> None:
        reset_in = getattr(self._ser, "reset_input_buffer", None) or getattr(self._ser, "flushInput")
        reset_out = getattr(self._ser, "reset_output_buffer", None) or getattr(self._ser, "flushOutput")
        reset_in()
        reset_out()

    def read_register(self, register: int) -> Optional[int]:
        """One query/reply cycle for a single register (None on failure)."""
        self._flush()
        self._ser.write(build_query(register))
        return parse_register_reply(self._ser.read(REPLY_LENGTH))

    def poll_round(self) -> Dict[str, Optional[int]]:
        """Poll every register once; a failed register becomes None for this round."""
        for name, register in REGISTERS.items():
            try:
                self.readings[name] = self.read_register(register)
            except Exception:
                logger.exception("env sensor register 0x%04X (%s) poll failed", register, name)
                self.readings[name] = None
        return dict(self.readings)

    def _poll_loop(self) -> None:
        while not self._stop.wait(self._poll):
            try:
                self.poll_round()
            except Exception:
                logger.exception("env sensor poll round failed")
