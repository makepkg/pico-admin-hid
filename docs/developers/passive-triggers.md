# Passive Trigger System

Technical documentation for the passive (hardware-driven) trigger system.

---

## Overview

The passive trigger system handles asynchronous hardware events from sensors (e.g., Hall effect, INA226 power monitor) and physical buttons. These triggers execute scenarios independently of menu navigation and user interaction.

### Key Characteristics

- **Asynchronous** — Events occur at any time, independent of menu state
- **Hardware-driven** — Triggered by physical sensor activation, not user clicks
- **High Priority** — Can bypass cooldown for emergency actions
- **Debounced** — Anti-bounce logic prevents false triggers

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    INPUTS MANAGER                         │
│                  (inputs_manager.py)                      │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐ │
│  │ HallSensorInput │ │PowerMonitorInput│ │ Button       │ │
│  │ (type: hall)    │ │(type: ina226)   │ │ (GPIO GP24)  │ │
│  └────────┬────────┘ └────────┬────────┘ └──────┬───────┘ │
│           │                   │                 │         │
│           ▼                   ▼                 ▼         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐ │
│  │ Debounce Logic  │ │ Threshold Logic │ │ Double-Click │ │
│  │ (300ms default) │ │ (% or voltage)  │ │ Detection    │ │
│  └────────┬────────┘ └────────┬────────┘ └──────┬───────┘ │
│           │                   │                 │         │
│           └──────────┬────────┴─────────────────┘         │
│                      ▼                                    │
│           ┌────────────────────┐                          │
│           │  State Change      │                          │
│           │  Detection         │                          │
│           └──────────┬─────────┘                          │
└──────────────────────┼────────────────────────────────────┘
                       │
                       ▼
            ┌────────────────────┐
            │  trigger_bus.fire() │
            │  priority=HIGH      │
            └──────────┬──────────┘
                       │
                       ▼
            ┌────────────────────┐
            │ execute_pipeline() │
            └────────────────────┘
```

*Note: The button is not implemented as a standalone Input class; it is handled directly within `InputsManager._process_button()` due to its special double-click and double-purpose nature.*

---

## Hardware Inputs

All typed passive sensors are defined in the `config.json` → `inputs` section. The dictionary key acts as the unique `input_id`.

### Hall Effect Sensors

**Purpose**: Detect magnetic field proximity (emergency triggers).

**Configuration**:
```json
"inputs": {
  "hall_sensor_1": {
    "type": "hall",
    "pin": 15,
    "active_low": true
  }
}
```

**Pin Logic**:
- `active_low: true` — Sensor pulls pin LOW when triggered (common with pull-up)
- `active_low: false` — Sensor pulls pin HIGH when triggered (less common)

**Typical Use Cases**:
- Emergency shutdown when case opened
- Door/drawer close detection
- Magnetic key/card activation

### INA226 Power Monitor

**Purpose**: I2C battery voltage and current monitoring, triggering on low battery thresholds.

**Configuration**:
```json
"inputs": {
  "ina226": {
    "type": "power_monitor",
    "enabled": true,
    "trigger_mode": "percent",
    "threshold_percent": 15,
    "threshold_voltage": 16.5,
    "warning_offset_percent": 5,
    "cooldown_sec": 300,
    "cancel_cooldown_sec": 3600
  }
}
```

**Fields**:
- `trigger_mode`: `"percent"` or `"voltage"`. Determines which metric triggers the alarm.
- `threshold_*`: The exact value below which the emergency trigger fires.
- `warning_offset_percent`: Adds an offset (e.g., `+5`) to the threshold to determine the "warning zone". If the battery enters this zone, a warning screen appears before the actual trigger fires.
- `cooldown_sec`: Cooldown after the trigger successfully fires.
- `cancel_cooldown_sec`: Cooldown applied if the user manually cancels the warning via encoder center click.

**Warning Dismissal**:
- **Cancel**: Encoder center click cancels the trigger and applies `cancel_cooldown_sec`.
- **Snooze/Dismiss**: Encoder scroll simply hides the warning overlay but keeps the trigger armed (`warning_dismissed` flag). If the battery drops to the critical threshold, it will still fire. The dismiss state is reset only when the battery charges back above the warning zone.

### Button Input

**Purpose**: Physical button for direct triggers (alternative to encoder).

**Pin**: Defined in `hardware.button_pin` (default GP24, also used for boot mode selection).

**Detection**: Double-click within time window.

---

## Trigger Binding

Passive triggers are bound to scenarios in the `config.json` → `passive` section using the `pipeline` format:

```json
"passive": {
  "hall_sensor_1": {
    "pipeline": ["scenario_shutdown"],
    "loop": false
  },
  "btn_double": {
    "pipeline": ["scenario_lock"],
    "loop": false
  }
}
```

**Binding Rules**:
- The key must match the sensor ID from the `inputs` section (e.g., `hall_sensor_1`) or be `btn_double`.
- The value is an object containing `pipeline` (array of scenario names) and `loop` (boolean).
- Missing binding = trigger does nothing.

**Backward Compatibility**:
The engine (`trigger_bus.py`) still supports the legacy string format:
```json
"passive": {
  "hall_sensor_1": "scenario_shutdown"
}
```
At runtime, `trigger_bus.fire()` automatically converts this string into the modern `{ "pipeline": ["scenario_shutdown"], "loop": false }` format before executing.

---

## Debouncing Logic

### Hall Sensor Debounce

**Debounce Window**: 300ms default (configurable in `config.json` → `device.debounce_ms`)

**Why Needed**:
- Reed switches can bounce on activation
- Magnetic field fluctuations near threshold
- Mechanical vibrations

### Button Debounce

Built into CircuitPython's `DigitalInOut` when using pull resistors.

**Double-Click Window**: Typically 400-500ms

---

## Priority System

Passive sensors typically use **PRIORITY_HIGH** to ensure emergency actions execute immediately:

```python
# Hall sensors and power monitors bypass cooldown
trigger_bus.fire("hall_sensor_1", PRIORITY_HIGH)

