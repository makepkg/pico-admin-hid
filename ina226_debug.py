import board
import busio

def scan_i2c(i2c_bus=None):
    print("--- I2C Scanner ---")
    
    own_i2c = False
    try:
        if i2c_bus is None:
            print("Initializing I2C on SDA=GP4, SCL=GP5...")
            i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
            own_i2c = True
        else:
            print("Using provided shared I2C bus...")
            i2c = i2c_bus
            
        # Перед сканированием шину необходимо заблокировать
        while not i2c.try_lock():
            pass
            
        print("Scanning for devices...")
        addresses = i2c.scan()
        
        # Разблокируем шину
        i2c.unlock()
        
        if own_i2c:
            i2c.deinit()

        if not addresses:
            print("No I2C devices found on bus.")
            return

        print(f"Found {len(addresses)} device(s):")
        ina226_found = False
        
        for addr in addresses:
            hex_addr = hex(addr)
            print(f" - {hex_addr}")
            if addr == 0x40:
                ina226_found = True
                
        print("-------------------")
        if ina226_found:
            print("INA226 OK")
        else:
            print("INA226 NOT FOUND")

