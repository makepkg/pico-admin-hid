# Output System

Technical documentation for the output layer of Pico Commander.

---

## Overview

In the Pico Commander architecture, an **Output** is the final recipient of an action defined in a scenario. While triggers (inputs or menu clicks) initiate a pipeline, the pipeline consists of scenarios, and each scenario is a list of steps. 

Each step can specify an `"output"` key matching a name defined in `config["outputs"]`. If omitted, it defaults to `"hid"`. A single output module can serve any number of steps across different scenarios.

Currently, there are four built-in types of outputs:
1. `hid` — USB HID Keyboard commands (typing, shortcuts).
2. `gpio` — Digital pin control (relays, optocouplers, LEDs).
3. `mouse` — USB HID Mouse commands (movement, clicks).
4. `serial` — Raw or structured events over the second USB CDC (serial data) port, for a listener script on the host.

---

## The OutputHandler Contract

All output handlers must inherit from `OutputHandler` defined in `output_base.py`.

```python
class OutputHandler:
    def __init__(self, name, config):
        self.name = name
        self._config = config
        self._enabled = config.get("enabled", True)
        
    @property
    def enabled(self):
        return self._enabled
        
    def execute(self, action):
        raise NotImplementedError()
        
    def cleanup(self):
        pass
```

### Key Rules for Implementation
- **Initialization**: The `__init__` method receives the output's `name` and its specific `config` dictionary. It must save `self.name`, `self._config`, and `self._enabled`. If initialization fails (e.g., bad config or hardware missing), it should set `self._enabled = False` rather than crashing the system.
- **Execution**: The `execute(action)` method receives the **entire step dictionary** from the scenario (e.g., `{"output": "gpio1", "action": "gpio_pulse", "duration": 250}`). The handler is responsible for reading the keys it needs.
- **Error Handling**: `execute()` must return `True` on success and `False` on failure. It **MUST NOT** throw exceptions that bubble up. Catch errors internally, log them, and return `False`.
- **Cleanup**: The optional `cleanup()` method is called when the system shuts down or reloads. It should reset hardware to a safe state (e.g., release all keys, turn off relays).

---

## Built-in Output: HID (`output_hid.py`)

The HID output sends keystrokes to the connected host computer.

**Supported Actions**:
- `type`: Types a string of text (`value`).
- `key`: Presses a combination of keys (`combo`, e.g., `"ctrl+shift+esc"`).
- `wait`: Pauses execution (`ms`). *Note: It is generally preferred to use the shorthand `{"wait": 500}` directly in the scenario rather than routing it through the HID output.*
- `enter`: Presses the Enter key `count` times (clamped to 1-10).

**Key Modifiers and Mapping**:
Keys are mapped internally via `_build_key_map()`. Supported modifiers include `ctrl`, `alt`, `shift`, `super`/`win`. Regular keys include `a-z`, `0-9`, `f1-f12`, `enter`, `escape`/`esc`, `space`, `tab`, `backspace`, `delete`, and arrow keys (`up`, `down`, `left`, `right`).

**Lazy Initialization**:
To prevent boot delays or crashes when a USB host isn't connected, the `Keyboard` and `KeyboardLayoutUS` objects are not created in `__init__`. Instead, they are initialized upon the first call to `execute()`. If `supervisor.runtime.usb_connected` is false, the step is safely skipped and returns `False`.

**Safety**:
The `cleanup()` method calls `release_all()` to ensure no keys remain virtually "stuck" if the device resets during execution.

---

## Built-in Output: GPIO (`output_gpio.py`)

The GPIO output controls physical digital pins.

**Configuration**:
- `pin`: The GPIO pin number (required).
- `active_high`: Boolean (default `true`). Determines the physical electrical level considered "active".
- `label`: Human-readable name for logging.
- `enabled`: Boolean toggle.

### The `_drive()` Abstraction
Internally, `GpioOutput` uses a private method `_drive(active: bool)`. This translates a logical state ("ON" or "OFF") into the correct physical voltage level based on `active_high`.
- If `active_high=True`: `_drive(True)` sets pin HIGH.
- If `active_high=False`: `_drive(True)` sets pin LOW.

### Supported Actions

1. **`gpio_pulse`** (No parameters)
   - Calls `_drive(True)`, waits 250ms, then calls `_drive(False)`.
   - Simulates a button press. Respects `active_high`.
2. **`gpio_hold`** (`duration_ms`)
   - Calls `_drive(True)`, waits for `duration_ms`, then calls `_drive(False)`.
   - Respects `active_high`.
