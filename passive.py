"""
passive.py — мониторинг пассивных датчиков.

Читает из config['hardware'] список датчиков Холла и пин кнопки.
Для добавления датчика — только config.json, код не трогать.
"""

import board
import digitalio
import time
import trigger_bus
import config as cfg


_BTN_DEBOUNCE_MS   = 50
_BTN_DOUBLE_WINDOW = 0.400   # секунды между нажатиями для double-click


class PassiveHandler:

    def __init__(self):
        conf = cfg.get_config()
        dev  = conf.get("device", {})
        hw   = conf.get("hardware", {})

        self._armed           = dev.get("armed", False)
        self._hall_debounce_ms = dev.get("debounce_ms", 300)
        # active_low теперь per-sensor (берётся из каждого элемента hall_sensors)

        # ── LED ───────────────────────────────────────────────────────────
        led_pin    = hw.get("led_pin", 25)
        self._led  = self._make_output(led_pin)
        self._led.value = self._armed

        # ── Hall-датчики (из конфига, масштабируется) ─────────────────────
        self._halls = []
        for sensor_conf in hw.get("hall_sensors", []):
            pin_num   = sensor_conf.get("pin")
            sensor_id = sensor_conf.get("id", "hall_unknown")
            if pin_num is None:
                print("[passive] WARNING: пин не задан для", sensor_id)
                continue
            active_low = sensor_conf.get("active_low", True)
            sensor     = self._make_input_pullup(pin_num)
            raw        = self._read_hall(sensor, active_low)
            self._halls.append({
                "id":         sensor_id,
                "sensor":     sensor,
                "active_low": active_low,
                "stable":     raw,
                "last_raw":   raw,
                "debounce_t": time.monotonic(),
            })
            print("[passive] Hall", sensor_id, "на GP", pin_num,
                  "active_low:", active_low, "— начальное:", "PRESENT" if raw else "ABSENT")

        # ── Кнопка ────────────────────────────────────────────────────────
        btn_pin            = hw.get("button_pin", 24)
        self._btn          = self._make_input_pullup(btn_pin)
        raw_btn            = not self._btn.value
        self._btn_stable   = raw_btn
        self._btn_last_raw = raw_btn
        self._btn_deb_t    = time.monotonic()
        self._btn_count    = 0
        self._btn_first_t  = 0.0

        print("[passive] Button на GP", btn_pin)
        print("[passive] init OK, armed:", self._armed)

    # ── Public ────────────────────────────────────────────────────────────

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
        self._process_halls(now)
        self._process_button(now)

    # ── Hall ──────────────────────────────────────────────────────────────

    def _process_halls(self, now):
        for h in self._halls:
            current = self._read_hall(h["sensor"], h["active_low"])

            if current != h["last_raw"]:
                h["debounce_t"] = now
                h["last_raw"]   = current

            if (now - h["debounce_t"]) * 1000 < self._hall_debounce_ms:
                continue  # ещё в окне дребезга

            if current == h["stable"]:
                continue  # состояние не изменилось

            h["stable"] = current
            state_str   = "PRESENT" if current else "ABSENT"
            print("[passive]", h["id"], "→", state_str)

            if not self._armed:
                continue

            if not trigger_bus.is_busy():
                if not current:   # магнит потерян — аварийный триггер
                    trigger_bus.fire(h["id"], trigger_bus.PRIORITY_HIGH)
                # hall_restored: раскомментировать если нужен отдельный триггер
                # else:
                #     trigger_bus.fire(h["id"] + "_restored", trigger_bus.PRIORITY_NORMAL)

    def _read_hall(self, sensor, active_low=True):
        raw = sensor.value
        return (not raw) if active_low else raw

    # ── Button ────────────────────────────────────────────────────────────

    def _process_button(self, now):
        current = not self._btn.value   # Pull.UP: нажато = False → инвертируем

        if current != self._btn_last_raw:
            self._btn_deb_t    = now
            self._btn_last_raw = current

        if (now - self._btn_deb_t) * 1000 < _BTN_DEBOUNCE_MS:
            return  # дребезг

        if current != self._btn_stable:
            self._btn_stable = current
            if current:   # передний фронт (нажатие)
                if self._btn_count == 0:
                    self._btn_count   = 1
                    self._btn_first_t = now
                elif self._btn_count == 1:
                    if now - self._btn_first_t <= _BTN_DOUBLE_WINDOW:
                        # ── двойное нажатие ──────────────────────────────
                        print("[passive] btn_double")
                        if self._armed:
                            trigger_bus.fire("btn_double", trigger_bus.PRIORITY_NORMAL)
                        self._btn_count = 0
                    else:
                        # второе нажатие слишком поздно — считаем новым первым
                        self._btn_count   = 1
                        self._btn_first_t = now

        # Таймаут одиночного нажатия
        if self._btn_count == 1 and (now - self._btn_first_t) > _BTN_DOUBLE_WINDOW:
            print("[passive] btn_single (не используется)")
            # trigger_bus.fire("btn_single", trigger_bus.PRIORITY_NORMAL)
            self._btn_count = 0

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make_output(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.OUTPUT
        return pin

    def _make_input_pullup(self, pin_num):
        pin = digitalio.DigitalInOut(getattr(board, "GP" + str(pin_num)))
        pin.direction = digitalio.Direction.INPUT
        pin.pull      = digitalio.Pull.UP
        return pin
