"""
encoder.py — обработчик энкодера KY-040.

Пины берутся из config['hardware'].
Генерирует события через callback:
  EV_ROTATE_LEFT  — поворот против часовой (предыдущий пункт)
  EV_ROTATE_RIGHT — поворот по часовой (следующий пункт)
  EV_PRESS        — короткое нажатие (исполнить команду)
  EV_LONG_PRESS   — удержание >1с (зарезервировано)

Замечание по KY-040:
  divisor=4 → одно событие на один физический щелчок.
  Если меню листается по два пункта — поменяй на divisor=2.
  Если направление вращения инвертировано — поменяй местами CLK и DT в конфиге.
"""

import board
import digitalio
import rotaryio
import time
import config as cfg

EV_ROTATE_LEFT  = "rotate_left"
EV_ROTATE_RIGHT = "rotate_right"
EV_PRESS        = "press"
EV_LONG_PRESS   = "long_press"

_SW_DEBOUNCE_MS = 50
_LONG_PRESS_MS  = 1000


class EncoderHandler:

    def __init__(self):
        hw = cfg.get_config().get("hardware", {})

        clk_num = hw.get("encoder_clk", 6)
        dt_num  = hw.get("encoder_dt",  7)
        sw_num  = hw.get("encoder_sw",  8)

        clk = getattr(board, "GP" + str(clk_num))
        dt  = getattr(board, "GP" + str(dt_num))
        sw  = getattr(board, "GP" + str(sw_num))

        # rotaryio обрабатывает дребезг CLK/DT аппаратно на RP2040
        self._enc      = rotaryio.IncrementalEncoder(clk, dt, divisor=4)
        self._last_pos = self._enc.position

        self._sw = digitalio.DigitalInOut(sw)
        self._sw.direction = digitalio.Direction.INPUT
        self._sw.pull      = digitalio.Pull.UP

        self._sw_last_raw  = not self._sw.value
        self._sw_stable    = False
        self._sw_deb_t     = time.monotonic()
        self._sw_press_t   = 0.0
        self._sw_held      = False

        self._callback = None

        print("[encoder] init OK  CLK=GP", clk_num,
              " DT=GP", dt_num, " SW=GP", sw_num)

    # ── Public ────────────────────────────────────────────────────────────

    def set_callback(self, cb):
        """
        cb(event: str) будет вызываться при каждом событии.
        Вызов синхронный — не делай в нём долгих операций.
        """
        self._callback = cb

    def update(self):
        """Вызывать каждую итерацию main loop."""
        self._process_rotation()
        self._process_button(time.monotonic())

    # ── Internal ──────────────────────────────────────────────────────────

    def _emit(self, event):
        if self._callback:
            self._callback(event)

    def _process_rotation(self):
        pos = self._enc.position
        if pos == self._last_pos:
            return

        delta          = pos - self._last_pos
        self._last_pos = pos

        steps = abs(delta)
        if delta > 0:
            for _ in range(steps):
                self._emit(EV_ROTATE_RIGHT)
        else:
            for _ in range(steps):
                self._emit(EV_ROTATE_LEFT)

    def _process_button(self, now):
        current = not self._sw.value   # Pull.UP инвертируем

        # Антидребезг
        if current != self._sw_last_raw:
            self._sw_deb_t    = now
            self._sw_last_raw = current

        if (now - self._sw_deb_t) * 1000 < _SW_DEBOUNCE_MS:
            return

        if current == self._sw_stable:
            return

        self._sw_stable = current

        if current:
            # Передний фронт — запоминаем момент нажатия
            self._sw_press_t = now
            self._sw_held    = True
        else:
            # Задний фронт — определяем тип по длительности
            if self._sw_held:
                held_ms       = (now - self._sw_press_t) * 1000
                self._sw_held = False
                if held_ms >= _LONG_PRESS_MS:
                    self._emit(EV_LONG_PRESS)
                else:
                    self._emit(EV_PRESS)
