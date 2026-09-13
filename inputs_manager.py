"""
inputs_manager.py — унифицированный менеджер входных датчиков.

Читает из config['inputs'] список датчиков и создаёт объекты по типу.
Для добавления датчика — только config.json, код не трогать.
"""

import board
import digitalio
import countio
import time
import trigger_bus
import config as cfg
from ina226_monitor import INA226Monitor


def _log_power_event(msg):
    try:
        import time
        with open("/power_monitor.log", "a") as f:
            f.write(f"[{time.monotonic():.1f}] {msg}\n")
    except:
        pass


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


class TrackballInput:
    """Трек-болл: 4 направленных пина, гибридная схема опроса.
    
    UP/RIGHT — через countio.Counter (аппаратный счётчик, PWM Channel B,
    нечётные GPIO). DOWN/LEFT — через digitalio polling в update() (RP2040
    countio требует PWM Channel B, недоступен на чётных GPIO — физическое
    ограничение чипа, не выбор реализации). Кнопка — digitalio с debounce.
    
    Работает НАПРЯМУЮ через trigger_bus.execute_output(), в обход
    fire()/cooldown/busy. Не проверяет device.armed (UI-устройство, как энкодер).
    """

    def __init__(self, input_id, config_dict):
        self.input_id = input_id
        self.config = config_dict

        self.output_name = config_dict.get("output", "mouse")
        self.sensitivity = config_dict.get("sensitivity", 1)
        self.debounce_ms = config_dict.get("debounce_ms", 15)
        self.triple_click_window_ms = config_dict.get("triple_click_window_ms", 1000)
        self.triple_click_count = config_dict.get("triple_click_count", 3)
        self.click_mode = config_dict.get("click_mode", "mouse")
        self.triple_click_mode = config_dict.get("triple_click_mode", "mouse")

        pin_up = config_dict.get("pin_up")
        pin_down = config_dict.get("pin_down")
        pin_left = config_dict.get("pin_left")
        pin_right = config_dict.get("pin_right")
        pin_button = config_dict.get("pin_button")

        missing = [n for n, v in [
            ("pin_up", pin_up), ("pin_down", pin_down),
            ("pin_left", pin_left), ("pin_right", pin_right),
            ("pin_button", pin_button),
        ] if v is None]
        if missing:
            raise ValueError(f"Trackball {input_id}: не указаны пины: {missing}")

        # UP/RIGHT — аппаратный countio.Counter (требует нечётный GPIO, PWM Channel B)
        self._c_up = countio.Counter(getattr(board, "GP" + str(pin_up)))
        self._c_right = countio.Counter(getattr(board, "GP" + str(pin_right)))

        # DOWN/LEFT — ручной polling через digitalio (чётные GPIO, PWM Channel A,
        # countio недоступен — физическое ограничение RP2040)
        self._pin_down = self._make_input_pullup(pin_down)
        self._pin_left = self._make_input_pullup(pin_left)
        self._last_raw_down = self._pin_down.value
        self._last_raw_left = self._pin_left.value

        self._btn = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_button)))
        self._btn.direction = digitalio.Direction.INPUT
        self._btn.pull = digitalio.Pull.UP

        self._last_raw_btn = False
        self._last_stable_btn = False
        self._btn_change_t = time.monotonic()

        self._click_count = 0
        self._first_click_t = 0.0

        self._btn_is_down = False

        print(f"[inputs] Trackball {input_id}: UP=GP{pin_up}(countio) "
              f"RIGHT=GP{pin_right}(countio) DOWN=GP{pin_down}(poll) "
              f"LEFT=GP{pin_left}(poll) BTN=GP{pin_button}")

    def update(self, now):
        up = self._c_up.count
        self._c_up.count = 0
        right = self._c_right.count
        self._c_right.count = 0

        # Ручной edge-detect для DOWN/LEFT: считаем переход HIGH→LOW
        # (кнопка/контакт трек-болла подтянута к 3V3, замыкание на GND = LOW)
        down = 0
        raw_down = self._pin_down.value
        if raw_down != self._last_raw_down:
            if self._last_raw_down and not raw_down:
                down = 1
            self._last_raw_down = raw_down

        left = 0
        raw_left = self._pin_left.value
        if raw_left != self._last_raw_left:
            if self._last_raw_left and not raw_left:
                left = 1
            self._last_raw_left = raw_left

        dy = (down - up) * self.sensitivity
        dx = (right - left) * self.sensitivity

        if dx != 0 or dy != 0:
            trigger_bus.execute_output(self.output_name, {"action": "move", "dx": dx, "dy": dy})

        self._process_button(now)

    def _process_button(self, now):
        raw_pressed = not self._btn.value

        if raw_pressed != self._last_raw_btn:
            self._last_raw_btn = raw_pressed
            self._btn_change_t = now

        if (now - self._btn_change_t) * 1000 < self.debounce_ms:
            return

        if raw_pressed == self._last_stable_btn:
            return

        self._last_stable_btn = raw_pressed

        if raw_pressed:
            if (now - self._first_click_t) * 1000 > self.triple_click_window_ms:
                self._click_count = 0
                self._first_click_t = now

            self._click_count += 1

            if self._click_count == self.triple_click_count:
                if self._btn_is_down:
                    trigger_bus.execute_output(self.output_name, {"action": "release", "button": "left"})
                    self._btn_is_down = False

                if self.triple_click_mode == "scenario":
                    trigger_bus.fire(f"{self.input_id}_triple_click", trigger_bus.PRIORITY_HIGH)
                else:
                    trigger_bus.execute_output(self.output_name, {"action": "click", "button": "right"})

                self._click_count = 0
            else:
                if self.click_mode == "scenario":
                    trigger_bus.fire(f"{self.input_id}_click", trigger_bus.PRIORITY_HIGH)
                else:
                    trigger_bus.execute_output(self.output_name, {"action": "press", "button": "left"})
                    self._btn_is_down = True
        else:
            if self._btn_is_down:
                trigger_bus.execute_output(self.output_name, {"action": "release", "button": "left"})
                self._btn_is_down = False

    def _make_input_pullup(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        return pin


class PowerMonitorInput:
    """INA226 power monitor input handler"""
    
    # State machine constants
    STATE_MONITORING = "monitoring"
    STATE_TRIGGERED = "triggered"
    STATE_SUSPENDED = "suspended"
    STATE_SUSPENDED_WAITING = "suspended_waiting"
    
    def __init__(self, input_id, config_dict, i2c):
        self.input_id = input_id
        self.config = config_dict
        
        self.monitor = INA226Monitor(i2c, config_dict)
        self.available = self.monitor.available
        
        self.trigger_attempts = 0
        self.trigger_attempt_deadline = 0
        self.max_attempts = config_dict.get("trigger_attempts", 3)
        self.attempt_interval = config_dict.get("trigger_attempt_interval_sec", 60)
        self.recovery_offset = config_dict.get("recovery_offset_percent", 5)
        
        self.warning_active = False
        self.warning_dismissed = False
        
        self.last_read = 0
        self.read_interval = config_dict.get("read_interval_sec", 5.0)
        self.last_metrics = None
        
        # Log rotation
        try:
            import os
            stat = os.stat("/power_monitor.log")
            if stat[6] > 20480:  # 20KB
                os.remove("/power_monitor.log")
        except:
            pass
        
        # Проверить начальное состояние — если % уже ниже threshold и USB нет, стартовать в SUSPENDED
        _initial_state = self.STATE_MONITORING
        if self.available:
            try:
                import supervisor
                _initial_metrics = self.monitor.get_metrics()
                _initial_usb = supervisor.runtime.usb_connected
                _threshold = config_dict.get("threshold_percent", 15)
                if _initial_metrics and _initial_metrics["percent"] <= _threshold and not _initial_usb:
                    _initial_state = self.STATE_SUSPENDED
            except:
                pass
        
        self.state = _initial_state
        _log_power_event(f"{self.input_id}: --- BOOT --- state={_initial_state}")
        
        if self.available:
            print(f"[inputs] Power monitor {input_id} initialized (I2C 0x{config_dict.get('i2c_address', 64):02X})")
        else:
            print(f"[inputs] Power monitor {input_id} — sensor not found or disabled")
    
    def update(self, now):
        """Process power monitor state"""
        if not self.available or not self.config.get("enabled", False):
            return
        
        import supervisor
        usb = supervisor.runtime.usb_connected
        
        # --- STATE: TRIGGERED ---
        if self.state == self.STATE_TRIGGERED:
            if not usb:
                # Сервер офнулся — подтверждено
                self.state = self.STATE_SUSPENDED
                self.warning_active = False
                _log_power_event(f"{self.input_id}: USB gone → SUSPENDED")
                print(f"[inputs] {self.input_id}: USB gone → SUSPENDED")
                return
            if now >= self.trigger_attempt_deadline:
                if self.trigger_attempts >= self.max_attempts:
                    # Исчерпали попытки — всё равно переходим в SUSPENDED
                    self.state = self.STATE_SUSPENDED
                    self.warning_active = False
                    _log_power_event(f"{self.input_id}: max attempts → SUSPENDED")
                    print(f"[inputs] {self.input_id}: max attempts → SUSPENDED")
                    return
                # Новая попытка
                self.trigger_attempts += 1
                self.trigger_attempt_deadline = now + self.attempt_interval
                _log_power_event(f"{self.input_id}: RETRY attempt={self.trigger_attempts}/{self.max_attempts}")
                print(f"[inputs] {self.input_id}: retry {self.trigger_attempts}/{self.max_attempts}")
                trigger_bus.fire(self.input_id, trigger_bus.PRIORITY_HIGH)
            return
        
        # --- STATE: SUSPENDED ---
        if self.state == self.STATE_SUSPENDED:
            if usb:
                # USB вернулся — сервер включён вручную
                self.state = self.STATE_SUSPENDED_WAITING
                _log_power_event(f"{self.input_id}: USB back → SUSPENDED_WAITING")
                print(f"[inputs] {self.input_id}: USB back → SUSPENDED_WAITING")
            return
        
        # --- STATE: SUSPENDED_WAITING ---
        if self.state == self.STATE_SUSPENDED_WAITING:
            # Читаем метрики, ждём восстановления заряда
            metrics = self._read_metrics(now)
            if metrics is None:
                return
            threshold = self._get_threshold(metrics)
            recovery = threshold + self.recovery_offset
            if metrics["percent"] > recovery:
                self.state = self.STATE_MONITORING
                self.trigger_attempts = 0
                self.warning_dismissed = False
                _log_power_event(f"{self.input_id}: recovered pct={metrics['percent']}% → MONITORING")
                print(f"[inputs] {self.input_id}: charge recovered → MONITORING")
            return
        
        # --- STATE: MONITORING ---
        metrics = self._read_metrics(now)
        if metrics is None:
            return
        
        threshold = self._get_threshold(metrics)
        warn_threshold = threshold + self.config.get("warning_offset_percent", 5)
        warning_enabled = self.config.get("warning_enabled", True)
        
        # Warning - log only on state change
        _prev_warning = self.warning_active
        self.warning_active = (
            warning_enabled and
            metrics["percent"] <= warn_threshold and
            not self.warning_dismissed
        )
        if self.warning_active != _prev_warning:
            _log_power_event(f"{self.input_id}: WARNING={'ON' if self.warning_active else 'OFF'} pct={metrics['percent']}%")
        
        # Trigger — только если USB подключён
        if metrics["percent"] <= threshold and usb:
            self.state = self.STATE_TRIGGERED
            self.trigger_attempts = 1
            self.trigger_attempt_deadline = now + self.attempt_interval
            self.warning_active = False
            _log_power_event(f"{self.input_id}: TRIGGER fired attempt=1/{self.max_attempts} usb={usb} pct={metrics['percent']}%")
            print(f"[inputs] {self.input_id}: threshold reached → TRIGGERED, attempt 1/{self.max_attempts}")
            trigger_bus.fire(self.input_id, trigger_bus.PRIORITY_HIGH)
    
    def cancel_trigger(self):
        """Пользователь отменил shutdown через энкодер."""
        if self.state == self.STATE_TRIGGERED:
            self.state = self.STATE_SUSPENDED
            self.warning_active = False
            _log_power_event(f"{self.input_id}: canceled by user → SUSPENDED")
            print(f"[inputs] {self.input_id}: trigger canceled by user → SUSPENDED")
    
    def dismiss_warning(self):
        """Вызывается при прокруте энкодера — убирает warning без cooldown."""
        self.warning_dismissed = True
        self.warning_active = False
    
    def get_metrics(self):
        """Публичный доступ к метрикам для splash screen"""
        if self.available:
            return self.monitor.get_metrics()
        return None
    
    @property
    def blocks_auto_boot(self):
        """Проверка блокировки авто-старта (батарея разряжена и в SUSPENDED)"""
        return self.state == self.STATE_SUSPENDED
    
    def _read_metrics(self, now):
        """Throttled metrics reading"""
        if now - self.last_read >= self.read_interval:
            self.last_metrics = self.monitor.get_metrics()
            self.last_read = now
        return self.last_metrics
    
    def _get_threshold(self, metrics):
        """Get current threshold based on trigger mode"""
        mode = self.config.get("trigger_mode", "percent")
        if mode == "voltage":
            return self.config.get("threshold_voltage", 16.5)
        return self.config.get("threshold_percent", 15)


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

            if not input_cfg.get("enabled", True):
                print(f"[inputs] '{input_id}' disabled in config — skipping")
                continue

            try:
                if input_type == "hall":
                    handler = HallSensorInput(input_id, input_cfg, self._hall_debounce_ms, self._armed)
                    self._inputs.append(handler)
                
                elif input_type == "power_monitor":
                    handler = PowerMonitorInput(input_id, input_cfg, i2c)
                    self._inputs.append(handler)
                
                elif input_type == "trackball":
                    handler = TrackballInput(input_id, input_cfg)
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
    
    @property
    def auto_boot_blocked(self):
        """Проверка блокировки авто-старта любым power monitor"""
        for inp in self._inputs:
            if isinstance(inp, PowerMonitorInput) and inp.blocks_auto_boot:
                return True
        return False
    
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
