"""output_mouse.py — USB HID Mouse output handler."""

import usb_hid
import supervisor
from adafruit_hid.mouse import Mouse
from output_base import OutputHandler


class MouseOutput(OutputHandler):
    """Output handler для USB HID мыши (трек-болл и т.д.)."""

    def __init__(self, name, config):
        super().__init__(name, config)
        self._mouse = None  # lazy init, как у HidOutput — на первом execute()

    def _ensure_mouse(self):
        if self._mouse is not None:
            return True
        try:
            self._mouse = Mouse(usb_hid.devices)
            return True
        except Exception as e:
            print(f"[output:{self.name}] Mouse init failed:", e)
            return False

    def execute(self, action):
        if not self.enabled:
            return False

        if not supervisor.runtime.usb_connected:
            print(f"[output:{self.name}] USB not connected — skip")
            return False

        if not self._ensure_mouse():
            return False

        act = action.get("action")

        try:
            if act == "move":
                dx = action.get("dx", 0)
                dy = action.get("dy", 0)
                self._mouse.move(x=dx, y=dy)
                return True

            elif act == "click":
                button = action.get("button", "left")
                btn_map = {
                    "left": Mouse.LEFT_BUTTON,
                    "right": Mouse.RIGHT_BUTTON,
                    "middle": Mouse.MIDDLE_BUTTON,
                }
                b = btn_map.get(button)
                if b is None:
                    print(f"[output:{self.name}] Unknown button: {button}")
                    return False
                self._mouse.click(b)
                return True

            elif act == "press":
                button = action.get("button", "left")
                btn_map = {
                    "left": Mouse.LEFT_BUTTON,
                    "right": Mouse.RIGHT_BUTTON,
                    "middle": Mouse.MIDDLE_BUTTON,
                }
                b = btn_map.get(button)
                if b is None:
                    return False
                self._mouse.press(b)
                return True

            elif act == "release":
                button = action.get("button", "left")
                btn_map = {
                    "left": Mouse.LEFT_BUTTON,
                    "right": Mouse.RIGHT_BUTTON,
                    "middle": Mouse.MIDDLE_BUTTON,
                }
                b = btn_map.get(button)
                if b is None:
                    return False
                self._mouse.release(b)
                return True

            else:
                print(f"[output:{self.name}] Unknown mouse action: {act}")
                return False

        except Exception as e:
            print(f"[output:{self.name}] Error in action '{act}':", e)
            return False

    def cleanup(self):
        if self._mouse is not None:
            try:
                self._mouse.release_all()
            except Exception:
                pass
