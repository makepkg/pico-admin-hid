"""
trigger_bus.py — центральная шина триггеров с поддержкой множественных outputs.

Единственная точка исполнения сценариев для всей системы.
Предотвращает конфликты через busy-флаг и cooldown.

Приоритеты:
  PRIORITY_LOW    (0) — зарезервирован
  PRIORITY_NORMAL (1) — активное меню, кнопка
  PRIORITY_HIGH   (2) — датчик Холла (аварийный) — обходит cooldown
"""

import time
import config as cfg

# Импорты новых output handlers
from output_hid import HidOutput
from output_gpio import GpioOutput

PRIORITY_LOW    = 0
PRIORITY_NORMAL = 1
PRIORITY_HIGH   = 2

_outputs_manager = None
_busy           = False
_cooldown_until = 0.0


# ── OutputsManager ─────────────────────────────────────────────────────────

class OutputsManager:
    """Управляет всеми output handlers (HID, GPIO, и т.д.)"""
    
    def __init__(self, config):
        self._outputs = {}
        outputs_config = config.get("outputs", {})
        
        for name, cfg_dict in outputs_config.items():
            output_type = cfg_dict.get("type")
            try:
                if output_type == "hid":
                    self._outputs[name] = HidOutput(name, cfg_dict)
                elif output_type == "gpio":
                    self._outputs[name] = GpioOutput(name, cfg_dict)
                else:
                    print(f"[outputs] Unknown type '{output_type}' for output '{name}'")
            except Exception as e:
                print(f"[outputs] Failed to init output '{name}':", e)
        
        print(f"[outputs] Manager ready: {len(self._outputs)} outputs loaded")
    
    def execute(self, output_name, action):
        """Выполнить действие через указанный output.
        
        Args:
            output_name: имя output из config (напр. "hid", "opto_pwr")
            action: dict шага сценария
        
        Returns:
            bool: успех выполнения
        """
        handler = self._outputs.get(output_name)
        if handler is None:
            print(f"[outputs] Output '{output_name}' not found")
            return False
        
        if not handler.enabled:
            print(f"[outputs] Output '{output_name}' is disabled")
            return False
        
        return handler.execute(action)
    
    def get(self, output_name):
        """Получить handler по имени (для прямого доступа)"""
        return self._outputs.get(output_name)


# ── Init ───────────────────────────────────────────────────────────────────

def init():
    """Инициализация outputs manager — вызывать ДО любых fire()"""
    global _outputs_manager
    conf = cfg.get_config()
    _outputs_manager = OutputsManager(conf)
    print("[bus] Outputs manager OK")


def execute_output(output_name, action):
    """Выполнить действие через указанный output (публичный API).
    
    Args:
        output_name: имя output из config (напр. "hid", "opto_pwr")
        action: dict действия (напр. {"action": "gpio_pulse"})
    
    Returns:
        bool: True при успехе, False при ошибке
    
    Example:
        success = trigger_bus.execute_output("opto_pwr", {"action": "gpio_pulse"})
    """
    if _outputs_manager is None:
        print("[bus] ERROR: execute_output called before init()")
        return False
    
    return _outputs_manager.execute(output_name, action)


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

# ── Public API ─────────────────────────────────────────────────────────────

def execute_pipeline(pipeline_config, trigger_id, priority=PRIORITY_NORMAL):
    """
    Универсальная функция выполнения пайплайна триггера.
    
    Args:
        pipeline_config: dict с ключами:
            - "pipeline": list[str|dict] - список сценариев (строки или {"scenario": "...", "label": "..."})
            - "loop": bool - режим выполнения (false=все подряд, true=циклический)
        trigger_id: str - ID триггера для отслеживания позиции (при loop=true)
        priority: int - приоритет выполнения
    
    Returns:
        bool: успех выполнения
    
    Modes:
        loop=false: выполняет все сценарии из pipeline подряд (halt on error)
        loop=true:  выполняет один сценарий по текущей позиции, инкрементирует позицию
    """
    global _busy
    if not _can_fire(priority):
        return False
    
    pipeline = pipeline_config.get("pipeline", [])
    if not pipeline:
        print(f"[bus] empty pipeline for trigger '{trigger_id}'")
        return False
    
    loop_mode = pipeline_config.get("loop", False)
    
    _busy = True
    try:
        if loop_mode:
            # Циклический режим - один сценарий за раз
            state = cfg.get_state()
            positions = state.setdefault("trigger_positions", {})
            pos = positions.get(trigger_id, 0) % len(pipeline)
            
            item = pipeline[pos]
            # Backward compatibility: support both string and dict format
            scenario_name = item["scenario"] if isinstance(item, dict) else item
            _run_scenario(scenario_name)
            
            # Инкремент позиции для следующего вызова
            positions[trigger_id] = (pos + 1) % len(pipeline)
            cfg.save_state()
        else:
            # Последовательный режим - все подряд
            for item in pipeline:
                # Backward compatibility: support both string and dict format
                scenario_name = item["scenario"] if isinstance(item, dict) else item
                _run_scenario(scenario_name)
    finally:
        _busy = False
        _apply_cooldown()
    
    return True


