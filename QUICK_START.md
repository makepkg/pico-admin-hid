# Quick Start Guide

Get Pico Commander running in 10 minutes.

---

## Prerequisites

- Raspberry Pi Pico board
- Micro-USB cable
- Components: SSD1306 OLED (128×32), KY-040 rotary encoder
- Optional: Hall effect sensors

---

## Step 1: Flash CircuitPython (2 minutes)

1. **Download firmware**:
   - https://circuitpython.org/board/raspberry_pi_pico/
   - Get CircuitPython 9.x UF2 file

2. **Enter bootloader**:
   - Hold **BOOTSEL** button on Pico
   - Connect USB while holding
   - Release button
   - Pico appears as **RPI-RP2** drive

3. **Flash**:
   - Copy `.uf2` file to RPI-RP2 drive
   - Pico reboots automatically
   - Now appears as **CIRCUITPY** drive ✓

---

## Step 2: Install Libraries (3 minutes)

### Option A: Use Included Libraries (Easiest)

If you cloned this repo, libraries are already in `lib/` folder:

```bash
# Linux/macOS
cp -r lib/* /media/$USER/CIRCUITPY/lib/

# Windows
Copy-Item -Recurse lib\* D:\lib\
```

### Option B: Download from Adafruit Bundle

1. **Check CircuitPython version**:
   - Open `boot_out.txt` on CIRCUITPY drive
   - Note version (e.g., 9.0.0)

2. **Download bundle**:
   - https://circuitpython.org/libraries
   - Click "Download Bundle" for your version
   - Extract ZIP file

3. **Copy 3 items** from bundle `lib/` to CIRCUITPY `lib/`:
   - `adafruit_displayio_ssd1306.mpy` (file)
   - `adafruit_display_text/` (folder)
   - `adafruit_hid/` (folder)

---

## Step 3: Deploy Code (2 minutes)

Copy all Python files to CIRCUITPY root:

```bash
# Required files:
boot.py
code.py
config.py
config.json
display.py
encoder.py
inputs_manager.py
output_base.py
output_hid.py
output_gpio.py
trigger_bus.py
screensaver.py
ina226_monitor.py
splash_screen.py
splash_trigger.py
warning_screen.py
```

**Linux/macOS**:
```bash
cp *.py *.json /media/$USER/CIRCUITPY/
```

**Windows**:
```bash
Copy-Item *.py, *.json D:\
```

---

## Step 4: Connect Hardware (3 minutes)

### Minimum Setup (OLED + Encoder)

| Component | Connection |
|-----------|------------|
| **OLED Display** | |
| SDA | GP4 |
| SCL | GP5 |
| VCC | 3.3V |
| GND | GND |
| **Rotary Encoder** | |
| CLK | GP6 |
| DT | GP7 |
| SW | GP8 |
| + | 3.3V |
| GND | GND |

### Optional: Hall Sensors

| Component | Connection |
|-----------|------------|
| Sensor 1 OUT | GP15 |
| Sensor 2 OUT | GP16 |
| VCC | 3.3V |
| GND | GND |

---

## Step 5: Test (1 minute)

1. **Disconnect** Pico from USB
2. **Reconnect** (normal boot, no button pressed)
3. **Check OLED**: Should show "Booting..." then menu
4. **Test encoder**:
   - Rotate → Menu scrolls with animation
   - Click → Executes action
   - Long press → Goes back

---

## Next Steps

### Configure Your Menu

**Option A: Visual Editor** (Recommended)
1. Open `editor.html` in browser
2. Click "Load config.json" from CIRCUITPY
3. Build your menu visually
4. Save and copy back to Pico

**Option B: Manual Edit**
1. Edit `config.json` on CIRCUITPY (boot in dev mode: hold GP24 button)
2. Modify `active_menu` and `scenarios` sections
3. Reboot Pico

### Example Scenario

Add to `config.json`:

```json
"scenarios": {
  "test_hello": [
    {"output": "hid", "action": "type", "value": "Hello from Pico Commander!"},
    {"output": "hid", "action": "key", "combo": "enter"}
  ]
},
"active_menu": [
  {
    "id": "test_item",
    "label": "Test Hello",
    "pipeline": ["test_hello"],
    "loop": false
  }
]
```

Open text editor, select "Test Hello", click encoder. Text should appear!

---

## Troubleshooting

### Display Blank
- Check I2C wiring (SDA/SCL)
- Verify OLED address is 0x3C
- Test with multimeter: 3.3V on VCC

### Encoder Not Responding
- Check CLK/DT/SW pins
- Swap CLK/DT if direction inverted
- Verify 3.3V power

### "No module named..."
- Check `lib/` folder has all 3 libraries
- Verify bundle version matches CircuitPython version
- Re-copy libraries from bundle

### USB Keyboard Not Working
- Check USB connected: LED should blink on boot
- Verify `boot.py` enables HID
- Test on different computer/port

---

## Full Documentation

- **Complete Installation**: [README.md](README.md#-installation)
- **Config Editor Guide**: [docs/user/config-editor.md](docs/user/config-editor.md)
- **Pipelines & Scenarios**: [docs/user/pipelines.md](docs/user/pipelines.md)
- **Technical Docs**: [docs/developers/](docs/developers/)

---

## Community

- **Report Issues**: [GitHub Issues](../../issues)
- **Ask Questions**: [GitHub Discussions](../../discussions)
- **Contribute**: [CONTRIBUTORS.md](CONTRIBUTORS.md)

---

**Estimated Total Time**: 10 minutes  
**Difficulty**: Beginner-friendly  
**Cost**: ~$15 in parts
