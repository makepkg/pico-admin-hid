"""
display.py — управление OLED-дисплеем SSD1306 128×32.

CircuitPython 9+/10+: displayio.I2CDisplay переехал в i2cdisplaybus.I2CDisplayBus

Библиотеки (положить в lib/):
  adafruit_displayio_ssd1306.mpy
  adafruit_display_text/ (папка)
terminalio — встроен в CircuitPython 7+.

Компоновка экрана 128×32 (anchor_point = (0.5, 0.5) — центр по горизонтали и вертикали):
  y= 4  — верхняя строка  (статус / заголовок)
  y=16  — центральная     (имя текущего пункта меню)
  y=27  — нижняя строка   (следующее действие / подсказка)
"""

import board
import busio
import displayio
import terminalio
import time
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import i2cdisplaybus   # CircuitPython 9+/10+
import config as cfg

_W    = 128
_H    = 32
_ADDR = 0x3C


class DisplayManager:

    def __init__(self):
        hw      = cfg.get_config().get("hardware", {})
        sda_num = hw.get("display_sda", 4)
        scl_num = hw.get("display_scl", 5)

        sda = getattr(board, "GP" + str(sda_num))
        scl = getattr(board, "GP" + str(scl_num))

        displayio.release_displays()
        i2c = busio.I2C(scl=scl, sda=sda, frequency=400_000)
        self.i2c = i2c

        # ИСПРАВЛЕНО: i2cdisplaybus.I2CDisplayBus вместо displayio.I2CDisplay
        bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=_ADDR)
        self._disp = adafruit_displayio_ssd1306.SSD1306(bus, width=_W, height=_H)

        _cx = _W // 2   # 64 — горизонтальный центр экрана

        # ── Основная группа: 3 переиспользуемых лейбла ──────────────────
        self._main_group = displayio.Group()
        self._lbl_top    = self._make_label(" ", _cx, 4)
        self._lbl_center = self._make_label(" ", _cx, 16)
        self._lbl_bottom = self._make_label(" ", _cx, 27)
        self._main_group.append(self._lbl_top)
        self._main_group.append(self._lbl_center)
        self._main_group.append(self._lbl_bottom)
        self._disp.root_group = self._main_group

        # ── Группа анимации: два лейбла, пересоздаются не в цикле ───────
        self._anim_group   = displayio.Group()
        self._lbl_anim_old = self._make_label(" ", _cx,      16)
        self._lbl_anim_new = self._make_label(" ", _cx + _W, 16)
        self._anim_group.append(self._lbl_anim_old)
        self._anim_group.append(self._lbl_anim_new)

        # ── Группа скринсейвера ─────────────────────────────────────────
        self._screensaver_bitmap = displayio.Bitmap(_W, _H, 2)
        self._screensaver_palette = displayio.Palette(2)
        self._screensaver_palette[0] = 0x000000
        self._screensaver_palette[1] = 0xFFFFFF
        self._screensaver_tile_grid = displayio.TileGrid(
            self._screensaver_bitmap,
            pixel_shader=self._screensaver_palette
        )
        self._screensaver_group = displayio.Group()
        self._screensaver_group.append(self._screensaver_tile_grid)
        self._screensaver_manager = None

        print("[display] init OK  SDA=GP", sda_num, " SCL=GP", scl_num)

    # ── Public: основные экраны ────────────────────────────────────────────

    def draw_menu(self, item_label, action_name=""):
        _cx = _W // 2
        self._lbl_top.anchored_position    = (_cx, 4)
        self._lbl_center.anchored_position = (_cx, 16)
        self._lbl_bottom.anchored_position = (_cx, 27)

        self._lbl_top.text    = "< MENU >"
        self._lbl_center.text = self._fit(item_label, 21)
        self._lbl_bottom.text = ("-> " + action_name) if action_name else " "

        self._disp.root_group = self._main_group

    def show_executing(self, item_label, action_name=""):
        _cx = _W // 2
        self._lbl_top.anchored_position    = (_cx, 4)
        self._lbl_center.anchored_position = (_cx, 16)
        self._lbl_bottom.anchored_position = (_cx, 27)

        self._lbl_top.text    = "Running..."
        self._lbl_center.text = self._fit(item_label, 21)
        self._lbl_bottom.text = self._fit(action_name, 21) if action_name else " "

        self._disp.root_group = self._main_group

    def show_status(self, line1="", line2="", line3=""):
        _cx = _W // 2
        self._lbl_top.anchored_position    = (_cx, 4)
        self._lbl_center.anchored_position = (_cx, 16)
        self._lbl_bottom.anchored_position = (_cx, 27)

        self._lbl_top.text    = self._fit(line1, 21) if line1 else " "
        self._lbl_center.text = self._fit(line2, 21) if line2 else " "
        self._lbl_bottom.text = self._fit(line3, 21) if line3 else " "

        self._disp.root_group = self._main_group

    def show_boot(self):
        self.show_status(line2="Booting...")

    # ── Public: анимация перехода ──────────────────────────────────────────

    def animate_swipe(self, old_label, new_label, direction="right"):
        self._lbl_anim_old.text = self._fit(old_label, 21)
        self._lbl_anim_new.text = self._fit(new_label, 21)

        frames  = 6
        step_px = _W // frames   # 21 px за кадр
        cx      = _W // 2        # 64
        cy      = 16

        self._disp.root_group = self._anim_group

        for i in range(frames + 1):
            offset = i * step_px
            if direction == "right":
                self._lbl_anim_old.anchored_position = (cx - offset,      cy)
                self._lbl_anim_new.anchored_position = (cx + _W - offset, cy)
            else:
                self._lbl_anim_old.anchored_position = (cx + offset,      cy)
                self._lbl_anim_new.anchored_position = (cx - _W + offset, cy)
            time.sleep(0.022)

        self._disp.root_group = self._main_group

    # ── Public: скринсейвер и сон ──────────────────────────────────────────

    def start_screensaver(self, name):
        import screensaver
        self._screensaver_manager = screensaver.ScreensaverManager(self._screensaver_bitmap, name)
        # Отключаем автоматическое обновление экрана, чтобы избежать мерцания в процессе отрисовки
        try:
            self._disp.auto_refresh = False
        except AttributeError:
            pass
        self._disp.root_group = self._screensaver_group

    def update_screensaver(self):
        if self._screensaver_manager:
            self._screensaver_manager.draw_frame()
            # Принудительно обновляем экран только ПОСЛЕ полной отрисовки кадра
            try:
                self._disp.refresh()
            except AttributeError:
                pass

    def stop_screensaver(self):
        self._screensaver_manager = None
        # Возвращаем автоматическое обновление для нормальной работы меню
        try:
            self._disp.auto_refresh = True
        except AttributeError:
            pass
        self._disp.root_group = self._main_group

    def sleep(self):
        try:
            self._disp.sleep()
        except AttributeError:
            self._disp.root_group = displayio.Group()

    def wake(self):
        try:
            self._disp.wake()
        except AttributeError:
            pass
        self._disp.root_group = self._main_group

    # ── Internal ──────────────────────────────────────────────────────────

    def _make_label(self, text, x, y):
        return label.Label(
            terminalio.FONT,
            text=text,
            color=0xFFFFFF,
            anchor_point=(0.5, 0.5),
            anchored_position=(x, y),
        )

    @staticmethod
    def _fit(text, max_chars):
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 1] + "~"
