"""output_gpio.py — GPIO output handler для оптопар, реле, индикаторов."""

import time
import board
import digitalio
from output_base import OutputHandler


class GpioOutput(OutputHandler):
    """GPIO output handler для управления цифровыми пинами.
    
    Поддерживаемые actions:
    - gpio_pulse: короткий импульс 250ms (нажатие кнопки)
    - gpio_set: установить состояние HIGH/LOW
    - gpio_hold: HIGH на заданное время, потом LOW
    
    Config параметры:
    - pin: номер GPIO пина (обязательный)
    - active_high: true/false (default: true)
    - label: описание для логов (optional)
    - enabled: включен ли output (default: true)
    """
    
    def __init__(self, name, config):
        super().__init__(name, config)
        
        self._pin_obj = None
        
        # Проверка наличия pin в конфиге
        pin_num = config.get("pin")
        if pin_num is None:
            print(f"[output:{name}] WARNING: pin not specified — GPIO disabled")
            self._enabled = False
            return
        
        try:
            # Инициализация GPIO как OUTPUT
            pin_name = f"GP{pin_num}"
            self._pin_obj = digitalio.DigitalInOut(getattr(board, pin_name))
            self._pin_obj.direction = digitalio.Direction.OUTPUT
            
            self._active_high = config.get("active_high", True)
            self._label = config.get("label", f"GPIO{pin_num}")
            
            self._drive(False)  # Начальное состояние: inactive (учитывает active_high)
            
            print(f"[output:{name}] GPIO ready: {pin_name}, active_high={self._active_high}, label='{self._label}'")
        
        except Exception as e:
            print(f"[output:{name}] ERROR initializing GPIO pin {pin_num}:", e)
            self._enabled = False
    
    def _drive(self, active):
        """Переводит логическое состояние active/inactive в физический уровень пина
        с учётом active_high. active=True -> "включено" (кнопка нажата / реле сработало).
        """
        self._pin_obj.value = active if self._active_high else not active
    
    def execute(self, action):
        """Выполняет GPIO actions: gpio_pulse, gpio_set, gpio_hold.
        
        Args:
            action: dict шага сценария, например:
                {"action": "gpio_pulse"}
                {"action": "gpio_set", "value": "high"}
                {"action": "gpio_hold", "duration_ms": 1000}
        
        Returns:
            bool: True при успехе, False при ошибке
        """
        if not self.enabled or self._pin_obj is None:
            return False
        
        act = action.get("action")
        
        try:
            if act == "gpio_pulse":
                # Короткий импульс 250ms (нажатие кнопки питания)
                duration_ms = 250  # хардкод
                print(f"[output:{self.name}] Pulsing {self._label} for {duration_ms}ms...")
                self._drive(True)
                time.sleep(duration_ms / 1000.0)
                self._drive(False)
                print(f"[output:{self.name}] Pulse complete")
                return True
            
            # NOTE: gpio_set всегда работает с буквальным электрическим уровнем пина и
            # сознательно НЕ учитывает active_high — это low-level/raw control. Если нужна
            # активация с учётом active_high (как "нажатие кнопки"), используй gpio_pulse/gpio_hold.
            elif act == "gpio_set":
                # Установить состояние HIGH/LOW
                val_str = action.get("value", "low").lower()
                val = (val_str == "high")
                self._pin_obj.value = val
                print(f"[output:{self.name}] Set {self._label} to {val_str.upper()}")
                return True
            
            elif act == "gpio_hold":
                # HIGH на заданное время, потом LOW
                duration_ms = action.get("duration_ms", 500)
                print(f"[output:{self.name}] Holding {self._label} for {duration_ms}ms...")
                self._drive(True)
                time.sleep(duration_ms / 1000.0)
                self._drive(False)
                print(f"[output:{self.name}] Hold complete")
                return True
            
            else:
                print(f"[output:{self.name}] Unknown GPIO action: {act}")
                return False
        
        except Exception as e:
            print(f"[output:{self.name}] Error in action '{act}':", e)
            # Безопасность: сбросить в inactive при ошибке
            try:
                self._drive(False)
            except:
                pass
            return False
    
    def cleanup(self):
        """Сброс в inactive состояние (с учётом active_high) при завершении."""
        if self._pin_obj:
            try:
                self._drive(False)
                print(f"[output:{self.name}] cleanup: reset {self._label} to inactive")
            except Exception as e:
                print(f"[output:{self.name}] cleanup error:", e)
