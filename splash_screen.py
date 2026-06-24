import time
import displayio
import terminalio
from adafruit_display_text import label
import json

class SplashScreen:
    ANIM_FRAMES = 30        # кадров на анимацию count-up
    FRAME_INTERVAL = 0.025  # секунд между кадрами (~40fps)

    def __init__(self, disp):
        self._disp = disp
        self._group = displayio.Group()
        
        # Строка 1: Прогресс-бар
        self._line1 = label.Label(terminalio.FONT, x=0, y=5, color=0xFFFFFF)
        # Строка 2: Метрики
        self._line2 = label.Label(terminalio.FONT, x=0, y=21, color=0xFFFFFF)
        
        self._group.append(self._line1)
        self._group.append(self._line2)
        
        self._active = False
        self._prev_root = None
        self._metrics = None
        self._frame = 0
        self._next_frame_t = 0.0
        self._hide_at = 0.0
        
        # Load duration from config.json
        try:
            with open("config.json") as f:
                cfg = json.load(f)
            _ina = cfg.get("inputs", {}).get("ina226", {})
            self._duration = _ina.get("splash_duration_sec", 6)
        except Exception:
            self._duration = 6

    def show(self, metrics):
        if metrics is None:
            return
            
        try:
            self._prev_root = self._disp.root_group
            self._disp.root_group = self._group
            
            self._metrics = metrics
            self._frame = 0
            
            now = time.monotonic()
            self._next_frame_t = now
            self._hide_at = now + self._duration
            
            v = self._metrics.get("voltage", 0.0)
            c = self._metrics.get("current_ma", 0.0)
            s = self._metrics.get("state", "IDLE")
            
            self._line2.text = f"{v:5.1f}V{c:5.0f}mA {s}"
            
            self._active = True
        except Exception:
            pass

    def tick(self) -> bool:
        if not self._active:
            return False
            
        try:
            now = time.monotonic()
            if now >= self._hide_at:
                self._hide()
                return False
                
            if now >= self._next_frame_t and self._frame <= self.ANIM_FRAMES:
                target_pct = self._metrics.get("percent", 0)
                cur_pct = int(target_pct * self._frame / self.ANIM_FRAMES)
                
                filled = round(cur_pct / 10)
                bar = "#" * filled + "-" * (10 - filled)
                
                self._line1.text = f"PWR[{bar}]{cur_pct:3d}%"
                
                self._frame += 1
                self._next_frame_t = now + self.FRAME_INTERVAL
                
                if self._frame > self.ANIM_FRAMES:
                    # Убеждаемся, что в конце точно стоит финальное значение
                    filled = round(target_pct / 10)
                    bar = "#" * filled + "-" * (10 - filled)
                    self._line1.text = f"PWR[{bar}]{target_pct:3d}%"
                    
            return True
        except Exception:
            return True

    def _hide(self):
        try:
            if self._prev_root is not None:
                self._disp.root_group = self._prev_root
            self._active = False
            self._prev_root = None
        except Exception:
            pass

    @property
    def is_active(self):
        return self._active
