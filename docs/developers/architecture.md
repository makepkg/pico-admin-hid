# Pico Commander Architecture

Technical documentation for developers and contributors.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Core Components](#core-components)
- [Trigger System](#trigger-system)
- [Execution Flow](#execution-flow)
- [Module Reference](#module-reference)
- [Extension Possibilities](#extension-possibilities)

---

## System Overview

Pico Commander is a **state machine-based automation controller** that translates physical inputs (encoder, sensors, button) into USB HID keyboard commands. The system operates as a **USB HID device** without requiring drivers on the host system.

### Core Concepts

1. **Trigger-Action Model** — Events trigger scenarios; scenarios execute HID commands
2. **Priority System** — Emergency triggers bypass cooldown and queues
3. **State Persistence** — Menu position and sequence states survive reboots
4. **Modular Design** — Each input type has isolated handler with unified output bus

### Design Philosophy

- **Single Responsibility** — Each module handles one input/output type
- **Fail-Safe** — Hardware errors don't crash the system
- **Deterministic** — Same inputs produce same outputs every time
- **Extensible** — New input types integrate via trigger bus API

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         HARDWARE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  Rotary Encoder  │  Hall Sensors  │  Button  │  OLED Display   │
│    (GP6,7,8)     │   (GP15,16)    │  (GP24)  │   (GP4,5 I2C)   │
└────────┬─────────┴────────┬────────┴─────┬────┴─────────┬───────┘
         │                  │              │              │
         ▼                  ▼              ▼              ▼
┌────────────────┐  ┌──────────────┐  ┌─────────┐  ┌──────────┐
│ encoder.py     │  │ passive.py   │  │ config  │  │ display  │
│ • Rotation     │  │ • Hall sense │  │ loader  │  │ manager  │
│ • Click        │  │ • Dbl-click  │  └────┬────┘  └────┬─────┘
│ • Long press   │  │ • Debounce   │       │            │
└───────┬────────┘  └──────┬───────┘       │            │
        │                  │                │            │
        │                  │                ▼            │
        │                  │         ┌──────────────┐   │
        │                  │         │  config.py   │   │
        │                  │         │ • JSON parse │   │
        │                  │         │ • State mgmt │   │
        │                  │         └──────┬───────┘   │
        │                  │                │            │
        └──────────────────┼────────────────┘            │
                           │                             │
                           ▼                             │
                  ┌──────────────────┐                  │
                  │   trigger_bus.py │                  │
                  │ ┌──────────────┐ │                  │
                  │ │ Priority     │ │                  │
                  │ │ Queue        │ │                  │
                  │ └──────────────┘ │                  │
                  │ • Anti-spam      │                  │
                  │ • Cooldown       │                  │
                  │ • Busy flag      │                  │
                  └────────┬─────────┘                  │
                           │                             │
                           ▼                             │
                  ┌──────────────────┐                  │
                  │ Scenario Engine  │                  │
                  │ • Parse steps    │                  │
                  │ • Execute cmds   │                  │
                  └────────┬─────────┘                  │
                           │                             │
                           ▼                             │
                  ┌──────────────────┐                  │
                  │  adafruit_hid    │                  │
                  │ • Keyboard       │                  │
                  │ • Layout (US)    │                  │
                  │ • Keycodes       │                  │
                  └────────┬─────────┘                  │
                           │                             │
                           ▼                             ▼
                  ┌──────────────────┐         ┌────────────────┐
                  │   USB HID        │         │ OLED Feedback  │
                  │   Interface      │         │ • Animations   │
                  │                  │         │ • Screensavers │
                  └──────────────────┘         └────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   HOST SYSTEM    │
                  │  (Any OS with    │
                  │   USB support)   │
                  └──────────────────┘
```

---

## Core Components

### 1. Main Loop (`code.py`)

**Purpose**: System initialization and event processing loop

**Responsibilities**:
- Initialize all subsystems in correct order
- Process encoder events via callback
- Update passive sensors
- Manage display sleep/wake cycles
- Handle screensaver timing

**Boot Sequence**:
```python
1. config.load()           # Parse config.json and state.json
2. trigger_bus.init()      # Initialize HID keyboard (MUST be before fire())
3. DisplayManager()        # Initialize OLED display
4. PassiveHandler()        # Setup Hall sensors and button
5. EncoderHandler()        # Setup rotary encoder
6. Main loop starts        # Enter event processing loop
```

**Main Loop Logic**:
```
while True:
    passive.update()       # Poll Hall sensors and button (10ms cycle)
    encoder.update()       # Poll encoder, call callback on events
    
    # Screen timeout check
    if (now - last_interaction) > timeout:
        if screensaver_enabled:
            display.start_screensaver()
            screensaver.update()  # 20 FPS animation
        else:
            display.sleep()
    
    sleep(10ms)            # 100 Hz polling rate
```

### 2. Configuration System (`config.py`)

**Purpose**: Centralized configuration and state management

**Files**:
- `config.json` — Static configuration (menu structure, scenarios, hardware pins)
- `state.json` — Runtime state (menu cursor position, sequence indices)

**API**:
```python
config.load()                # Load config.json and state.json
config.get_config()          # Returns immutable config dict
config.get_state()           # Returns mutable state dict
config.save_state()          # Persist state.json to disk
```

**Config Structure**:
```json
{
  "hardware": {
    "encoder_clk": 6,
    "hall_sensors": [...]
  },
  "device": {
    "armed": true,
    "cooldown_ms": 5000
  },
  "passive": {
    "hall_sensor_1": "scenario_name"
  },
  "active_menu": [...],
  "scenarios": {
    "scenario_name": [...]
  }
}
```

**State Structure**:
```json
{
  "menu_cursor": 0,
  "seq_positions": {
    "menu_item_id": 2
  }
}
```

### 3. Trigger Bus (`trigger_bus.py`)

**Purpose**: Central execution hub with anti-conflict protection

**Key Features**:
- **Single Execution Point** — All scenarios go through one bottleneck
- **Priority System** — Emergency triggers bypass normal rules
- **Cooldown Protection** — Prevents accidental double-execution
- **Busy Flag** — Rejects triggers during scenario execution

**Priority Levels**:
```python
PRIORITY_LOW    = 0  # Reserved for future use
PRIORITY_NORMAL = 1  # Menu actions, button
PRIORITY_HIGH   = 2  # Hall sensors (emergency) - bypasses cooldown
```

**API**:
```python
# Initialize HID keyboard (MUST call before fire())
trigger_bus.init()

# Fire passive trigger (Hall sensor, button)
trigger_bus.fire(trigger_name, priority=PRIORITY_NORMAL)

# Fire active menu item sequence
trigger_bus.fire_active(item_id)

# Check execution state
trigger_bus.is_busy()

# Get next action name for display (non-destructive)
trigger_bus.get_next_action_name(item_id)
```

**Conflict Resolution**:
```python
def _can_fire(priority):
    if _busy:
        return False  # Reject: scenario already running
    
    if priority < PRIORITY_HIGH and now < _cooldown_until:
        return False  # Reject: cooldown active (unless emergency)
    
    return True
```

### 4. Display Manager (`display.py`)

**Purpose**: OLED display driver with animations and screensavers

**Features**:
- 128×32 SSD1306 OLED via I2C
- Swipe animations for menu transitions
- Screensaver support (Tesseract, Starfield, Matrix)
- Auto-refresh management for flicker-free animations

**Display Layout**:
```
┌────────────────────────────────┐
│  y=4  │ < MENU >               │  Header line
│  y=16 │ Current Item Label     │  Main content (center)
│  y=27 │ -> Next Action         │  Footer line
└────────────────────────────────┘
```

**API**:
```python
display.draw_menu(label, action_hint)
display.show_executing(label, action)
display.show_status(line1, line2, line3)
display.animate_swipe(old_label, new_label, direction)

display.start_screensaver(name)
display.update_screensaver()
display.stop_screensaver()

display.sleep()
display.wake()
```

### 5. Encoder Handler (`encoder.py`)

**Purpose**: Rotary encoder input processing with debouncing

**Hardware**: KY-040 rotary encoder (CLK, DT, SW pins)

**Events**:
```python
EV_ROTATE_LEFT   # Counter-clockwise rotation
EV_ROTATE_RIGHT  # Clockwise rotation
EV_PRESS         # Short click (<1s)
EV_LONG_PRESS    # Long hold (≥1s)
```

**Internal Logic**:
```python
# Hardware-debounced rotation via rotaryio
encoder.position → delta → emit EV_ROTATE_* (steps)

# Software-debounced button
SW pin → debounce (50ms) → held duration check → emit EV_PRESS or EV_LONG_PRESS
```

**Callback Pattern**:
```python
def on_encoder_event(event):
    if event == EV_ROTATE_RIGHT:
        menu_cursor = (menu_cursor + 1) % len(menu)
        display.animate_swipe(old, new, "right")
    elif event == EV_PRESS:
        trigger_bus.fire_active(current_item_id)

encoder.set_callback(on_encoder_event)
```

### 6. Passive Handler (`passive.py`)

**Purpose**: Hall sensors and button monitoring with debouncing

**Inputs**:
- Hall sensors (active-low or active-high)
- Boot button double-click detection

**Anti-Bounce Logic**:
```python
# Debounce timing
if (now - last_change_time) < debounce_ms:
    return  # Ignore noise
    
# State change confirmed
if new_state != old_state:
    trigger_bus.fire(trigger_name, PRIORITY_HIGH)
```

**Double-Click Detection**:
```python
# Button click within time window
if (now - last_click) < double_click_window:
    trigger_bus.fire("btn_double", PRIORITY_NORMAL)
```

---

## Trigger System

### Trigger Types

**Passive Triggers** (asynchronous, hardware-driven):
- Hall sensor activation
- Button double-click

**Active Triggers** (synchronous, user-driven):
- Encoder click on menu item
- Menu item sequences (toggle between scenarios)

### Execution Guarantees

1. **At-Most-Once** — Cooldown prevents double execution
2. **Non-Reentrant** — Busy flag rejects overlapping triggers
3. **Priority Override** — High-priority triggers bypass cooldown
4. **USB Detection** — Scenarios skip execution if USB disconnected

### Cooldown Mechanics

```python
# After scenario completes
_cooldown_until = now + cooldown_ms / 1000.0

# Future trigger attempts
if priority < PRIORITY_HIGH and now < _cooldown_until:
    print("DROP — cooldown active")
    return False
```

**Purpose**: Prevent accidental multi-execution from:
- Encoder bounce
- Rapid clicks
- Sensor oscillation

**Exception**: Emergency triggers (Hall sensors) bypass cooldown for safety.

---

## Execution Flow

### Active Menu Item Execution

```
User rotates encoder
    └─> encoder.update() detects position change
        └─> on_encoder_event(EV_ROTATE_RIGHT)
            └─> menu_cursor = (cursor + 1) % len(menu)
                └─> display.animate_swipe(old, new, "right")
                    └─> save_cursor()

User clicks encoder
    └─> encoder.update() detects button press
        └─> on_encoder_event(EV_PRESS)
            └─> item = current_menu_list[menu_cursor]
                └─> Has sequence?
                    YES: trigger_bus.fire_active(item_id)
                         └─> Load seq_positions[item_id]
                             └─> Get current scenario from sequence
                                 └─> _run_scenario(scenario_name)
                                     └─> Execute steps sequentially
                                         └─> HID keyboard commands
                                     └─> Advance sequence position
                                         └─> save_state()
                    NO:  Enter submenu (if exists)
```

### Passive Trigger Execution

```
Hall sensor activates
    └─> passive.update() detects state change
        └─> Debounce check passes
            └─> trigger_bus.fire("hall_sensor_1", PRIORITY_HIGH)
                └─> Check _can_fire(PRIORITY_HIGH)
                    └─> Bypass cooldown (emergency priority)
                        └─> Load scenario from config.passive["hall_sensor_1"]
                            └─> _run_scenario(scenario_name)
                                └─> Execute steps sequentially
                                    └─> HID keyboard commands
                                └─> Apply cooldown (future normal triggers)
```

### Scenario Step Execution

```python
for step in scenario_steps:
    action = step["action"]
    
    if action == "key":
        keys = parse_combo(step["combo"])  # "ctrl+c" → [Keycode.CONTROL, Keycode.C]
        keyboard.press(*keys)
        keyboard.release_all()
    
    elif action == "type":
        layout.write(step["value"])  # Types string character by character
    
    elif action == "wait":
        time.sleep(step["ms"] / 1000.0)
    
    elif action == "enter":
        for _ in range(step["count"]):
            keyboard.press(Keycode.ENTER)
            keyboard.release_all()
            time.sleep(0.05)  # 50ms between repeats
```

---

## Module Reference

### `code.py` — Main Application

**Global State**:
- `root_menu` — Immutable reference to top-level menu
- `current_menu_list` — Currently displayed menu level
- `menu_cursor` — Current selection index
- `menu_stack` — Navigation history for back navigation
- `last_interaction_time` — Timestamp for screen timeout
- `screen_sleeping` — Display sleep state flag
- `screensaver_active` — Screensaver running flag

**Functions**:
- `get_current_label()` — Returns label of selected item
- `get_current_action()` — Returns next action name in sequence
- `refresh_menu()` — Redraws display without animation
- `save_cursor()` — Persists menu position to state.json
- `wake_up_display()` — Exits sleep/screensaver, shows menu
- `on_encoder_event(event)` — Main event handler callback

### `trigger_bus.py` — Execution Bus

**Module State**:
- `_kbd` — Keyboard HID device
- `_layout` — KeyboardLayoutUS instance
- `_key_map` — String to Keycode mapping dict
- `_busy` — Execution lock flag
- `_cooldown_until` — Timestamp when cooldown expires

**Public Functions**:
- `init()` — Initialize HID devices
- `fire(trigger_name, priority)` — Execute passive trigger
- `fire_active(item_id)` — Execute menu item sequence
- `is_busy()` — Check if scenario running
- `get_next_action_name(item_id)` — Preview next action

**Internal Functions**:
- `_find_item(menu, item_id)` — Recursive menu search
- `_can_fire(priority)` — Anti-conflict checks
- `_apply_cooldown()` — Set cooldown timer
- `_run_scenario(name)` — Execute scenario steps
- `_build_key_map()` — Generate string→keycode mapping
- `_parse_combo(combo_str)` — Parse "ctrl+c" to keycodes

### `display.py` — Display Driver

**Constants**:
- `_W = 128` — Display width
- `_H = 32` — Display height
- `_ADDR = 0x3C` — I2C address

**Instance Variables**:
- `_disp` — SSD1306 display object
- `_main_group` — Primary display group (menu)
- `_anim_group` — Animation display group (swipe)
- `_screensaver_group` — Screensaver display group
- `_lbl_top`, `_lbl_center`, `_lbl_bottom` — Label objects
- `_screensaver_manager` — Active screensaver instance

**Methods**:
- `draw_menu()` — Display menu state
- `show_executing()` — Display execution feedback
- `show_status()` — Display 3-line status message
- `animate_swipe()` — 6-frame horizontal slide animation
- `start_screensaver()` — Initialize and display screensaver
- `update_screensaver()` — Render next frame (20 FPS)
- `stop_screensaver()` — Exit screensaver, restore menu
- `sleep()` — Turn off display
- `wake()` — Turn on display

### `encoder.py` — Encoder Driver

**Instance Variables**:
- `_enc` — rotaryio.IncrementalEncoder (hardware-debounced)
- `_last_pos` — Previous encoder position
- `_sw` — DigitalInOut (switch pin)
- `_sw_last_raw` — Raw switch state
- `_sw_stable` — Debounced switch state
- `_sw_deb_t` — Debounce timer
- `_sw_press_t` — Press start timestamp
- `_sw_held` — Long press detection flag
- `_callback` — Event handler function

**Methods**:
- `set_callback(cb)` — Register event handler
- `update()` — Poll encoder state (call every loop)
- `_emit(event)` — Internal: invoke callback
- `_process_rotation()` — Internal: detect rotation
- `_process_button(now)` — Internal: debounce button, detect press type

### `passive.py` — Passive Sensors

**Instance Variables**:
- `_hall_sensors` — List of Hall sensor DigitalInOut objects
- `_button` — Button DigitalInOut object
- `_led` — Status LED DigitalInOut object
- `_armed` — Enable/disable Hall sensor triggers
- `_debounce_ms` — Anti-bounce delay
- `_last_hall_states` — Previous Hall sensor readings
- `_last_hall_times` — Debounce timestamps
- `_btn_last_click` — Last button click timestamp

**Methods**:
- `update()` — Poll sensors (call every loop)
- `startup_blink()` — LED feedback on boot
- `_check_hall_sensors()` — Internal: poll and debounce Hall sensors
- `_check_button()` — Internal: double-click detection

### `config.py` — Configuration Loader

**Module State**:
- `_config_data` — Parsed config.json dict
- `_state_data` — Parsed state.json dict

**Functions**:
- `load()` — Load config.json and state.json from disk
- `get_config()` — Return config dict (read-only)
- `get_state()` — Return state dict (read-write)
- `save_state()` — Persist state dict to state.json

### `screensaver.py` — Screensaver Effects

**Class**: `ScreensaverManager`

**Supported Effects**:
- `tesseract` — 4D hypercube rotation
- `starfield` — 3D star movement with perspective
- `matrix` — Matrix-style falling characters

**Methods**:
- `__init__(bitmap, name)` — Initialize screensaver
- `draw_frame()` — Render next animation frame

---

## Extension Possibilities

### Adding New Input Types

**Example**: Adding a new sensor type

1. Create handler module (e.g., `gyro.py`)
2. Initialize in `code.py` boot sequence
3. Poll in main loop: `gyro.update()`
4. Fire triggers via bus: `trigger_bus.fire("gyro_tilt", priority)`
5. Add trigger binding in `config.json` → `passive` section

**Integration Pattern**:
```python
# gyro.py
class GyroHandler:
    def __init__(self):
        # Initialize hardware
        pass
    
    def update(self):
        if self._detect_tilt():
            trigger_bus.fire("gyro_tilt", PRIORITY_NORMAL)

# code.py
gyro = GyroHandler()

while True:
    gyro.update()
    # ... rest of loop
```

### Adding New Action Types

**Example**: Adding mouse movement

1. Import `adafruit_hid.mouse` in `trigger_bus.py`
2. Initialize mouse device: `_mouse = Mouse(usb_hid.devices)`
3. Add action parser in `_run_scenario()`:
```python
elif action == "mouse_move":
    dx = step.get("x", 0)
    dy = step.get("y", 0)
    _mouse.move(dx, dy)
```
4. Use in scenarios:
```json
"scenario_mouse_test": [
    {"action": "mouse_move", "x": 100, "y": 50},
    {"action": "wait", "ms": 100}
]
```

### Adding Network Features

**Potential**: Remote trigger via WiFi (requires Pico W)

1. Configure WiFi in `settings.toml`
2. Add network module (e.g., `network.py`)
3. Listen for HTTP/MQTT triggers
4. Fire scenarios via trigger bus

**Example Architecture**:
```python
# network.py (pseudo-code)
import wifi
import socketpool

def listen_for_triggers():
    while True:
        request = socket.accept()
        scenario = parse_request(request)
        trigger_bus.fire_scenario(scenario)
```

### Custom Display Modes

**Example**: Status dashboard mode

1. Add mode flag in `config.json` → `device.display_mode`
2. Create dashboard renderer in `display.py`
3. Switch modes based on long-press or sensor

**Dashboard Elements**:
- System uptime
- Trigger count statistics
- Last executed scenario
- USB connection status

### Macro Recording

**Concept**: Record keystrokes and save as scenario

1. Add recording mode trigger
2. Capture HID input via serial monitor
3. Convert to scenario JSON format
4. Save to `config.json` or separate file

### Multi-Device Sync

**Concept**: Share configurations across multiple Pico Commanders

1. Export `config.json` to SD card or network
2. Import on other devices
3. Maintain device-specific hardware pins in separate file

---

## Performance Considerations

### Timing Constraints

| Operation | Target | Actual | Notes |
|-----------|--------|--------|-------|
| Main loop cycle | 10ms | ~10ms | 100 Hz polling rate |
| Encoder debounce | 50ms | 50ms | Software timing |
| Hall debounce | 300ms | User config | Prevents oscillation |
| Display refresh | 50ms | ~40ms | SSD1306 I2C transfer |
| Scenario step | Varies | <1ms per step | Except wait actions |
| Screensaver frame | 50ms | 50ms | 20 FPS target |

### Memory Usage

Typical runtime memory footprint:
- **Code**: ~30KB (Python bytecode)
- **Libraries**: ~45KB (mpy files)
- **Config**: ~5-20KB (depends on menu size)
- **Display buffers**: ~2KB (128×32 bitmap + labels)
- **Free RAM**: ~100KB available for future features

### Optimization Tips

1. **Use .mpy files** — Precompiled libraries save RAM
2. **Minimize string allocations** — Reuse label objects in display
3. **Limit scenario complexity** — Long scenarios block input processing
4. **Avoid deep menu nesting** — Stack depth limited by RAM

---

## Error Handling

### Hardware Failures

**OLED Display**:
- If init fails, system continues without display
- Graceful degradation: no visual feedback, but commands still work

**Encoder**:
- If pins not responding, no events emitted
- System remains responsive to Hall sensors and code reloads

**Hall Sensors**:
- Pin read failures are silent
- Misconfigured active_low just inverts behavior

### Configuration Errors

**Invalid JSON**:
- Boot fails with error in serial console
- Fix config.json and reload code

**Missing Scenarios**:
- Trigger fires, but scenario not found → logged, no crash
- Display shows "Executing..." but nothing happens

**Invalid Keycodes**:
- Unknown key in combo → ignored, rest of combo executes
- Logged to serial: `[bus] unknown key: xyz`

### USB Disconnection

- Scenario execution checks `supervisor.runtime.usb_connected`
- If disconnected, scenario skips silently
- No keyboard output, no errors

---

## Debugging

### Serial Console

Connect to Pico's serial port to view debug output:

```bash
# Linux
screen /dev/ttyACM0 115200

# macOS
screen /dev/cu.usbmodem* 115200

# Windows
# Use PuTTY or TeraTerm
```

**Log Messages**:
```
[main] active_menu: 8 items
[bus] keyboard OK
[display] init OK  SDA=GP 4  SCL=GP 5
[encoder] init OK  CLK=GP 6  DT=GP 7  SW=GP 8
[passive] init OK  Hall sensors: 2
[main] Ready!

[bus] → scenario_nextcloud_stop
[bus] ✓ scenario_nextcloud_stop

[bus] DROP — cooldown 4.3 s
```

### Common Issues

**Scenarios don't execute**:
1. Check `trigger_bus.init()` called before any `fire()`
2. Verify USB connected: `supervisor.runtime.usb_connected`
3. Check cooldown not active: wait 5 seconds between triggers
4. Verify scenario exists in `config.json`

**Menu doesn't scroll**:
1. Check encoder wiring: CLK/DT pins correct
2. Swap CLK/DT if direction inverted
3. Adjust `divisor=4` in `encoder.py` if skipping items

**Display blank**:
1. Check I2C wiring: SDA/SCL pins
2. Verify I2C address: `0x3C` (most common) or `0x3D`
3. Check power: 3.3V to VCC

---

## Contributing Guidelines

### Code Style

- **PEP 8** compliance for Python code
- **Docstrings** for public functions
- **Type hints** optional but encouraged
- **Comments** for non-obvious logic

### Testing

Before submitting changes:
1. Test on actual hardware (not just simulation)
2. Verify all menu navigation paths
3. Test passive triggers (Hall sensors, button)
4. Check USB HID output in text editor
5. Verify state persistence across reboots

### Documentation

Update docs when adding:
- New configuration options
- New action types
- New hardware support
- API changes

---

## License

This project is licensed under the MIT License. See [LICENSE](../../LICENSE) file.

---

## Further Reading

- [CircuitPython Documentation](https://docs.circuitpython.org/)
- [Adafruit HID Library Guide](https://learn.adafruit.com/circuitpython-essentials/circuitpython-hid-keyboard-and-mouse)
- [USB HID Specification](https://www.usb.org/hid)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
