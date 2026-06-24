"""output_hid.py — USB HID Keyboard output handler."""

import time
import supervisor
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from output_base import OutputHandler


class HidOutput(OutputHandler):
    """USB HID Keyboard output handler.
    
    Поддерживаемые actions:
    - key: нажатие комбинации клавиш (напр. ctrl+c)
    - type: набор текста
    - wait: пауза в миллисекундах
    - enter: нажатие Enter (с опциональным count)
    """
    
    def __init__(self, name, config):
        super().__init__(name, config)
        
        # Отложенная инициализация USB HID (lazy initialization)
        self._kbd = None
        self._layout = None
        self._key_map = self._build_key_map()
        self._init_attempted = False
        
        print(f"[output:{name}] USB HID handler created (will init on first use)")
    
    def execute(self, action):
        """Выполняет HID actions: key, type, wait, enter.
        
        Args:
            action: dict шага сценария, например:
                {"action": "key", "combo": "ctrl+c"}
                {"action": "type", "value": "text"}
                {"action": "wait", "ms": 500}
                {"action": "enter", "count": 2}
        
        Returns:
            bool: True при успехе, False при ошибке
        """
        if not self.enabled:
            print(f"[output:{self.name}] Disabled — skip")
            return False
        
        if not supervisor.runtime.usb_connected:
            print(f"[output:{self.name}] USB not connected — skip")
            return False
        
        # Ленивая инициализация USB HID при первом использовании
        if not self._kbd and not self._init_attempted:
            self._init_attempted = True
            try:
                self._kbd = Keyboard(usb_hid.devices)
                self._layout = KeyboardLayoutUS(self._kbd)
                print(f"[output:{self.name}] USB HID Keyboard initialized")
            except Exception as e:
                print(f"[output:{self.name}] Failed to init USB HID:", e)
                self._enabled = False
                return False
        
        # Если инициализация не удалась ранее
        if not self._kbd:
            return False
        
        act = action.get("action")
        
        try:
            if act == "key":
                keys = self._parse_combo(action.get("combo", ""))
                if keys:
                    self._kbd.press(*keys)
                    self._kbd.release_all()
                    print(f"[output:{self.name}] key: {action.get('combo')}")
                else:
                    print(f"[output:{self.name}] key: no valid keys in combo")
            
            elif act == "type":
                value = action.get("value", "")
                self._layout.write(value)
                print(f"[output:{self.name}] type: '{value}'")
            
            elif act == "wait":
                ms = action.get("ms", 0)
                time.sleep(ms / 1000.0)
                print(f"[output:{self.name}] wait: {ms}ms")
            
            elif act == "enter":
                count = max(1, min(action.get("count", 1), 10))
                for _ in range(count):
                    self._kbd.press(Keycode.ENTER)
                    self._kbd.release_all()
                    time.sleep(0.05)
                print(f"[output:{self.name}] enter: {count}x")
            
            else:
                print(f"[output:{self.name}] Unknown action: {act}")
                return False
            
            return True
        
        except Exception as e:
            print(f"[output:{self.name}] Error in action '{act}':", e)
            try:
                if self._kbd:
                    self._kbd.release_all()
            except:
                pass
            return False
    
    def _build_key_map(self):
        """Строит маппинг клавиш (из trigger_bus.py).
        
        Returns:
            dict: маппинг строка -> Keycode
        """
        km = {
            "ctrl":      Keycode.CONTROL,
            "alt":       Keycode.ALT,
            "shift":     Keycode.SHIFT,
            "super":     Keycode.GUI,
            "win":       Keycode.GUI,
            "enter":     Keycode.ENTER,
            "escape":    Keycode.ESCAPE,
            "esc":       Keycode.ESCAPE,
            "space":     Keycode.SPACEBAR,
            "tab":       Keycode.TAB,
            "backspace": Keycode.BACKSPACE,
            "delete":    Keycode.DELETE,
            "up":        Keycode.UP_ARROW,
            "down":      Keycode.DOWN_ARROW,
            "left":      Keycode.LEFT_ARROW,
            "right":     Keycode.RIGHT_ARROW,
        }
        
        # F1-F12
        for i in range(12):
            km["f" + str(i + 1)] = getattr(Keycode, "F" + str(i + 1))
        
        # a-z
        for i in range(26):
            c = chr(ord('a') + i)
            km[c] = getattr(Keycode, c.upper())
        
        # 0-9
        for digit, name in {
            "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
            "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE"
        }.items():
            km[digit] = getattr(Keycode, name)
        
        return km
    
    def _parse_combo(self, combo_str):
        """Парсит combo строку типа 'ctrl+c' (из trigger_bus.py).
        
        Args:
            combo_str: строка комбинации клавиш, разделенных "+"
        
        Returns:
            list: список Keycode объектов
        """
        keys = []
        for part in combo_str.lower().split("+"):
            part = part.strip()
            kc = self._key_map.get(part)
            if kc:
                keys.append(kc)
            else:
                print(f"[output:{self.name}] неизвестная клавиша:", part)
        return keys
    
    def cleanup(self):
        """Освобождает все зажатые клавиши."""
        try:
            if self._kbd:
                self._kbd.release_all()
                print(f"[output:{self.name}] cleanup: released all keys")
        except Exception as e:
            print(f"[output:{self.name}] cleanup error:", e)
