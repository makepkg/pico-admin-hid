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
