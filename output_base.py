"""output_base.py — базовый класс для всех output handlers.

Архитектура:
trigger_bus → OutputsManager → конкретный OutputHandler

Каждый handler:
- Читает свою секцию из config["outputs"][name]
- Реализует execute(action) для выполнения действий
- Возвращает True/False для error handling
"""


class OutputHandler:
    """Базовый класс для output handlers (HID, GPIO, и т.д.).
    
    Все handlers должны наследоваться от этого класса.
    """
    
    def __init__(self, name, config):
        """
        Args:
            name: имя output (напр. "hid", "opto_pwr")
            config: dict из config.json["outputs"][name]
        """
        self.name = name
        self._config = config
        self._enabled = config.get("enabled", True)
        print(f"[output:{name}] Init, enabled={self._enabled}")
    
    @property
    def enabled(self):
        return self._enabled
    
    def execute(self, action):
        """Выполнить действие.
        
        Args:
            action: dict шага сценария, напр. {"action": "type", "value": "text"}
            
        Returns:
            bool: True при успехе, False при ошибке
        """
        raise NotImplementedError("Subclass must implement execute()")
    
    def cleanup(self):
        """Опционально: очистка ресурсов при завершении."""
        pass