def fire(trigger_name, priority=PRIORITY_NORMAL):
    """Пассивный триггер с поддержкой нового формата pipeline."""
    conf = cfg.get_config()
    trigger_config = conf.get("passive", {}).get(trigger_name)
    
    if not trigger_config:
        print("[bus] нет привязки для пассивного триггера:", trigger_name)
        return False
    
    # Обратная совместимость: строка → конвертировать в pipeline
    if isinstance(trigger_config, str):
        trigger_config = {
            "pipeline": [trigger_config],
            "loop": False
        }
    
    return execute_pipeline(trigger_config, f"passive_{trigger_name}", priority)


def fire_scenario(scenario_name, priority=PRIORITY_NORMAL):
    """Запускает сценарий напрямую по имени (для auto-boot и других служебных задач)."""
    global _busy
    if not _can_fire(priority):
        return False

    _busy = True
    try:
        _run_scenario(scenario_name)
    finally:
        _busy = False
        _apply_cooldown()
    return True


def fire_active(item_id):
    """Активный триггер (меню) с поддержкой нового формата pipeline."""
    conf = cfg.get_config()
    menu = conf.get("active_menu", [])
    item = _find_item(menu, item_id)

    if not item:
        print("[bus] active item не найден:", item_id)
        return False

    # Новый формат: {"pipeline": [...], "loop": true}
    if "pipeline" in item:
        return execute_pipeline(item, f"active_{item_id}", PRIORITY_NORMAL)
    
    # Обратная совместимость: старый формат "sequence"
    sequence = item.get("sequence", [])
    if not sequence:
        print("[bus] пустой sequence у:", item_id)
        return False
    
    # Конвертировать sequence в pipeline format
    pipeline = [_resolve_seq_entry(entry)[0] for entry in sequence]
    pipeline_config = {
        "pipeline": pipeline,
        "loop": True  # sequence всегда был циклическим
    }
    
    return execute_pipeline(pipeline_config, f"active_{item_id}", PRIORITY_NORMAL)


def is_busy():
    return _busy


def get_next_action_name(item_id):
    """Возвращает имя следующего действия для дисплея (без побочных эффектов)."""
    conf = cfg.get_config()
    state = cfg.get_state()

    menu = conf.get("active_menu", [])
    item = _find_item(menu, item_id)

    if not item:
        return ""

    # Новый формат: pipeline
    if "pipeline" in item:
        pipeline = item.get("pipeline", [])
        if not pipeline:
            return ""
        
        loop_mode = item.get("loop", False)
        if loop_mode:
            positions = state.get("trigger_positions", {})
            pos = positions.get(f"active_{item_id}", 0) % len(pipeline)
            return pipeline[pos]
        else:
            # Для loop=false показываем первый сценарий
            return pipeline[0]
    
    # Обратная совместимость: старый sequence
    sequence = item.get("sequence", [])
    if not sequence:
        return ""

    positions = state.get("seq_positions", {})
    pos = positions.get(item_id, 0) % len(sequence)
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
    """Выполнение сценария с поддержкой множественных outputs"""
    scenarios = cfg.get_config().get("scenarios", {})
    steps = scenarios.get(name)

    if not steps:
        print("[bus] сценарий не найден:", name)
        return

    print("[bus] →", name)
    for step in steps:
        # Специальный случай: {"wait": 500} — короткий формат паузы
        if "wait" in step:
            try:
                time.sleep(step.get("wait", 0) / 1000.0)
            except Exception as e:
                print("[bus] ошибка wait:", e)
            continue
        
        # Специальный случай: {"action": "wait", "ms": 500} — старый формат
        if "action" in step and step["action"] == "wait":
            try:
                time.sleep(step.get("ms", 0) / 1000.0)
            except Exception as e:
                print("[bus] ошибка wait:", e)
            continue
        
        # Определяем output (default = "hid" для обратной совместимости)
        output_name = step.get("output", "hid")
        
        # Выполняем через outputs manager
        success = _outputs_manager.execute(output_name, step)
        if not success:
            print(f"[bus] WARNING: step failed for output '{output_name}'")
            # Не прерываем сценарий — продолжаем выполнение

    print("[bus] ✓", name)

