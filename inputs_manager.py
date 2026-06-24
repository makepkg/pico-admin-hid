"""
inputs_manager.py — унифицированный менеджер входных датчиков.

Читает из config['inputs'] список датчиков и создаёт объекты по типу.
Для добавления датчика — только config.json, код не трогать.
"""

import board
import digitalio
import time
import trigger_bus
import config as cfg
from ina226_monitor import INA226Monitor


_BTN_DEBOUNCE_MS   = 50
_BTN_DOUBLE_WINDOW = 0.400   # секунды между нажатиями для double-click


class HallSensorInput:
    """Hall sensor input handler"""
    
    def __init__(self, input_id, config_dict, debounce_ms, armed):
        self.input_id = input_id
        self.config = config_dict
        self.debounce_ms = debounce_ms
        self.armed = armed
        
        pin_num = config_dict.get("pin")
        self.active_low = config_dict.get("active_low", True)
        
        if pin_num is None:
            raise ValueError(f"Hall sensor {input_id}: pin not specified")
        
        self.sensor = self._make_input_pullup(pin_num)
        raw = self._read_hall()
        
        self.stable = raw
        self.last_raw = raw
        self.debounce_t = time.monotonic()
        
        print(f"[inputs] Hall {input_id} на GP{pin_num}, active_low:{self.active_low} — начальное: {'PRESENT' if raw else 'ABSENT'}")
    
    def update(self, now):
        """Process hall sensor state"""
        current = self._read_hall()
        
        if current != self.last_raw:
            self.debounce_t = now
            self.last_raw = current
        
        if (now - self.debounce_t) * 1000 < self.debounce_ms:
            return  # ещё в окне дребезга
        
        if current == self.stable:
            return  # состояние не изменилось
        
        self.stable = current
        state_str = "PRESENT" if current else "ABSENT"
        print(f"[inputs] {self.input_id} → {state_str}")
        
        if not self.armed:
            return
        
        if not trigger_bus.is_busy():
            if not current:   # магнит потерян — аварийный триггер
                trigger_bus.fire(self.input_id, trigger_bus.PRIORITY_HIGH)
    
    def _read_hall(self):
        raw = self.sensor.value
        return (not raw) if self.active_low else raw
    
    def _make_input_pullup(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        return pin


class PowerMonitorInput:
    """INA226 power monitor input handler"""
    
    def __init__(self, input_id, config_dict, i2c):
        self.input_id = input_id
        self.config = config_dict
        
        self.monitor = INA226Monitor(i2c, config_dict)
        self.available = self.monitor.available
        
        self.cooldown_until = 0
        self.triggered = False
        self.warning_active = False
        self.trigger_canceled = False
        self.warning_dismissed = False  # Флаг для snooze/dismiss
        
        self.last_read = 0
        self.read_interval = config_dict.get("read_interval_sec", 5.0)
        self.last_metrics = None
        
        if self.available:
            print(f"[inputs] Power monitor {input_id} initialized (I2C 0x{config_dict.get('i2c_address', 64):02X})")
        else:
            print(f"[inputs] Power monitor {input_id} — sensor not found or disabled")
    
    def update(self, now):
        """Process power monitor state"""
        if not self.available:
            return
        
        if not self.config.get("enabled", False):
            return
        
        warning_enabled = self.config.get("warning_enabled", True)
        
        if now < self.cooldown_until:
            return
        
        # Throttle: не читаем I2C чаще чем раз в N сек
        if now - self.last_read < self.read_interval:
            metrics = self.last_metrics
        else:
            metrics = self.monitor.get_metrics()
            self.last_metrics = metrics
            self.last_read = now
        
        if metrics is None:
            return
        
        mode = self.config.get("trigger_mode", "percent")
        offset = self.config.get("warning_offset_percent", 5)
        fired = False
        
        if mode == "percent":
            threshold = self.config.get("threshold_percent", 15)
            warn_threshold = threshold + offset
            fired = metrics["percent"] <= threshold
            
            self.warning_active = (
                warning_enabled and
                metrics["percent"] <= warn_threshold and
                not self.trigger_canceled and
                not self.triggered and
                not self.warning_dismissed  # Dismiss снимается только при восстановлении батареи
            )
            
            # Сброс отмены и dismiss если зарядились выше warning зоны
            if metrics["percent"] > warn_threshold:
                self.trigger_canceled = False
                self.triggered = False
                self.warning_active = False
                self.warning_dismissed = False  # Сброс dismiss при восстановлении
        
        elif mode == "voltage":
            threshold = self.config.get("threshold_voltage", 16.5)
            warn_threshold = threshold + self.config.get("warning_offset_percent", 0.5)
            fired = metrics["voltage"] <= threshold
            
            self.warning_active = (
                warning_enabled and
                metrics["voltage"] <= warn_threshold and
                not self.trigger_canceled and
                not self.triggered and
                not self.warning_dismissed  # Dismiss снимается только при восстановлении батареи
            )
            
            # Сброс отмены и dismiss если зарядились выше warning зоны
            if metrics["voltage"] > warn_threshold:
                self.trigger_canceled = False
                self.triggered = False
                self.warning_active = False
                self.warning_dismissed = False  # Сброс dismiss при восстановлении
        
        if fired and not self.triggered:
            self.triggered = True
            self.warning_active = False
            self.cooldown_until = now + self.config.get("cooldown_sec", 300)
            trigger_bus.fire(self.input_id, trigger_bus.PRIORITY_HIGH)
    
    def cancel_trigger(self):
        """Вызывается при нажатии центра энкодера — отменяет shutdown триггер."""
        self.trigger_canceled = True
        self.triggered = True
        self.warning_active = False
        cancel_cd = self.config.get("cancel_cooldown_sec", 3600)
        self.cooldown_until = time.monotonic() + cancel_cd
    
    def dismiss_warning(self):
        """Вызывается при прокруте энкодера — убирает warning без cooldown."""
        self.warning_dismissed = True
        self.warning_active = False
    
    def get_metrics(self):
        """Публичный доступ к метрикам для splash screen"""
        if self.available:
            return self.monitor.get_metrics()
        return None


class InputsManager:
    """Unified manager for all input sensors (Hall, INA226, etc.)"""
    
    def __init__(self, i2c=None):
        conf = cfg.get_config()
        dev = conf.get("device", {})
        hw = conf.get("hardware", {})
        
        self._armed = dev.get("armed", False)
        self._hall_debounce_ms = dev.get("debounce_ms", 300)
        
        # ── LED ───────────────────────────────────────────────────────────
        led_pin = hw.get("led_pin", 25)
        self._led = self._make_output(led_pin)
        self._led.value = self._armed
        
        # ── Unified inputs list ───────────────────────────────────────────
        self._inputs = []
        inputs_config = conf.get("inputs", {})
        
        for input_id, input_cfg in inputs_config.items():
            input_type = input_cfg.get("type")
            
            try:
                if input_type == "hall":
                    handler = HallSensorInput(input_id, input_cfg, self._hall_debounce_ms, self._armed)
                    self._inputs.append(handler)
                
                elif input_type == "power_monitor":
                    handler = PowerMonitorInput(input_id, input_cfg, i2c)
                    self._inputs.append(handler)
                
                else:
                    print(f"[inputs] Unknown input type '{input_type}' for '{input_id}'")
            
            except Exception as e:
                print(f"[inputs] Failed to init input '{input_id}': {e}")
        
        # ── Кнопка ────────────────────────────────────────────────────────
        btn_pin = hw.get("button_pin", 24)
        self._btn = self._make_input_pullup(btn_pin)
        raw_btn = not self._btn.value
        self._btn_stable = raw_btn
        self._btn_last_raw = raw_btn
        self._btn_deb_t = time.monotonic()
        self._btn_count = 0
        self._btn_first_t = 0.0
        
        print(f"[inputs] Button на GP{btn_pin}")
        print(f"[inputs] Manager OK, armed: {self._armed}, inputs: {len(self._inputs)}")
    
    # ── Public API ────────────────────────────────────────────────────────
    
    @property
    def ina_warning_active(self):
        """Backward compatibility: check if any power monitor has warning active"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput) and inp.warning_active:
                return True
        return False
    
    @property
    def ina_warning_percent(self):
        """Backward compatibility: get warning percent from first active power monitor"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput) and inp.warning_active:
                if inp.last_metrics:
                    return inp.last_metrics.get("percent")
        return None
    
    def cancel_ina_trigger(self):
        """Backward compatibility: cancel trigger on all power monitors"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput):
                inp.cancel_trigger()
    
    def dismiss_ina_warning(self):
        """Dismiss INA226 warning without cooldown (for scroll dismiss)"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput):
                inp.dismiss_warning()
    
    def get_power_monitor(self, input_id="ina226"):
        """Get power monitor by ID for direct access (e.g., splash screen)"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput) and inp.input_id == input_id:
                return inp
        return None
    
    def startup_blink(self, count=3):
        """Мигает LED при старте для индикации готовности."""
        for _ in range(count):
            self._led.value = True
            time.sleep(0.4)
            self._led.value = False
            time.sleep(0.4)
        self._led.value = self._armed
    
    def update(self):
        """Вызывать каждую итерацию main loop."""
        now = time.monotonic()
        
        # Update all inputs
        for inp in self._inputs:
            inp.update(now)
        
        # Process button
        self._process_button(now)
    
    # ── Button ────────────────────────────────────────────────────────────
    
    def _process_button(self, now):
        current = not self._btn.value   # Pull.UP: нажато = False → инвертируем
        
        if current != self._btn_last_raw:
            self._btn_deb_t = now
            self._btn_last_raw = current
        
        if (now - self._btn_deb_t) * 1000 < _BTN_DEBOUNCE_MS:
            return  # дребезг
        
        if current != self._btn_stable:
            self._btn_stable = current
            if current:   # передний фронт (нажатие)
                if self._btn_count == 0:
                    self._btn_count = 1
                    self._btn_first_t = now
                elif self._btn_count == 1:
                    if now - self._btn_first_t <= _BTN_DOUBLE_WINDOW:
                        # ── двойное нажатие ──────────────────────────────
                        print("[inputs] btn_double")
                        if self._armed:
                            trigger_bus.fire("btn_double", trigger_bus.PRIORITY_NORMAL)
                        self._btn_count = 0
                    else:
                        # второе нажатие слишком поздно — считаем новым первым
                        self._btn_count = 1
                        self._btn_first_t = now
        
        # Таймаут одиночного нажатия
        if self._btn_count == 1 and (now - self._btn_first_t) > _BTN_DOUBLE_WINDOW:
            print("[inputs] btn_single (не используется)")
            self._btn_count = 0
    
    # ── Helpers ───────────────────────────────────────────────────────────
    
    def _make_output(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.OUTPUT
        return pin
    
    def _make_input_pullup(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        return pin


# Backward compatibility alias
PassiveHandler = InputsManager
