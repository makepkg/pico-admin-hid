import time
import displayio
import terminalio
from adafruit_display_text import label
import json


class WarningScreen:

    def __init__(self, disp):
        self._disp = disp
        self._group = displayio.Group()

        self._line1 = label.Label(terminalio.FONT, text="", x=0, y=5, color=0xFFFFFF)
        self._line2 = label.Label(terminalio.FONT, text="", x=0, y=21, color=0xFFFFFF)

        self._group.append(self._line1)
        self._group.append(self._line2)

        self._active = False
        self._prev_root = None
        self._blink_state = False
        self._next_blink = 0.0
        self._cancel_shown_until = 0.0
        self._percent = 0
        
        # Load settings from config.json
        try:
            with open("config.json") as f:
                _ina = json.load(f).get("inputs", {}).get("ina226", {})
            self.BLINK_INTERVAL = _ina.get("warning_blink_interval", 0.5)
            self._CANCELED_DISPLAY = _ina.get("warning_canceled_display_sec", 2.0)
        except Exception:
            self.BLINK_INTERVAL = 0.5
            self._CANCELED_DISPLAY = 2.0

    def show(self, percent):
        try:
            self._percent = percent
            if self._active:
                # Уже активен — только обновляем процент, root_group не трогаем
                return

            self._prev_root = self._disp.root_group
            self._disp.root_group = self._group

            self._line2.text = "  SHUTDOWN  ARMED  "
            self._cancel_shown_until = 0.0
            self._blink_state = False
            self._next_blink = time.monotonic()
            self._active = True
        except Exception:
            pass

    def show_canceled(self):
        try:
            self._line2.text = " SHUTDOWN CANCELED "
            self._cancel_shown_until = time.monotonic() + self._CANCELED_DISPLAY
        except Exception:
            pass

    def tick(self) -> bool:
        if not self._active:
            return False

        try:
            now = time.monotonic()

            # Таймер CANCELED — скрыть после 2 сек
            if self._cancel_shown_until > 0 and now >= self._cancel_shown_until:
                self._hide()
                return False

            # Мигание "!!" 
            if now >= self._next_blink:
                self._blink_state = not self._blink_state
                prefix = "!!" if self._blink_state else "  "
                self._line1.text = f"{prefix} LOW BATTERY {self._percent}% {prefix}"
                self._next_blink = now + self.BLINK_INTERVAL

            return True
        except Exception:
            return True

    def hide(self):
        """Публичный — для скролла энкодера."""
        try:
            self._hide()
        except Exception:
            pass

    def _hide(self):
        try:
            if self._prev_root is not None:
                self._disp.root_group = self._prev_root
            self._active = False
            self._prev_root = None
            self._cancel_shown_until = 0.0
        except Exception:
            pass

    @property
    def is_active(self):
        return self._active
