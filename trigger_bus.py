"""
trigger_bus.py — центральная шина триггеров.

Единственная точка исполнения сценариев для всей системы.
Предотвращает конфликты через busy-флаг и cooldown.

Приоритеты:
  PRIORITY_LOW    (0) — зарезервирован
  PRIORITY_NORMAL (1) — активное меню, кнопка
  PRIORITY_HIGH   (2) — датчик Холла (аварийный) — обходит cooldown
"""

import time
import supervisor
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import config as cfg

PRIORITY_LOW    = 0
PRIORITY_NORMAL = 1
PRIORITY_HIGH   = 2

_kbd     = None
_layout  = None
_key_map = None

_busy           = False
_cooldown_until = 0.0


# ── Init ───────────────────────────────────────────────────────────────────

def init():
    global _kbd, _layout, _key_map
    _kbd     = Keyboard(usb_hid.devices)
    _layout  = KeyboardLayoutUS(_kbd)
    _key_map = _build_key_map()
    print("[bus] keyboard OK")


# ── Internal: рекурсивный поиск элемента по id ────────────────────────────

def _find_item(menu, item_id):
    """
    Рекурсивно ищет элемент с нужным id в menu и вложенных submenu.
    Возвращает dict элемента или None.
    """
    for x in menu:
        if x["id"] == item_id:
            return x
        # Рекурсивно ищем в submenu
        sub = x.get("submenu")
        if sub:
            found = _find_item(sub, item_id)
            if found:
                return found
    return None


# ── Public API ─────────────────────────────────────────────────────────────

def fire(trigger_name, priority=PRIORITY_NORMAL):
    global _busy
    if not _can_fire(priority):
        return False

    scenario_name = cfg.get_config().get("passive", {}).get(trigger_name)
    if not scenario_name:
        print("[bus] нет привязки для пассивного триггера:", trigger_name)
        return False

    _busy = True
    try:
        _run_scenario(scenario_name)
    finally:
        _busy = False
        _apply_cooldown()
    return True


def fire_active(item_id):
    global _busy
    if not _can_fire(PRIORITY_NORMAL):
        return False

    conf  = cfg.get_config()
    state = cfg.get_state()

    menu = conf.get("active_menu", [])
    item = _find_item(menu, item_id)

    if not item:
        print("[bus] active item не найден:", item_id)
        return False

    sequence = item.get("sequence", [])
    if not sequence:
        print("[bus] пустой sequence у:", item_id)
        return False

    positions     = state.setdefault("seq_positions", {})
    pos           = positions.get(item_id, 0) % len(sequence)
    scenario_name, _ = _resolve_seq_entry(sequence[pos])

    _busy = True
    try:
        _run_scenario(scenario_name)
        positions[item_id] = (pos + 1) % len(sequence)
        cfg.save_state()
    finally:
        _busy = False
        _apply_cooldown()
    return True


def is_busy():
    return _busy


def get_next_action_name(item_id):
    """Возвращает имя следующего действия для дисплея (без побочных эффектов)."""
    conf  = cfg.get_config()
    state = cfg.get_state()

    menu = conf.get("active_menu", [])
    item = _find_item(menu, item_id)

    if not item:
        return ""

    sequence = item.get("sequence", [])
    if not sequence:
        return ""

    pos = state.get("seq_positions", {}).get(item_id, 0) % len(sequence)
    _, display_name = _resolve_seq_entry(sequence[pos])
    return display_name


# ── Internal: sequence ─────────────────────────────────────────────────────

def _resolve_seq_entry(entry):
    if isinstance(entry, str):
        return entry, entry
    return entry.get("scenario", ""), entry.get("name", entry.get("scenario", ""))


# ── Internal: anti-conflict ────────────────────────────────────────────────

def _can_fire(priority):
    if _busy:
        print("[bus] DROP — busy")
        return False
    now = time.monotonic()
    if priority < PRIORITY_HIGH and now < _cooldown_until:
        remaining = round(_cooldown_until - now, 1)
        print("[bus] DROP — cooldown", remaining, "s")
        return False
    return True


def _apply_cooldown():
    global _cooldown_until
    ms = cfg.get_config().get("device", {}).get("cooldown_ms", 5000)
    _cooldown_until = time.monotonic() + ms / 1000.0


# ── Internal: scenario execution ──────────────────────────────────────────

def _run_scenario(name):
    scenarios = cfg.get_config().get("scenarios", {})
    steps     = scenarios.get(name)

    if not steps:
        print("[bus] сценарий не найден:", name)
        return

    if not supervisor.runtime.usb_connected:
        print("[bus] USB не подключён — пропуск")
        return

    print("[bus] →", name)
    for step in steps:
        act = step.get("action")
        try:
            if act == "key":
                keys = _parse_combo(step.get("combo", ""))
                if keys:
                    _kbd.press(*keys)
                    _kbd.release_all()

            elif act == "type":
                _layout.write(step.get("value", ""))

            elif act == "wait":
                time.sleep(step.get("ms", 0) / 1000.0)

            elif act == "enter":
                count = max(1, min(step.get("count", 1), 10))
                for _ in range(count):
                    _kbd.press(Keycode.ENTER)
                    _kbd.release_all()
                    time.sleep(0.05)

        except Exception as e:
            print("[bus] ошибка шага '", act, "':", e)
            try:
                _kbd.release_all()
            except Exception:
                pass

    print("[bus] ✓", name)


# ── Internal: key map ──────────────────────────────────────────────────────

def _build_key_map():
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
    for i in range(12):
        km["f" + str(i + 1)] = getattr(Keycode, "F" + str(i + 1))
    for i in range(26):
        c = chr(ord('a') + i)
        km[c] = getattr(Keycode, c.upper())
    for digit, name in {
        "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
        "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE"
    }.items():
        km[digit] = getattr(Keycode, name)
    return km


def _parse_combo(combo_str):
    keys = []
    for part in combo_str.lower().split("+"):
        part = part.strip()
        kc   = _key_map.get(part)
        if kc:
            keys.append(kc)
        else:
            print("[bus] неизвестная клавиша:", part)
    return keys
