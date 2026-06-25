# Input System

Technical documentation for the input layer of Pico Commander.

---

## Overview

In the Pico Commander architecture, an **Input** is a source of hardware events (sensors, buttons, power monitors) that eventually triggers a pipeline via `trigger_bus.fire(input_id, priority)`.

Inputs are registered and configured dynamically from the `config.json` → `inputs` section based on their `type`. 

Currently, there are two built-in typed inputs:
1. `hall` — Digital Hall-effect sensor (`HallSensorInput`).
2. `power_monitor` — INA226 battery monitor via I2C (`PowerMonitorInput`).

*Note: The physical boot button (`button_pin`) is handled directly inside `InputsManager._process_button()`. It is NOT implemented as a typed Input class. This asymmetry is intentional due to its dual-purpose nature (boot selection and double-click).*

---

## Input Classes (No Formal Base Class)

Unlike the output layer (which has a strict `OutputHandler` base class), the input layer **does not currently have a formal base class**. 

`HallSensorInput` and `PowerMonitorInput` are independent classes that share a duck-typed implicit contract. `InputsManager.update()` simply loops through all registered input objects and calls `.update(now)` on them.

### The Implicit Input Contract

To be compatible with `InputsManager`, a custom input class must implement:

1. **Constructor**: Must accept at least `input_id` and `config_dict`. It may accept other dependencies (like an `i2c` bus or global `debounce_ms`) if needed.
2. **`update(self, now: float)`**: This method is called on every iteration of the main loop (approx. 100 Hz). `now` is the current `time.monotonic()`.
3. **Trigger Execution**: The class is responsible for evaluating its own state and calling `trigger_bus.fire(self.input_id, priority)` directly when its trigger condition is met.

---

## Built-in Input: Hall Sensor (`HallSensorInput`)

The Hall sensor input is designed for magnetic proximity detection (e.g., a door opening or a case being removed).

**Configuration**:
- `pin`: The GPIO pin number (required).
- `active_low`: Boolean (default `true`). Determines whether a LOW signal means the magnet is present.

**Behavior**:
- **Debounce**: It uses a global `debounce_ms` (from `config["device"]["debounce_ms"]`) passed down from the manager. It requires the pin state to remain stable for this duration before acknowledging a state change.
- **Armed State**: It respects the global `config["device"]["armed"]` flag. If `armed` is false, state changes are detected and logged, but `trigger_bus.fire()` is skipped.
- **Trigger Condition**: It fires when the state transitions to **"magnet lost"** (i.e., the door opened). 
- **Priority**: Always uses `trigger_bus.PRIORITY_HIGH`. This ensures emergency shutdown scenarios execute immediately, bypassing any active cooldowns.

---

## Built-in Input: Power Monitor (`PowerMonitorInput`)

The power monitor uses the `INA226Monitor` wrapper to read voltage and current over I2C. The I2C communication is decoupled into `ina226_monitor.py`, while `PowerMonitorInput` handles the trigger logic.

**Configuration**:
- `trigger_mode`: `"percent"` or `"voltage"`.
- `threshold_percent` / `threshold_voltage`: The critical threshold where the trigger fires.
- `warning_offset_percent`: Adds an offset (e.g., +5%) to the threshold. When the battery enters this zone, a warning screen is displayed, but the trigger does not fire yet.
- `read_interval_sec`: Throttles I2C reads (e.g., only poll the sensor every 5 seconds).
- `recovery_offset_percent`: Additional % above threshold required before resuming normal monitoring after recovery. Prevents re-triggering immediately after the battery recovers.
- `trigger_attempts`: Maximum number of shutdown attempts before entering SUSPENDED state.
- `trigger_attempt_interval_sec`: Seconds between retry attempts when the server does not shut down.

**State Machine**:

`PowerMonitorInput` uses a four-state machine:

- `MONITORING`: Normal operation. If battery % drops to or below `threshold_percent` and USB is connected, transitions to TRIGGERED.
- `TRIGGERED`: Shutdown sequence active. Fires trigger on the bus, retries up to `trigger_attempts` times. If USB disconnects (server shut down) → SUSPENDED. If max attempts reached → SUSPENDED.
- `SUSPENDED`: Shutdown complete or max attempts exhausted. Auto-boot is blocked (`blocks_auto_boot = True`). Waits for USB to reconnect.
- `SUSPENDED_WAITING`: USB reconnected, waiting for battery to recover above `threshold_percent + recovery_offset_percent` before returning to MONITORING.

**USB Gate**: The trigger fires only if USB is connected (`usb=True`). If the server is already off, no trigger is sent.

**Boot behaviour**: On Pico startup, if battery % is already below threshold and USB is absent, the system starts directly in SUSPENDED — preventing auto-boot from attempting to start the server on a low battery.

**Priority**: Always uses `trigger_bus.PRIORITY_HIGH`.

---

## How to Add a New Input Type

