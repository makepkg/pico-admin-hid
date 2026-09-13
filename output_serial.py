"""output_serial.py — USB Serial (CDC data) output handler."""

import time
import json
import usb_cdc
from output_base import OutputHandler


class SerialOutput(OutputHandler):
    """USB Serial (CDC data port) output handler.

    Поддерживаемые actions:
    - send: отправить строку как есть (value)
    - send_line: отправить строку + перевод строки (value)
    - event: отправить JSON-событие {"event": name, "uptime": ..., ...data} + "\n"
    """

    def __init__(self, name, config):
        super().__init__(name, config)
        self._serial = None
        self._init_attempted = False

        print(f"[output:{name}] Serial handler created (will init on first use)")

    def execute(self, action):
        if not self.enabled:
            print(f"[output:{self.name}] Disabled — skip")
            return False

        if not self._init_attempted:
            self._init_attempted = True
            try:
                self._serial = usb_cdc.data
                if self._serial is not None:
                    self._serial.write_timeout = 0
                print(f"[output:{self.name}] Serial data port initialized")
            except Exception as e:
                print(f"[output:{self.name}] Failed to init serial:", e)
                self._enabled = False
                return False

        if self._serial is None:
            print(f"[output:{self.name}] usb_cdc.data not available — skip")
            return False

        if not self._serial.connected:
            print(f"[output:{self.name}] Host not listening — skip")
            return False

        act = action.get("action")

        try:
            if act == "send":
                value = action.get("value", "")
                self._serial.write(value.encode("utf-8"))
                print(f"[output:{self.name}] send: '{value}'")

            elif act == "send_line":
                value = action.get("value", "")
                self._serial.write((value + "\n").encode("utf-8"))
                print(f"[output:{self.name}] send_line: '{value}'")

            elif act == "event":
                payload = {
                    "event": action.get("name", ""),
                    "uptime": time.monotonic(),
                }
                extra = action.get("data")
                if isinstance(extra, dict):
                    payload.update(extra)
                line = json.dumps(payload) + "\n"
                self._serial.write(line.encode("utf-8"))
                print(f"[output:{self.name}] event: {line.strip()}")

            else:
                print(f"[output:{self.name}] Unknown action: {act}")
                return False

            return True

        except OSError as e:
            print(f"[output:{self.name}] Serial write failed (buffer full?):", e)
            return False
        except Exception as e:
            print(f"[output:{self.name}] Error in action '{act}':", e)
            return False

    def cleanup(self):
        pass
