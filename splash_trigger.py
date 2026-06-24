import time
import json

class SplashTrigger:
    def __init__(self, interval=None):
        if interval is None:
            # Читаем из конфига если не передан явно
            try:
                with open("config.json") as f:
                    cfg = json.load(f)
                self.interval = cfg.get("inputs", {}).get("ina226", {}).get("splash_interval_sec", 30)
            except Exception:
                self.interval = 30
        else:
            self.interval = interval
        
        self.last_splash_time = time.monotonic()
        self.last_reason = ""

    def tick(self, is_idle: bool, ina_available: bool = True) -> bool:
        """
        Если ina_available=False — таймер не считается, всегда False.
        """
        if not ina_available:
            return False
        
        if not is_idle:
            return False  # не сбрасывать таймер, просто не срабатывать
        
        now = time.monotonic()
        
        if now - self.last_splash_time >= self.interval:
            self.last_splash_time = now
            self.last_reason = "TIMER"
            return True
            
        return False

    def reset_timer(self):
        """Сброс таймера при входе в screensaver"""
        self.last_splash_time = time.monotonic()

    def fire_event(self, reason: str) -> bool:
        self.last_reason = reason
        self.last_splash_time = time.monotonic()
        return True