# Button uses normal priority (respects cooldown)
trigger_bus.fire("btn_double", PRIORITY_NORMAL)
```

### Priority Behavior

| Priority | Cooldown | Busy Check | Use Case |
|----------|----------|------------|----------|
| HIGH | **Bypassed** | Checked | Emergency sensors |
| NORMAL | Enforced | Checked | User interactions |

**Rationale**: Emergency scenarios (like safe shutdown) must execute immediately, even if another scenario just finished.

---

## State Machine

### Hall Sensor State Transitions

```
     ┌─────────────┐
     │   INACTIVE  │
     │  (no magnet)│
     └──────┬──────┘
            │ Magnet approaches
            │ (pin changes state)
            ▼
     ┌─────────────┐
     │  DEBOUNCING │
     │  (300ms)    │
     └──────┬──────┘
            │ Stable state confirmed
            ▼
     ┌─────────────┐
     │   ACTIVE    │────────► trigger_bus.fire()
     │  (triggered)│
     └──────┬──────┘
            │ Magnet removed
            │ (pin changes state)
            ▼
     ┌─────────────┐
     │  DEBOUNCING │
     │  (300ms)    │
     └──────┬──────┘
            │ Stable state confirmed
            ▼
     ┌─────────────┐
     │   INACTIVE  │
     └─────────────┘
```

**Note**: Trigger fires on **transition to ACTIVE**, not on every poll.

### Button State Machine

```
     ┌─────────────┐
     │    IDLE     │
     └──────┬──────┘
            │ Button pressed
            ▼
     ┌─────────────┐
     │   WAITING   │─────► Store timestamp
     └──────┬──────┘
            │ Timeout (>400ms)
            │ OR
            │ Second press (<400ms)
            ▼
     ┌─────────────┐
     │   SINGLE    │────────► Ignore (no binding)
     │   CLICK     │
     └─────────────┘
     
            OR
            
     ┌─────────────┐
     │   DOUBLE    │────────► trigger_bus.fire("btn_double")
     │   CLICK     │
     └─────────────┘
```

---

## Configuration Options

### Device-Level Settings

```json
"device": {
  "armed": true,           // Enable/disable Hall sensor triggers
  "debounce_ms": 300,      // Anti-bounce delay for sensors
  "cooldown_ms": 5000      // Cooldown after scenario execution
}
```

**armed Flag**:
- `true` — Sensors fire triggers
- `false` — Sensors monitored but don't fire (safety mode)

---

## Execution Flow Example

### Hall Sensor Trigger

```
1. Magnet approaches hall_sensor_1 (GP15)
2. Pin state changes: HIGH → LOW (active_low=true)
3. inputs_manager.py detects state change
4. Debounce timer starts (300ms)
5. State remains stable for 300ms
6. inputs_manager.py calls: trigger_bus.fire("hall_sensor_1", PRIORITY_HIGH)
7. trigger_bus checks:
   - is_busy? NO → continue
   - cooldown? BYPASSED (HIGH priority) → continue
