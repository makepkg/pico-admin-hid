"""
config.py — загрузка config.json и state.json, сохранение state.

Публичное API:
  load()        — вызвать один раз при старте из code.py
  get_config()  — вернуть dict конфигурации (read-only)
  get_state()   — вернуть dict состояния (изменяемый)
  save_state()  — записать state.json на диск
"""

import json
import os

_CONFIG_PATH = "config.json"
_STATE_PATH  = "state.json"

_config = {}
_state  = {}


# ── Public API ─────────────────────────────────────────────────────────────

def load():
    """Загружает config.json и state.json. Вызвать один раз из code.py."""
    global _config, _state

    # --- config.json (обязателен) ----------------------------------------
    try:
        with open(_CONFIG_PATH, "r") as f:
            _config = json.load(f)
        print("[config] config.json OK")
    except OSError:
        print("[config] WARN: config.json не найден — используем пустой конфиг")
        _config = {}
    except ValueError as e:
        print("[config] WARN: ошибка разбора config.json:", e)
        _config = {}

    # --- state.json (создаётся если отсутствует) --------------------------
    try:
        with open(_STATE_PATH, "r") as f:
            _state = json.load(f)
        print("[config] state.json OK")
    except (OSError, ValueError):
        print("[config] state.json не найден — создаём с нулями")
        _state = {}

    _migrate_state()
    _check_pin_conflicts()


def get_config():
    """Возвращает dict конфигурации."""
    return _config


def get_state():
    """Возвращает dict состояния. Изменения нужно зафиксировать через save_state()."""
    return _state


def save_state():
    """Записывает текущий _state в state.json."""
    try:
        with open(_STATE_PATH, "w") as f:
            json.dump(_state, f)
    except OSError as e:
        print("[config] WARN: не удалось сохранить state.json:", e)


# ── Internal ───────────────────────────────────────────────────────────────

def _migrate_state():
    """
    Тихая миграция: если в active_menu появился новый сервис,
    добавляем его в seq_positions с позицией 0.
    Старые записи не трогаем.
    """
    menu      = _config.get("active_menu", [])
    positions = _state.setdefault("seq_positions", {})
    cursor    = _state.setdefault("menu_cursor", 0)

    changed = False
    for item in menu:
        item_id = item.get("id")
        if item_id and item_id not in positions:
            positions[item_id] = 0
            changed = True
            print("[config] migrate: seq_positions добавлен:", item_id)

    # Защита курсора от выхода за пределы
    if menu and cursor >= len(menu):
        _state["menu_cursor"] = 0
        changed = True

    if changed:
        save_state()


def _add_pin(pin_usage, pin_num, module, purpose):
    """Helper: добавляет пин в словарь использования для проверки конфликтов."""
    if pin_num is not None:
        pin_usage.setdefault(pin_num, []).append((module, purpose))


def _check_pin_conflicts():
    """Проверяет конфликты пинов между модулями на основе config.json.

    Учитывает только модули, реально enabled в текущем конфиге (display_enabled,
    encoder_enabled, outputs[*].enabled) — отключённый модуль не считается
    занимающим пин. Не останавливает загрузку, только логирует предупреждение;
    физическая инициализация (try/except в code.py/InputsManager) остаётся
    последней линией защиты.
    """
    hw = _config.get("hardware", {})
    inputs_cfg = _config.get("inputs", {})
    outputs_cfg = _config.get("outputs", {})
    device = _config.get("device", {})

    pin_usage = {}

    if device.get("display_enabled", True):
        _add_pin(pin_usage, hw.get("display_sda", 4), "Display", "I2C SDA")
        _add_pin(pin_usage, hw.get("display_scl", 5), "Display", "I2C SCL")

    if device.get("encoder_enabled", True):
        _add_pin(pin_usage, hw.get("encoder_clk", 6), "Encoder", "CLK")
        _add_pin(pin_usage, hw.get("encoder_dt", 7), "Encoder", "DT")
        _add_pin(pin_usage, hw.get("encoder_sw", 8), "Encoder", "SW")

    _add_pin(pin_usage, hw.get("button_pin", 24), "Button", "USR")
    _add_pin(pin_usage, hw.get("led_pin", 25), "LED", "Status")

    for input_id, input_cfg in inputs_cfg.items():
        input_type = input_cfg.get("type")

        if input_type == "hall":
            _add_pin(pin_usage, input_cfg.get("pin"), f"Hall[{input_id}]", "Sensor")

        elif input_type == "trackball":
            _add_pin(pin_usage, input_cfg.get("pin_up"), f"Trackball[{input_id}]", "UP")
            _add_pin(pin_usage, input_cfg.get("pin_down"), f"Trackball[{input_id}]", "DOWN")
            _add_pin(pin_usage, input_cfg.get("pin_left"), f"Trackball[{input_id}]", "LEFT")
            _add_pin(pin_usage, input_cfg.get("pin_right"), f"Trackball[{input_id}]", "RIGHT")
            _add_pin(pin_usage, input_cfg.get("pin_button"), f"Trackball[{input_id}]", "BTN")

    for output_id, output_cfg in outputs_cfg.items():
        if output_cfg.get("enabled", True) and output_cfg.get("type") == "gpio":
            _add_pin(pin_usage, output_cfg.get("pin"), f"Output[{output_id}]", "GPIO")

    conflicts = {pin: users for pin, users in pin_usage.items() if len(users) > 1}

    if conflicts:
        print("[config] WARN: PIN CONFLICTS DETECTED:")
        for pin, users in sorted(conflicts.items()):
            details = ", ".join(f"{m}({p})" for m, p in users)
            print(f"[config]   GP{pin}: {details}")
        print("[config] Один из конфликтующих модулей не сможет корректно инициализироваться")
