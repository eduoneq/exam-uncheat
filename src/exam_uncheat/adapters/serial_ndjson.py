"""Serial line-JSON (NDJSON) adapter — default transport for ESP32 and
commercial detectors with USB/serial output.

Wire format: UTF-8, one JSON object per line, ``\\n`` terminated. The first
line SHOULD be a hello::

    {"schema":"exam-uncheat.hello/v1","sensor_id":"esp32s3-a","driver":"esp32-sniffer",
     "driver_version":"0.1.0","hw":"ESP32-S3-DevKitC-1","capabilities":["ble.adv"],
     "tx_capable":false}

Events may omit ``sensor`` (filled from hello) and ``schema``.
"""
from __future__ import annotations

import json
import time

from .base import Adapter


class LineParser:
    def __init__(self, default_sensor_id: str = "serial", location: dict | None = None):
        self.hello: dict | None = None
        self.default_sensor_id = default_sensor_id
        self.location = location or {}
        self.bad_lines = 0

    def parse(self, line: str | bytes) -> dict | None:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = line.strip()
        if not line or not line.startswith("{"):
            return None  # boot logs etc.
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.bad_lines += 1
            return None
        if obj.get("schema") == "exam-uncheat.hello/v1":
            if obj.get("tx_capable"):
                raise ValueError("sensor reports tx_capable=true; refusing (receive-only policy)")
            self.hello = obj
            return obj
        obj.setdefault("schema", "exam-uncheat.event/v1")
        sensor = obj.setdefault("sensor", {})
        sensor.setdefault("id", (self.hello or {}).get("sensor_id", self.default_sensor_id))
        if self.hello and "driver" not in sensor:
            sensor["driver"] = f"{self.hello.get('driver')}@{self.hello.get('driver_version')}"
        if self.location and "location" not in sensor:
            sensor["location"] = dict(self.location)
        return obj


class SerialNDJSONAdapter(Adapter):
    name = "serial-ndjson"

    def __init__(self, sink, port: str, baud: int = 115200, location: dict | None = None):
        super().__init__(sink)
        self.port, self.baud = port, baud
        self.parser = LineParser(default_sensor_id=port.split("/")[-1], location=location)

    def run(self) -> None:
        import serial  # pyserial

        while not self.stopped:
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as ser:
                    while not self.stopped:
                        raw = ser.readline()
                        if not raw:
                            continue
                        obj = self.parser.parse(raw)
                        if obj is not None:
                            self.emit(obj)
            except Exception as exc:  # unplugged, permission, etc. → retry
                self.emit({"schema": "exam-uncheat.adapter_error/v1", "adapter": self.name,
                           "port": self.port, "error": str(exc)})
                time.sleep(2)
