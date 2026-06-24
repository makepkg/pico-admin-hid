"""
ina226_monitor.py — INA226 Power Monitor

Reads voltage/current from INA226 I2C sensor.
Configuration is now passed from config.json inputs section.
"""

class SimpleINA226:
    def __init__(self, i2c, address, shunt_ohms):
        self.i2c = i2c
        self.address = address
        self.shunt_ohms = shunt_ohms
        self.buf1 = bytearray(1)
        self.buf2 = bytearray(2)
        self.found = False
        if i2c:
            try:
                while not i2c.try_lock():
                    pass
                if address in i2c.scan():
                    self.found = True
                i2c.unlock()
            except Exception:
                pass
            
    def read(self):
        if not self.found or not self.i2c: return None, None
        try:
            while not self.i2c.try_lock(): pass
            
            # Напряжение шины
            self.buf1[0] = 0x02
            self.i2c.writeto(self.address, self.buf1)
            self.i2c.readfrom_into(self.address, self.buf2)
            bus_v = ((self.buf2[0] << 8) | self.buf2[1]) * 1.25 / 1000.0
            
            # Напряжение шунта
            self.buf1[0] = 0x01
            self.i2c.writeto(self.address, self.buf1)
            self.i2c.readfrom_into(self.address, self.buf2)
            raw_shunt = (self.buf2[0] << 8) | self.buf2[1]
            if raw_shunt > 32767: raw_shunt -= 65536
            
            # Ток в мА: (raw * 2.5uV) / R_shunt 
            current_ma = (raw_shunt * 0.0025) / self.shunt_ohms
            
            self.i2c.unlock()
            return bus_v, current_ma
        except Exception:
            try:
                self.i2c.unlock()
            except Exception:
                pass
            return None, None

class INA226Monitor:
    def __init__(self, i2c, cfg_input):
        """
        Args:
            i2c: I2C bus object
            cfg_input: dict from config.json inputs.ina226
        """
        self.available = False
        self.cfg = cfg_input
        
        if not cfg_input.get("enabled", False):
            return
        
        address = cfg_input.get("i2c_address", 64)  # 0x40 = 64
        shunt_ohms = cfg_input.get("shunt_ohms", 0.1)
        
        self.ina = SimpleINA226(i2c, address, shunt_ohms)
        if self.ina.found:
            self.available = True
        
        self.battery_max_v = cfg_input.get("battery_max_v", 21.0)
        self.battery_min_v = cfg_input.get("battery_min_v", 15.0)

    def get_metrics(self):
        if not self.available:
            return None
            
        try:
            v, c_ma = self.ina.read()
            
            if v is None or c_ma is None:
                self.available = False
                return None
                
            p_w = (v * c_ma) / 1000.0
            
            # Процент заряда (линейная интерполяция, clamp 0-100)
            if v >= self.battery_max_v:
                pct = 100
            elif v <= self.battery_min_v:
                pct = 0
            else:
                pct = int((v - self.battery_min_v) / (self.battery_max_v - self.battery_min_v) * 100)
                
            # State
            if c_ma > 5.0:
                state = "ONLINE"
            else:
                state = "IDLE"
                
            if pct < 15:
                state = "WARN"
                
            return {
                "voltage": float(v),
                "current_ma": float(c_ma),
                "power_w": float(p_w),
                "percent": int(pct),
                "state": str(state)
            }
        except Exception:
            self.available = False
            return None
