"""Modbus flame-sensor polling for the fire dual-confirmation chain.

A background thread polls a serial flame sensor every poll_seconds: it sends
the fixed Modbus read-holding-registers query, reads the 7-byte reply and
decodes the flame register (reply hex chars [6:10], 1 = flame detected).

Graceful degradation: when the port cannot be opened (no sensor wired,
wrong COM/tty path) the monitor starts in a "sensor never fires" state and
only logs a warning — the service keeps running, and the AND fusion then
never publishes, per design.

Tests inject a fake `serial_factory`, so no real port is ever required.
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Optional, Tuple

logger = logging.getLogger("front_vision.fire_sensor")

# Modbus RTU query: slave 0x02, function 0x03 (read holding registers),
# register 0x0007, count 1, CRC 0x35F8.
DEFAULT_QUERY = bytes.fromhex("02 03 00 07 00 01 35 F8")
REPLY_LENGTH = 7


def default_sensor_port() -> str:
    """Platform default serial path for the flame sensor."""
    return "COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0"


def parse_fire_register(reply: bytes) -> Optional[int]:
    """Decode the flame register from a 7-byte Modbus reply (None if malformed)."""
    if len(reply) < REPLY_LENGTH:
        return None
    return int(reply.hex()[6:10], 16)


class FlameSensorMonitor:
    """Background serial polling thread exposing the latest flame state."""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        poll_seconds: float = 0.1,
        timeout_seconds: float = 0.5,
        query: bytes = DEFAULT_QUERY,
        serial_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._poll = poll_seconds
        self._timeout = timeout_seconds
        self._query = query
        self._serial_factory = serial_factory
        self._ser = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.available = False
        self.flame_detected = False
        self.sensor_state = 0

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
                "flame sensor port %s unavailable (%s); sensor channel disabled", self._port, exc
            )
            self._ser = None
            return False
        self.available = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="front-vision-fire-sensor", daemon=True)
        self._thread.start()
        logger.info("flame sensor monitor started (port=%s, baudrate=%d)", self._port, self._baudrate)
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
                logger.debug("flame sensor close failed", exc_info=True)
            self._ser = None
        self.available = False

    def _flush(self) -> None:
        reset_in = getattr(self._ser, "reset_input_buffer", None) or getattr(self._ser, "flushInput")
        reset_out = getattr(self._ser, "reset_output_buffer", None) or getattr(self._ser, "flushOutput")
        reset_in()
        reset_out()

    def poll_once(self) -> Optional[int]:
        """One query/reply cycle; returns the decoded register or None."""
        self._flush()
        self._ser.write(self._query)
        return parse_fire_register(self._ser.read(REPLY_LENGTH))

    def _poll_loop(self) -> None:
        while not self._stop.wait(self._poll):
            try:
                state = self.poll_once()
            except Exception:
                logger.exception("flame sensor poll failed")
                continue
            if state is None:
                continue  # short/garbled reply: keep the previous state
            self.sensor_state = int(state)
            self.flame_detected = state == 1