3. **`gpio_set`** (`value`: `"high"` / `"low"`)
   - **Important Asymmetry**: This action **intentionally bypasses** `_drive()` and `active_high`. It writes the literal electrical level directly to the pin. It exists as a raw, low-level control tool for driving basic components (like an LED) where the concept of "active state" might just add confusion.

### Initial and Safety States
Upon initialization, and during `cleanup()` or error fallbacks, the pin is set to the INACTIVE state using `_drive(False)`. This ensures that relays or optocouplers do not accidentally trigger on boot or crash.

### `default_scenario` Convention
You might see `default_scenario` in the `config.json` for GPIO outputs. This is **not** used by `output_gpio.py` itself. It is a UI convention used by Config Studio (`editor.html`) to auto-generate a convenient one-step scenario (e.g., `scenario_opto_pwr_pulse`) that can be easily referenced in pipelines or `auto_boot`.

---

## Built-in Output: Mouse (`output_mouse.py`)

USB HID Mouse commands — movement and clicks. Used for a trackball input, but can also be driven from any scenario like any other output.

### Configuration
```json
"outputs": {
  "mouse": {
    "type": "mouse",
    "enabled": true
  }
}
```

### Supported Actions
- `move`: relative movement via `dx`/`dy` pixel offsets.
- `click`: a full press+release on `button` (`left`/`right`/`middle`, defaults to `left`).
- `press`: presses `button` and holds it.
- `release`: releases `button`.

### Lazy Initialization and Safety
Same pattern as `HidOutput` — the `Mouse` object is created on first `execute()` call, not at `__init__`. If USB is not connected (`supervisor.runtime.usb_connected` is `False`), the action is skipped and logged. `cleanup()` calls `release_all()` to ensure no button is left held down on stop/reload.

### Direct-Call Pattern (Trackball Input)
Unlike scenario-driven outputs, `TrackballInput` (`inputs_manager.py`) calls `trigger_bus.execute_output("mouse", {...})` directly on every `update(now)` tick for movement, bypassing `fire()`/`fire_active()` entirely. This is intentional: a busy mouse-output call would otherwise block on the continuous movement stream from the same input if it went through the normal cooldown/priority queue. See `docs/developers/inputs.md` for the full explanation of this exception.

---

## Built-in Output: Serial (`output_serial.py`)

Sends events to a listener script on the host over the second USB CDC interface (`usb_cdc.data`), separate from the console/REPL port. This exists because HID typing depends on host focus, keyboard layout, and an application actually being ready to receive keystrokes — Serial is a plain data channel that works regardless of what's on screen on the host.

### Configuration
```json
"outputs": {
  "serial": {
    "type": "serial",
    "enabled": true,
    "label": "Host event channel"
  }
}
```

### Requires `boot.py` Setup
`usb_cdc.enable(console=True, data=True)` must be called in `boot.py`, before `usb_hid.enable(...)`. This creates a second CDC port (e.g. `/dev/ttyACM1` on Linux) separate from the console port used for logs and REPL. This only takes effect after a full USB replug — a soft-reload of `code.py` alone will not apply a `boot.py` change.

