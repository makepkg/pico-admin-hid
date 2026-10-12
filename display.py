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
  y=24  — нижняя строка   (следующее действие / подсказка)
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

try:
    import bitmaptools
except ImportError:
    bitmaptools = None

_W    = 128
_H    = 32
_ADDR = 0x3C

# Geometric render constants
GEO_SLOTS = 6                      # слотов на странице
GEO_SHAPES = ("square", "triangle", "circle", "diamond")
GEO_REST = 16                      # размер невыбранной фигуры, px
GEO_SEL = 28                       # размер выбранной фигуры, px
GEO_GAP = 3                        # зазор, px


class DisplayManager:

    def __init__(self):
        hw      = cfg.get_config().get("hardware", {})
        sda_num = hw.get("display_sda", 4)
        scl_num = hw.get("display_scl", 5)

        sda = getattr(board, "GP" + str(sda_num))
        scl = getattr(board, "GP" + str(scl_num))

        displayio.release_displays()
        i2c = None
        try:
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
            self._lbl_bottom = self._make_label(" ", _cx, 24)
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

            # ── Geometric render группа ─────────────────────────────────────
            self._render_mode = "text"
            self._geo_bitmap = displayio.Bitmap(_W, _H, 2)
            self._geo_palette = displayio.Palette(2)
            self._geo_palette[0] = 0x000000
            self._geo_palette[1] = 0xFFFFFF
            self._geo_group = displayio.Group()
            self._geo_group.append(displayio.TileGrid(self._geo_bitmap, pixel_shader=self._geo_palette))
            self._geo_cursor = 0     # последнее показанное положение курсора
            self._geo_total = 0
            self._geo_depth = 0
            self._geo_target_cursor = 0
            self._geo_target_total = 0
            self._geo_target_depth = 0
            self._geo_last_bump = 0.0

            print("[display] init OK  SDA=GP", sda_num, " SCL=GP", scl_num)
        except Exception:
            if i2c is not None:
                try:
                    i2c.deinit()
                except Exception:
                    pass
            self.i2c = None
            raise

    # ── Public: режим рендера и состояние меню ─────────────────────────────

    def set_render_mode(self, mode):
        """Установить режим рендера: 'text' или 'geometric'."""
        if mode not in ("text", "geometric"):
            print(f"[display] WARNING: unknown render mode '{mode}', defaulting to 'text'")
            mode = "text"
        self._render_mode = mode
        print(f"[display] render mode: {mode}")

    def set_menu_state(self, cursor, total, depth):
        """Запомнить целевое состояние меню (вызывается перед draw_menu/animate_swipe)."""
        self._geo_target_cursor = cursor
        self._geo_target_total = total
        self._geo_target_depth = depth

    def _geo_active(self):
        """Проверка активности геометрического режима."""
        return (
            self._render_mode == "geometric" and
            self._geo_target_depth == 0 and
            self._geo_target_total > 0
        )

    def is_geometric(self):
        """Публичная проверка геометрического режима."""
        return self._render_mode == "geometric"

    def _geo_fail(self, err):
        """Откат на текстовый режим при ошибке геометрического рендера."""
        print("[display] geometric render failed, fallback to text:", err)
        self._render_mode = "text"
        try:
            self._disp.auto_refresh = True
        except Exception:
            pass

    # ── Geometric render: bitmap drawing ───────────────────────────────────

    def _px(self, x, y):
        """Установить пиксель в bitmap с клиппингом."""
        if 0 <= x < _W and 0 <= y < _H:
            self._geo_bitmap[x, y] = 1

    def _fill_shape(self, kind, cx, cy, size, color, dx=0):
        """Залить фигуру с центром (cx+dx, cy), размер size×size."""
        half = size // 2
        cx = cx + dx
        
        if bitmaptools is not None:
            # Быстрый путь через bitmaptools.fill_region
            if kind == "square":
                x1 = max(0, cx - half)
                x2 = min(_W, cx + half + 1)
                y1 = max(0, cy - half)
                y2 = min(_H, cy + half + 1)
                if x1 < x2 and y1 < y2:
                    bitmaptools.fill_region(self._geo_bitmap, x1, y1, x2, y2, color)
            
            elif kind == "circle":
                r = half
                for dy in range(-half, half + 1):
                    y_abs = cy + dy
                    if not (0 <= y_abs < _H):
                        continue
                    dx_max = int((r * r - dy * dy) ** 0.5) if (r * r - dy * dy) >= 0 else 0
                    x1 = max(0, cx - dx_max)
                    x2 = min(_W, cx + dx_max + 1)
                    if x1 < x2:
                        bitmaptools.fill_region(self._geo_bitmap, x1, y_abs, x2, y_abs + 1, color)
            
            elif kind == "triangle":
                for dy in range(-half, half + 1):
                    y_abs = cy + dy
                    if not (0 <= y_abs < _H):
                        continue
                    ratio = (dy + half) / (size if size > 0 else 1)
                    dx_max = int(half * ratio)
                    x1 = max(0, cx - dx_max)
                    x2 = min(_W, cx + dx_max + 1)
                    if x1 < x2:
                        bitmaptools.fill_region(self._geo_bitmap, x1, y_abs, x2, y_abs + 1, color)
            
            elif kind == "diamond":
                for dy in range(-half, half + 1):
                    y_abs = cy + dy
                    if not (0 <= y_abs < _H):
                        continue
                    dx_max = int(half * (1 - abs(dy) / (half if half > 0 else 1)))
                    x1 = max(0, cx - dx_max)
                    x2 = min(_W, cx + dx_max + 1)
                    if x1 < x2:
                        bitmaptools.fill_region(self._geo_bitmap, x1, y_abs, x2, y_abs + 1, color)
        else:
            # Запасной пиксельный путь
            if kind == "square":
                for dy in range(-half, half + 1):
                    for dxx in range(-half, half + 1):
                        x, y = cx + dxx, cy + dy
                        if 0 <= x < _W and 0 <= y < _H:
                            self._geo_bitmap[x, y] = color
            
            elif kind == "circle":
                r = half
                for dy in range(-half, half + 1):
                    dx_max = int((r * r - dy * dy) ** 0.5) if (r * r - dy * dy) >= 0 else 0
                    for dxx in range(-dx_max, dx_max + 1):
                        x, y = cx + dxx, cy + dy
                        if 0 <= x < _W and 0 <= y < _H:
                            self._geo_bitmap[x, y] = color
            
            elif kind == "triangle":
                for dy in range(-half, half + 1):
                    ratio = (dy + half) / (size if size > 0 else 1)
                    dx_max = int(half * ratio)
                    for dxx in range(-dx_max, dx_max + 1):
                        x, y = cx + dxx, cy + dy
                        if 0 <= x < _W and 0 <= y < _H:
                            self._geo_bitmap[x, y] = color
            
            elif kind == "diamond":
                for dy in range(-half, half + 1):
                    dx_max = int(half * (1 - abs(dy) / (half if half > 0 else 1)))
                    for dxx in range(-dx_max, dx_max + 1):
                        x, y = cx + dxx, cy + dy
                        if 0 <= x < _W and 0 <= y < _H:
                            self._geo_bitmap[x, y] = color

    def _draw_shape(self, kind, cx, cy, size, filled, dx=0):
        """Нарисовать фигуру (заливка или контур)."""
        if filled or size <= 6:
            self._fill_shape(kind, cx, cy, size, 1, dx)
        else:
            # Контур: внешняя заливка белым, внутренняя черным
            self._fill_shape(kind, cx, cy, size, 1, dx)
            self._fill_shape(kind, cx, cy, size - 4, 0, dx)

    def _geo_row(self, page, sel_index, sel_size, other_size, dx):
        """Нарисовать ряд слотов для страницы."""
        start_idx = page * GEO_SLOTS
        end_idx = min(self._geo_target_total, (page + 1) * GEO_SLOTS)
        count = end_idx - start_idx
        if count <= 0:
            return
        
        # Вычисляем общую ширину ряда
        total_width = 0
        for i in range(start_idx, end_idx):
            if i == sel_index:
                total_width += sel_size
            else:
                total_width += other_size
        total_width += GEO_GAP * (count - 1)
        
        # Начальная позиция X (центрируем ряд)
        x = (_W - total_width) // 2
        y = 16
        
        # Рисуем слоты
        shape_kind = GEO_SHAPES[page % len(GEO_SHAPES)]
        for i in range(start_idx, end_idx):
            size = sel_size if i == sel_index else other_size
            filled = (i == sel_index)
            half = size // 2
            self._draw_shape(shape_kind, x + half, y, size, filled, dx)
            x += size + GEO_GAP

    # ── Geometric render: static and animation ─────────────────────────────

    def bump(self, direction):
        """Анимация упора в края меню (только для геометрического режима)."""
        if self._render_mode != "geometric" or self._geo_total <= 0:
            return
        
        now = time.monotonic()
        if now - self._geo_last_bump < 0.2:
            return
        self._geo_last_bump = now
        
        try:
            duration = 0.16
            sgn = -1 if direction == "left" else 1
            start_time = time.monotonic()
            
            self._disp.auto_refresh = False
            try:
                while True:
                    elapsed = time.monotonic() - start_time
                    t = min(1.0, elapsed / duration)
                    # Треугольный профиль: вперёд до 0.5, назад после 0.5
                    p = t * 2 if t < 0.5 else (1 - t) * 2
                    dx = int(round(sgn * 6 * p))
                    
                    self._geo_bitmap.fill(0)
                    
                    # Рисуем ряд со сдвигом
                    page = self._geo_cursor // GEO_SLOTS
                    self._geo_row(page, self._geo_cursor, GEO_SEL, GEO_REST, dx)
                    
                    # Рисуем стенку
                    if bitmaptools is not None:
                        if direction == "left":
                            bitmaptools.fill_region(self._geo_bitmap, 0, 0, 2, _H, 1)
                        else:
                            bitmaptools.fill_region(self._geo_bitmap, _W - 2, 0, _W, _H, 1)
                    else:
                        # Запасной путь через _px
                        if direction == "left":
                            for y in range(_H):
                                self._geo_bitmap[0, y] = 1
                                self._geo_bitmap[1, y] = 1
                        else:
                            for y in range(_H):
                                self._geo_bitmap[_W - 2, y] = 1
                                self._geo_bitmap[_W - 1, y] = 1
                    
                    self._disp.root_group = self._geo_group
                    self._disp.refresh()
                    
                    if t >= 1.0:
                        break
            finally:
                self._disp.auto_refresh = True
            
            # Финальный статичный кадр
            self._draw_geo_static(self._geo_cursor, self._geo_total)
        except Exception as e:
            self._geo_fail(e)

    def _draw_geo_static(self, cursor, total):
        """Статичная отрисовка геометрического меню."""
        self._disp.auto_refresh = False
        try:
            self._geo_bitmap.fill(0)
            page = cursor // GEO_SLOTS
            self._geo_row(page, cursor, GEO_SEL, GEO_REST, 0)
            self._disp.root_group = self._geo_group
            self._disp.refresh()
        finally:
            self._disp.auto_refresh = True
        self._geo_cursor = cursor
        self._geo_total = total

    def _animate_geo(self, old_cursor, new_cursor, total, direction):
        """Анимация переходов в геометрическом режиме."""
        old_page = old_cursor // GEO_SLOTS
        new_page = new_cursor // GEO_SLOTS
        
        self._disp.auto_refresh = False
        try:
            if old_page == new_page:
                # Анимация роста внутри одной страницы
                duration = 0.14
                start_time = time.monotonic()
                
                while True:
                    elapsed = time.monotonic() - start_time
                    t = min(1.0, elapsed / duration)
                    # Ease-out: p = 1 - (1 - t)^2
                    p = 1 - (1 - t) * (1 - t)
                    
                    old_size = int(GEO_SEL - (GEO_SEL - GEO_REST) * p)
                    new_size = int(GEO_REST + (GEO_SEL - GEO_REST) * p)
                    
                    self._geo_bitmap.fill(0)
                    
                    # Рисуем старый выбранный (сжимается)
                    old_page_calc = old_cursor // GEO_SLOTS
                    start_idx = old_page_calc * GEO_SLOTS
                    end_idx = min(total, (old_page_calc + 1) * GEO_SLOTS)
                    count = end_idx - start_idx
                    
                    # Пересчитываем ширину с текущими размерами
                    total_width = 0
                    for idx in range(start_idx, end_idx):
                        if idx == old_cursor:
                            total_width += old_size
                        elif idx == new_cursor:
                            total_width += new_size
                        else:
                            total_width += GEO_REST
                    total_width += GEO_GAP * (count - 1)
                    
                    x = (_W - total_width) // 2
                    y = 16
                    shape_kind = GEO_SHAPES[old_page_calc % len(GEO_SHAPES)]
                    
                    for idx in range(start_idx, end_idx):
                        if idx == old_cursor:
                            size = old_size
                            filled = True
                        elif idx == new_cursor:
                            size = new_size
                            filled = True
                        else:
                            size = GEO_REST
                            filled = False
                        
                        half = size // 2
                        self._draw_shape(shape_kind, x + half, y, size, filled, 0)
                        x += size + GEO_GAP
                    
                    self._disp.root_group = self._geo_group
                    self._disp.refresh()
                    
                    if t >= 1.0:
                        break
            else:
                # Анимация слайда между страницами
                duration = 0.18
                start_time = time.monotonic()
                step_px = _W
                dir_mult = 1 if direction == "right" else -1
                
                while True:
                    elapsed = time.monotonic() - start_time
                    t = min(1.0, elapsed / duration)
                    # Ease-out: p = 1 - (1 - t)^2
                    p = 1 - (1 - t) * (1 - t)
                    
                    self._geo_bitmap.fill(0)
                    offset = int(step_px * p)
                    
                    # Старая страница уходит
                    old_dx = -dir_mult * offset
                    self._geo_row(old_page, old_cursor, GEO_REST, GEO_REST, old_dx)
                    
                    # Новая страница входит
                    new_dx = dir_mult * (step_px - offset)
                    self._geo_row(new_page, new_cursor, GEO_SEL, GEO_REST, new_dx)
                    
                    self._disp.root_group = self._geo_group
                    self._disp.refresh()
                    
                    if t >= 1.0:
                        break
        finally:
            self._disp.auto_refresh = True
        
        # Обновляем текущее состояние
        self._geo_cursor = new_cursor
        self._geo_total = total

    # ── Public: основные экраны ────────────────────────────────────────────

    def draw_menu(self, item_label, action_name=""):
        if self._geo_active():
            try:
                self._draw_geo_static(self._geo_target_cursor, self._geo_target_total)
                return
            except Exception as e:
                self._geo_fail(e)
        
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

    def show_encoder_control(self, mode_label, mode_type=""):
        _cx = _W // 2
        self._lbl_top.anchored_position    = (_cx, 4)
        self._lbl_center.anchored_position = (_cx, 16)
        self._lbl_bottom.anchored_position = (_cx, 27)

        self._lbl_top.text    = "< CONTROL >"
        self._lbl_center.text = self._fit(mode_label, 21)
        self._lbl_bottom.text = self._fit(mode_type, 21) if mode_type else "Long: Exit"

        self._disp.root_group = self._main_group

    def show_boot(self):
        self.show_status(line2="Booting...")

    # ── Public: анимация перехода ──────────────────────────────────────────

    def animate_swipe(self, old_label, new_label, direction="right"):
        if self._geo_active():
            try:
                self._animate_geo(self._geo_cursor, self._geo_target_cursor, self._geo_target_total, direction)
                return
            except Exception as e:
                self._geo_fail(e)
        
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