Let's add a "PIR Motion Sensor" input. Since it's a simple digital pin, we can add it directly to `inputs_manager.py`. 

*(Heuristic: If your sensor requires complex bus logic like I2C/SPI, put the hardware logic in a separate file like `ina226_monitor.py`. If it's a simple GPIO read, you can write the class directly in `inputs_manager.py`.)*

### 1. Create the Input Class

In `inputs_manager.py`, add the class. We will use a debounce pattern similar to the Hall sensor.

```python
import time
import board
import digitalio
import trigger_bus

class MotionSensorInput:
    def __init__(self, input_id, config_dict, debounce_ms):
        self.input_id = input_id
        self.config = config_dict
        self.debounce_ms = debounce_ms
        
        pin_num = config_dict.get("pin")
        if pin_num is None:
            raise ValueError(f"Motion sensor {input_id}: pin not specified")
            
        # Setup pin (PIR usually outputs HIGH on motion)
        self.sensor = digitalio.DigitalInOut(getattr(board, f"GP{pin_num}"))
        self.sensor.direction = digitalio.Direction.INPUT
        
        self.stable = self.sensor.value
        self.last_raw = self.stable
        self.debounce_t = time.monotonic()
        self.triggered = False

    def update(self, now):
        current = self.sensor.value
        
        # Reset debounce timer if state fluctuates
        if current != self.last_raw:
            self.debounce_t = now
            self.last_raw = current
            
        # Wait for stability
        if (now - self.debounce_t) * 1000 < self.debounce_ms:
            return
            
        if current == self.stable:
            return
            
        self.stable = current
        
        # Fire trigger on rising edge (Motion Detected)
        if current:
            print(f"[inputs] {self.input_id} → Motion Detected!")
            
            # Use PRIORITY_NORMAL for non-emergency triggers (respects cooldown)
            # Use PRIORITY_HIGH for emergency triggers (bypasses cooldown)
            if not trigger_bus.is_busy():
                trigger_bus.fire(self.input_id, trigger_bus.PRIORITY_NORMAL)
```

### 2. Register in InputsManager

Update `InputsManager.__init__` to recognize the new type:

```python
for input_id, input_cfg in inputs_config.items():
    input_type = input_cfg.get("type")
    
    try:
        if input_type == "hall":
            handler = HallSensorInput(input_id, input_cfg, self._hall_debounce_ms, self._armed)
            self._inputs.append(handler)
            
        elif input_type == "power_monitor":
            handler = PowerMonitorInput(input_id, input_cfg, i2c)
            self._inputs.append(handler)
            
        elif input_type == "motion":  # <--- Add this block
            handler = MotionSensorInput(input_id, input_cfg, self._hall_debounce_ms)
            self._inputs.append(handler)
            
        else:
            print(f"[inputs] Unknown input type '{input_type}'")
```

### 3. Update `config.json`

Add the input definition to `inputs`:
```json
"inputs": {
  "living_room_pir": {
    "type": "motion",
    "pin": 17
  }
}
```

Bind the input to a pipeline in the `passive` section:
```json
"passive": {
  "living_room_pir": {
    "pipeline": ["scenario_turn_on_lights"],
    "loop": false
  }
}
```

### 4. Config Studio UI Integration (Optional)

To support this in the Web UI (`editor.html`):
1. Add `<option value="motion">Motion Sensor</option>` to the "Choose Input Type" modal.
2. Create a `renderMotionInput(id, cfg)` function mirroring `renderHallInput()`, exposing the `pin` setting.

---

## Priority Selection (HIGH vs NORMAL)

When writing `trigger_bus.fire(self.input_id, priority)`, you must choose a priority level:

- **`PRIORITY_HIGH`**: Bypasses active cooldowns. Use this for emergency sensors (Hall sensors detecting an opened case, battery reaching critical shutdown levels) where the action *must* execute immediately, even if the user just clicked the encoder.
- **`PRIORITY_NORMAL`**: Respects cooldowns. Use this for convenience sensors (PIR motion, buttons, ambient light sensors) to prevent them from interrupting user interactions or firing too rapidly.

---

## Known Issues / Design Notes

- **No Formal `InputBase`**: As noted above, the input system relies on duck-typing (`update(now)`). This is a deliberate simplification because the requirements of different inputs vary wildly (e.g., some need I2C, some need global armed flags). If the number of input types grows significantly, formalizing an `InputBase` contract might become necessary.
- **The Button is Hardcoded**: The physical button (`button_pin`) is hardcoded into `InputsManager._process_button()` rather than being an `Input` class. If you wish to generalize buttons as typed inputs, you will need to refactor that specific logic out of the manager.

---

## Related Documentation

- [System Architecture](architecture.md)
- [Output System Guide](outputs.md)
- [Passive Trigger System](passive-triggers.md)
- [Pipeline Configuration Guide](../user/pipelines.md)