### Supported Actions
- `send`: writes a raw string with no trailing newline.
- `send_line`: writes a string followed by `\n`.
- `event`: writes a JSON object followed by `\n`. Always includes `"event"` (from the step's `name` field) and `"uptime"` (`time.monotonic()`, not wall-clock time — there is no RTC on the Pico). Any fields in the step's `data` object are merged in.

Example scenario:
```json
"scenario_notify_poweroff": [
  {"output": "serial", "action": "event", "name": "poweroff", "data": {"source": "menu"}}
]
```

### Safety / Non-Blocking Behavior
- `write_timeout` is set to `0` — writes never block the main loop, even if the host isn't reading.
- If the host isn't listening (`usb_cdc.data.connected` is `False`), the step is skipped and logged — same fail-safe pattern as `HidOutput`'s USB-not-connected check.
- There is no acknowledgment or delivery guarantee. This is a fire-and-forget channel, not a request/response protocol.

---

## OutputsManager (`trigger_bus.py`)

The `OutputsManager` class is the registry and dispatcher for all output handlers.

1. **Registration**: During boot (`trigger_bus.init()`), the manager reads `config["outputs"]`. It checks the `type` field of each entry and instantiates the corresponding class (`HidOutput` or `GpioOutput`). If a type is unknown, it logs a warning and skips it.
2. **Dispatching**: When a scenario step is executed, the engine calls `_outputs_manager.execute(output_name, step)`. The manager looks up the handler by name, verifies it is `enabled`, and calls its `execute(action)` method.
3. **Public API**: The bus exposes `trigger_bus.execute_output(name, action)` for direct execution outside of standard pipelines.

---

## `auto_boot` (Consumer of Outputs)

The `auto_boot` feature is a specialized routine in `code.py` that automatically triggers a server boot sequence if a USB connection is not detected.

**How it interacts with Outputs**:
It does not use the pipeline engine. Instead, it looks through `config["outputs"]` for the first GPIO output that has `auto_boot.enabled: true`. If the conditions are met, it directly calls:
```python
trigger_bus.execute_output(auto_boot_output_name, {"action": "gpio_pulse"})
```

*For full configuration details of `auto_boot`, see the [Configuration Guide](../user/configuration-guide.md).*

---

## How to Add a New Output Type

Adding a new output type requires a new handler class and registering it in the manager. Let's create a `PwmOutput` for controlling LED brightness or fan speed via `pwmio`.

### 1. Create the Handler Class (`output_pwm.py`)

```python
import pwmio
import board
from output_base import OutputHandler

class PwmOutput(OutputHandler):
    def __init__(self, name, config):
        super().__init__(name, config)
        
        pin_num = config.get("pin")
        if pin_num is None:
            print(f"[output:{name}] WARNING: pin not specified")
            self._enabled = False
            return
            
        try:
            pin_name = f"GP{pin_num}"
            self._pwm = pwmio.PWMOut(getattr(board, pin_name), frequency=1000, duty_cycle=0)
            print(f"[output:{name}] PWM ready on {pin_name}")
        except Exception as e:
            print(f"[output:{name}] ERROR initializing PWM:", e)
            self._enabled = False

    def execute(self, action):
        if not self.enabled:
            return False
            
        act = action.get("action")
        
        try:
            if act == "set_duty":
                # Expects 0 to 100 percentage
                percent = max(0, min(100, action.get("percent", 0)))
                # Convert 0-100 to 0-65535
                self._pwm.duty_cycle = int((percent / 100.0) * 65535)
                print(f"[output:{self.name}] Duty cycle set to {percent}%")
                return True
            else:
                print(f"[output:{self.name}] Unknown action: {act}")
                return False
        except Exception as e:
            print(f"[output:{self.name}] Error:", e)
            return False

    def cleanup(self):
        if self._enabled and hasattr(self, "_pwm"):
            self._pwm.duty_cycle = 0
```

### 2. Register in OutputsManager (`trigger_bus.py`)

Import your new module at the top of `trigger_bus.py`:
```python
from output_hid import HidOutput
from output_gpio import GpioOutput
from output_pwm import PwmOutput  # <--- Add this
```

Update the `OutputsManager.__init__` method:
```python
if output_type == "hid":
    self._outputs[name] = HidOutput(name, cfg_dict)
elif output_type == "gpio":
    self._outputs[name] = GpioOutput(name, cfg_dict)
elif output_type == "pwm":  # <--- Add this block
    self._outputs[name] = PwmOutput(name, cfg_dict)
```

### 3. Update `config.json`

Add the new output to the `outputs` dictionary:
```json
"outputs": {
  "case_fan": {
    "type": "pwm",
    "enabled": true,
    "pin": 17
  }
}
```

Use it in a scenario step:
```json
"scenario_fan_max": [
  {"output": "case_fan", "action": "set_duty", "percent": 100}
]
```

### 4. Config Studio UI Integration (Optional)
If you want users to be able to configure this output via the Web UI (`editor.html`):
1. Add `<option value="pwm">PWM Controller</option>` to the "Choose Output Type" modal.
2. Create a `renderPwmOutput(name, cfg)` function mirroring `renderGpioOutput()`, exposing the `pin` setting.

---

## Known Issues / Design Notes

- **`gpio_set` Asymmetry**: As mentioned, `gpio_set` intentionally ignores the `active_high` configuration and writes absolute electrical levels to the pin. This is a deliberate design choice for raw component control, not a bug. Do not "fix" this by wrapping it in `_drive()`.
- **`auto_boot` Limitation**: The `auto_boot` routine currently scans `config["outputs"]` and binds to the **first** GPIO output it finds with `auto_boot.enabled: true`. It does not support executing multiple auto-boot sequences simultaneously across different outputs.

---

## Related Documentation

- [System Architecture](architecture.md)
- [Input System Guide](inputs.md)
- [Pipeline Configuration Guide](../user/pipelines.md)
