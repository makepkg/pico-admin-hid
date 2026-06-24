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
- [Known Limitations](#known-limitations)
- [Performance Considerations](#performance-considerations)
- [Error Handling](#error-handling)
- [Debugging](#debugging)
- [Contributing Guidelines](#contributing-guidelines)
- [License](#license)

---

## System Overview

Pico Commander is a **trigger-pipeline sequencer** that translates physical inputs (encoder, sensors, button) into USB HID keyboard commands and GPIO control signals. The system operates as a **USB HID device** without requiring drivers on the host system.

### Core Concepts

1. **Input → Pipeline → Output Model** — Hardware inputs trigger pipelines; pipelines route steps to appropriate outputs (HID, GPIO)
2. **Typed I/O Modules** — Extensible input handlers (Hall, power monitor) and output handlers (HID keyboard, GPIO)
3. **Unified Pipeline Engine** — Both menu triggers and sensor triggers use the same execution engine
4. **Priority System** — Emergency triggers bypass cooldown and queues
5. **State Persistence** — Menu position and pipeline states survive reboots

### Design Philosophy

- **Automation Skeleton** — Not a framework you configure around; a small runtime with swappable I/O modules
- **Single Responsibility** — Each input/output type is an isolated handler class
- **Fail-Safe** — Hardware errors don't crash the system
- **Deterministic** — Same inputs produce same outputs every time
- **Extensible** — New input/output types integrate via simple contracts (see [inputs.md](inputs.md) and [outputs.md](outputs.md))

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         HARDWARE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  Rotary Encoder  │  Hall Sensors  │  Button  │  OLED Display   │
│    (GP6,7,8)     │   (GP15,16)    │  (GP24)  │   (GP4,5 I2C)   │
│                  │  INA226 Power  │          │                  │
│                  │  Monitor (I2C) │          │                  │
└────────┬─────────┴────────┬────────┴─────┬────┴─────────┬───────┘
         │                  │              │              │
         ▼                  ▼              ▼              ▼
┌────────────────┐  ┌───────────────────────────┐  ┌──────────┐
│ encoder.py     │  │ inputs_manager.py         │  │ display  │
│ • Rotation     │  │ • HallSensorInput         │  │ manager  │
│ • Click        │  │ • PowerMonitorInput       │  └────┬─────┘
│ • Long press   │  │ • Button dbl-clk          │       │
└───────┬────────┘  └──────┬────────────────────┘       │
        │                  │                            │
        │                  │                            ▼
        │                  │                  ┌──────────────────┐
        │                  │                  │  config.py       │
        │                  │                  │ • JSON parse     │
        │                  │                  │ • State mgmt     │
        │                  │                  │ • inputs{}       │
        │                  │                  │ • outputs{}      │
        │                  │                  └──────┬───────────┘
        │                  │                         │
        └──────────────────┼─────────────────────────┘
                           │
                           ▼
                  ┌────────────────────────┐
                  │   trigger_bus.py       │
                  │                        │
                  │  Pipeline Engine:      │
                  │ ┌────────────────────┐ │
                  │ │ execute_pipeline() │ │
                  │ │ • loop: true/false │ │
                  │ │ • Priority queue   │ │
                  │ │ • Busy flag        │ │
                  │ │ • Cooldown         │ │
                  │ └────────────────────┘ │
                  │                        │
                  │  OutputsManager:       │
                  │ ┌────────────────────┐ │
                  │ │ Route by output="" │ │
                  │ └───────┬────────────┘ │
                  └─────────┼──────────────┘
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
    ┌────────────────┐           ┌───────────────────┐
    │ output_hid.py  │           │ output_gpio.py    │
    │ • type         │           │ • gpio_pulse      │
    │ • key          │           │ • gpio_set        │
    │ • enter        │           │ • gpio_hold       │
    │ • wait         │           │ • active_high     │
    └────────┬───────┘           └────────┬──────────┘
             │                            │
             ▼                            ▼
    ┌────────────────┐           ┌──────────────┐
    │ adafruit_hid   │           │ digitalio    │
    │ • Keyboard     │           │ GPIO pins    │
    │ • Layout (US)  │           └──────┬───────┘
    │ • Keycodes     │                  │
    └────────┬───────┘                  │
             │                          │
             ▼                          ▼
    ┌────────────────┐         ┌──────────────────┐
    │   USB HID      │         │ GPIO Output      │
    │   Interface    │         │ Relay/Opto/Power │
    └────────┬───────┘         └──────────────────┘
             │
             ▼
    ┌────────────────┐
    │   HOST SYSTEM  │
    │  (Any OS with  │
    │   USB support) │
    └────────────────┘
```

---

## Core Components

### 1. Main Loop (`code.py`)

**Purpose**: System initialization and event processing loop

**Responsibilities**:
- Initialize all subsystems in correct order
- Process encoder events via callback
- Update sensors via InputsManager
- Manage display sleep/wake cycles
- Handle screensaver and warning overlays

**Boot Sequence**:
```python
1. config.load()           # Parse config.json and state.json
2. trigger_bus.init()      # Initialize HID keyboard (MUST be before fire())
3. display                 # Initialize OLED display
4. inputs_manager          # Setup Hall sensors, INA226, button
5. encoder                 # Setup rotary encoder callback
6. warning_screen / splash_screen # Setup overlays
7. auto_boot setup         # Check for auto_boot outputs
8. Main loop starts        # Enter event processing loop
```

**Main Loop Logic**:
```python
while True:
    inputs.update()        # Poll sensors and button
    encoder.update()       # Poll encoder, call callback on events
    
    # Screen timeout check
    if (now - last_interaction) > timeout:
        if screensaver_enabled:
            display.start_screensaver()
            screensaver.update()
        else:
            display.sleep()
            
    # Handle overlays and auto_boot cycles...
    
    sleep(10ms)            # 100 Hz polling rate
```

### 2. Configuration System (`config.py`)

**Purpose**: Centralized configuration and state management

**Files**:
- `config.json` — Static configuration (menu structure, scenarios, hardware pins, inputs, outputs)
- `state.json` — Runtime state (menu cursor position, sequence/pipeline indices)

**API**:
```python
config.load()                # Load config.json and state.json
config.get_config()          # Returns immutable config dict
config.get_state()           # Returns mutable state dict
config.save_state()          # Persist state.json to disk
```

### 3. Trigger Bus (`trigger_bus.py`)

**Purpose**: Central execution hub with unified pipeline engine and output routing.

**Key Features**:
- **Single Execution Point** — All scenarios go through `execute_pipeline()`.
- **Outputs Manager** — Routes scenario steps to the correct output handler (e.g., HID, GPIO) based on `step["output"]`.
- **Priority System** — Emergency triggers bypass normal rules.
- **Cooldown Protection** — Prevents accidental double-execution.
- **Busy Flag** — Rejects triggers during scenario execution.

**Priority Levels**:
```python
PRIORITY_LOW    = 0  # Reserved for future use
PRIORITY_NORMAL = 1  # Menu actions, button
PRIORITY_HIGH   = 2  # Hall sensors (emergency) - bypasses cooldown
```

### 4. Input Manager (`inputs_manager.py`)

**Purpose**: Unified manager for all input sensors.

**Inputs Supported**:
- `HallSensorInput`: Hall effect sensors (active-low or active-high) for emergency triggers.
- `PowerMonitorInput`: INA226 I2C battery voltage/current monitor, triggers on low battery thresholds.
- **Button**: Boot button double-click detection.

**Logic**:
- Reads from `config["inputs"]` and dynamically creates appropriate handlers.
- Implements anti-bounce logic for mechanical inputs.
- Emits triggers via `trigger_bus.fire()`.

### 5. Outputs Manager & Handlers (`trigger_bus.py` + `output_*.py`)

**Purpose**: Extensible system for executing scenario steps across different hardware.

**Outputs Supported**:
- `HidOutput` (`output_hid.py`): USB keyboard commands (`key`, `type`, `wait`, `enter`).
- `GpioOutput` (`output_gpio.py`): Digital pin control (`gpio_pulse`, `gpio_set`, `gpio_hold`).

**Logic**:
- Managed by `OutputsManager` inside `trigger_bus.py`.
- Resolves target via `step.get("output", "hid")`.
- Dispatches execution to the respective `OutputHandler.execute(action)`.

### 6. Display Manager (`display.py`)

**Purpose**: OLED display driver with animations and screensavers.

**Features**:
- 128×32 SSD1306 OLED via I2C.
- Swipe animations for menu transitions.
- Screensaver support.

### 7. Encoder Handler (`encoder.py`)

**Purpose**: Rotary encoder input processing with debouncing.

**Hardware**: KY-040 rotary encoder (CLK, DT, SW pins).

### 8. INA226 Power Monitor (`ina226_monitor.py`)

**Purpose**: I2C battery voltage and current monitoring with graceful degradation.

### 9. Warning & Splash Screens (`warning_screen.py`, `splash_screen.py`)

**Purpose**: Overlays for battery status and warnings.

---

## Trigger System

### Trigger Types

**Passive Triggers** (asynchronous, hardware-driven):
- Hall sensor activation
- Button double-click
- INA226 low battery threshold

**Active Triggers** (synchronous, user-driven):
- Encoder click on menu item

### Execution Guarantees

1. **At-Most-Once** — Cooldown prevents double execution.
2. **Non-Reentrant** — Busy flag rejects overlapping triggers.
3. **Priority Override** — High-priority triggers bypass cooldown.
4. **Resilient Steps** — A single failed step (e.g., USB not connected for HID) logs a warning but DOES NOT halt the remaining scenario steps.

---

## Execution Flow

### Unified Pipeline Engine

Both active and passive triggers use the same engine: `execute_pipeline(pipeline_config, trigger_id, priority)`.

`fire()` (passive) and `fire_active()` (menu) act as thin facades that convert their configuration into a standardized `pipeline_config` and pass it to `execute_pipeline()`.

**Pipeline Semantics (`loop: true` vs `loop: false`)**:
- `loop: false`: Executes the entire chain of scenarios sequentially in one go, without tracking position.
- `loop: true`: Executes exactly one scenario per trigger event, advancing a pointer in `state.json["trigger_positions"]` so the next trigger runs the next scenario in the cycle.

**Backward Compatibility**:
`fire_active()` still supports the old `"sequence"` format by resolving it into a `loop: true` pipeline using `_resolve_seq_entry()`.

### Step Resolution & Execution

```python
# Inside _run_scenario(name):
for step in scenario_steps:
    output_name = step.get("output", "hid")  # Default to 'hid' for legacy support
    
    # OutputsManager.execute() routes to the specific handler
    success = _outputs_manager.execute(output_name, step)
    
    if not success:
        print(f"[bus] WARNING: step failed for output '{output_name}'")
        # Execution CONTINUES for the next step despite failure
```

---

## Module Reference

### `code.py` — Main Application
- `root_menu`, `current_menu_list`, `menu_cursor`, `menu_stack`
- Initializer for all components.
- Main loop polling `inputs.update()` and `encoder.update()`.

### `trigger_bus.py` — Execution Bus
- `init()` — Initializes `OutputsManager`.
- `execute_pipeline(pipeline_config, trigger_id, priority)` — Core execution logic.
- `fire(trigger_name, priority)` — Passive trigger facade.
- `fire_active(item_id)` — Active trigger facade.
- `_outputs_manager` — Instance of `OutputsManager` for routing steps.

### `inputs_manager.py` — Input Manager
- `InputsManager`: Reads `config["inputs"]` and initializes handlers.
- `HallSensorInput`: Handles debounced Hall sensor reads.
- `PowerMonitorInput`: Manages INA226 polling and threshold checks.

### `output_base.py` — Output Contract
- `OutputHandler`: Base class defining `execute(action)` and `cleanup()`.

### `output_hid.py` — HID Output
- `HidOutput`: Executes `key`, `type`, `wait`, `enter` actions via USB HID.

### `output_gpio.py` — GPIO Output
- `GpioOutput`: Executes `gpio_pulse`, `gpio_set`, `gpio_hold` actions on hardware pins.

### `config.py` — Configuration Loader
- `load()`, `get_config()`, `get_state()`, `save_state()`.
- `_migrate_state()`: Migrates only legacy `seq_positions` for top-level menu items. `trigger_positions` does not require migration (uses `.get(key, 0)` with a default).

### `display.py` — Display Driver
- SSD1306 display object manager and animation handler.

### `encoder.py` — Encoder Driver
- Rotary encoder input processing and debouncing.

---

## Extension Possibilities

### Adding New Input Types
Adding a new sensor or input mechanism requires implementing a handler class in `inputs_manager.py`.
See [Input System guide](inputs.md) for the full walkthrough.

### Adding New Action Types
Adding a new output capability (e.g., networking, I2C commands) involves creating a new class inheriting from `OutputHandler`.
See [Output System guide](outputs.md) for the full walkthrough.

### Adding Network Features
**Potential**: Remote trigger via WiFi (requires Pico W).
1. Configure WiFi in `settings.toml`.
2. Add network module listening for HTTP/MQTT triggers.
3. Fire scenarios via `trigger_bus`.

### Custom Display Modes
**Potential**: Status dashboard mode displaying system uptime, trigger counts, or USB connection status.

### Macro Recording
**Potential**: Record keystrokes and save as a scenario to `config.json`.

### Multi-Device Sync
**Potential**: Share configurations across multiple Pico Commanders by exporting/importing `config.json`.

---

## Known Limitations

- **Auto-Boot GPIO Limit**: The `auto_boot` feature supports only one GPIO output simultaneously. It picks the first output found with `auto_boot.enabled: true` and ignores the rest.
- **GPIO Set Asymmetry**: `gpio_set` in `output_gpio.py` intentionally works with the literal electrical level (`"value": "high"/"low"` directly on the pin), bypassing the `active_high` configuration. This is for raw/low-level pin control. Conversely, `gpio_pulse` and `gpio_hold` respect the `active_high` flag.
- **Config Studio Limitations**: The web UI (Config Studio / `editor.html`) currently does not allow assembling a pipeline with `loop: false` and multiple scenarios via the interface. It must be done through Raw JSON or manual editing of `config.json`, even though the pipeline engine fully supports it.

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

### Optimization Tips

1. **Use .mpy files** — Precompiled libraries save RAM.
2. **Minimize string allocations** — Reuse label objects in display.
3. **Limit scenario complexity** — Long scenarios block input processing.
4. **Avoid deep menu nesting** — Stack depth limited by RAM.

---

## Error Handling

### Hardware Failures

**OLED Display**:
- If init fails, system continues without display.

**Encoder**:
- If pins not responding, no events emitted. System remains responsive to other inputs.

### Configuration Errors

**Missing Scenarios**:
- Trigger fires, but scenario not found → logged, no crash.

**Invalid Action/Step**:
- Unknown key or failed action → logged (`[bus] WARNING: step failed...`), but the rest of the scenario continues to execute.

### USB Disconnection

- Scenario execution via `HidOutput` checks `supervisor.runtime.usb_connected`.
- If disconnected, the step skips silently without failing the whole scenario.

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
[outputs] Manager ready: 2 outputs loaded
[bus] Outputs manager OK
[display] init OK  SDA=GP 4  SCL=GP 5
[inputs] Hall hall_sensor_1 на GP15, active_low:True — начальное: PRESENT
[inputs] Manager OK, armed: True, inputs: 2
[main] Ready!

[bus] → scenario_nextcloud_stop
[output:hid] key: ctrl+c
[bus] ✓ scenario_nextcloud_stop

[bus] DROP — cooldown 4.3 s
```

---

## Contributing Guidelines

### Code Style

- **PEP 8** compliance for Python code
- **Docstrings** for public functions
- **Type hints** optional but encouraged
- **Comments** for non-obvious logic

### Testing

Before submitting changes:
1. Test on actual hardware (not just simulation).
2. Verify all menu navigation paths.
3. Test passive triggers (Hall sensors, INA226, button).
4. Check USB HID output in text editor.
5. Verify state persistence across reboots.

---

## License

This project is licensed under the MIT License. See [LICENSE](../../LICENSE) file.

---

## Further Reading

- [CircuitPython Documentation](https://docs.circuitpython.org/)
- [Adafruit HID Library Guide](https://learn.adafruit.com/circuitpython-essentials/circuitpython-hid-keyboard-and-mouse)
- [USB HID Specification](https://www.usb.org/hid)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