8. trigger_bus loads pipeline from config.passive["hall_sensor_1"]
9. trigger_bus calls execute_pipeline()
10. Branches based on `loop`:
    - loop=false: executes all scenarios in the pipeline sequentially
    - loop=true: executes one scenario based on trigger_positions, increments position
11. Scenario executes (e.g., "scenario_shutdown") via OutputsManager
12. Cooldown applied (for future NORMAL priority triggers)
```

---

## Common Patterns

### Emergency Shutdown

**Trigger**: Hall sensor on case/door
**Scenario**: Safe system shutdown

```json
"passive": {
  "hall_sensor_1": { "pipeline": ["scenario_emergency_shutdown"], "loop": false }
},
"scenarios": {
  "scenario_emergency_shutdown": [
    {"action": "enter", "count": 3},
    {"wait": 500},
    {"action": "type", "value": "sudo shutdown -h now"},
    {"action": "key", "combo": "enter"}
  ]
}
```

**Use Case**: Server case opened → automatic graceful shutdown

### Access Control

**Trigger**: Hall sensor + magnetic keycard
**Scenario**: Unlock screen or open application

```json
"passive": {
  "hall_sensor_2": { "pipeline": ["scenario_unlock"], "loop": false }
},
"scenarios": {
  "scenario_unlock": [
    {"action": "key", "combo": "super+l"},
    {"wait": 200},
    {"action": "type", "value": "password123"},
    {"action": "key", "combo": "enter"}
  ]
}
```

### Dual-Sensor Logic

**Trigger**: Both sensors must activate
**Implementation**: Custom logic is required. You should add a custom `Input` class or modify `InputsManager.update()` directly.

For details on extending the input system, see [Adding a New Input Type](inputs.md).

---

## Troubleshooting

### Sensor Not Triggering

**Check**:
1. Verify `inputs` configuration matches hardware pins.
2. Check `active_low` setting matches sensor behavior.
3. Verify `device.armed = true`.
4. Check serial console for `[inputs]` logs during boot and debounce events.

### False Triggers

**Symptoms**: Triggers fire without magnet/button press

**Causes**:
- Electromagnetic interference (EMI)
- Loose wiring (floating pins)
- Wrong `active_low` setting
- Sensor too sensitive (adjust mounting distance)

**Solutions**:
- Increase `device.debounce_ms` (e.g., 500ms)
- Add hardware pull-up/pull-down resistors

### Trigger Ignored

**Symptoms**: Sensor activates but scenario doesn't execute

**Check**:
1. Serial console: `[bus] DROP — busy` or `[bus] DROP — cooldown`
2. Verify scenario name exists in `config.json`
3. Verify button priority not blocked by active cooldown

---

## Performance Characteristics

### Polling Rate

- **Main loop**: 100 Hz (10ms cycle time)
- **Sensor sampling**: Every loop iteration
- **Effective latency**: 10-20ms (loop + debounce start)

### Debounce Overhead

- **No overhead** when sensors inactive
- **300ms delay** from physical event to trigger fire
- **Tradeoff**: Lower debounce = faster response but more false triggers

---

## Safety Considerations

### Emergency Triggers

**Design Principle**: Hall sensors and power monitors bypass cooldown for safety-critical actions

**Example**: Server shutdown must execute even if user just triggered another scenario

**Implementation**:
```python
# Always use PRIORITY_HIGH for emergency sensors
trigger_bus.fire("hall_sensor_emergency", PRIORITY_HIGH)
```

### Armed Mode

**Purpose**: Disable sensors during maintenance

**Usage**:
```json
"device": {
  "armed": false  // Sensors monitored but don't fire
}
```

---

## API Reference

### InputsManager Class

**Constructor**:
```python
InputsManager(i2c=None)
```

**Lifecycle Methods**:
```python
update()                # Poll all inputs and button, call every main loop
startup_blink(count=3)  # LED feedback on boot
```

**INA226 / Power Monitor Methods**:
```python
@property
ina_warning_active      # Checks if any power monitor has warning active
@property
ina_warning_percent     # Gets warning percent from first active power monitor

cancel_ina_trigger()    # Cancels the trigger on all power monitors
dismiss_ina_warning()   # Dismisses the warning without cooldown
get_power_monitor(input_id) # Gets power monitor by ID for direct access
```

---

## Related Documentation

- [Active Trigger System](active-triggers.md)
- [Trigger Bus Architecture](architecture.md#trigger-system)
- [Hardware Configuration](../user/config-editor.md#hardware-pins-configuration)
- [Input System Guide](inputs.md) (How to add a new input type)
