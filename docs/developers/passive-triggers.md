# Passive Trigger System

Technical documentation for the passive (hardware-driven) trigger system.

---

## Overview

The passive trigger system handles asynchronous hardware events from Hall effect sensors and physical buttons. These triggers execute scenarios independently of menu navigation and user interaction.

### Key Characteristics

- **Asynchronous** — Events occur at any time, independent of menu state
- **Hardware-driven** — Triggered by physical sensor activation, not user clicks
- **High Priority** — Can bypass cooldown for emergency actions
- **Debounced** — Anti-bounce logic prevents false triggers

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    PASSIVE HANDLER                        │
│                     (passive.py)                          │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐         ┌──────────────────┐       │
│  │  Hall Sensors   │         │  Button          │       │
│  │  (GPIO inputs)  │         │  (GPIO input)    │       │
│  └────────┬────────┘         └────────┬─────────┘       │
│           │                           │                  │
│           ▼                           ▼                  │
│  ┌─────────────────┐         ┌──────────────────┐       │
│  │  Debounce Logic │         │  Double-Click    │       │
│  │  (300ms default)│         │  Detection       │       │
│  └────────┬────────┘         └────────┬─────────┘       │
│           │                           │                  │
│           └──────────┬────────────────┘                  │
│                      ▼                                   │
│           ┌────────────────────┐                         │
│           │  State Change      │                         │
│           │  Detection         │                         │
│           └──────────┬─────────┘                         │
└──────────────────────┼──────────────────────────────────┘
                       │
                       ▼
            ┌────────────────────┐
            │  trigger_bus.fire() │
            │  priority=HIGH      │
            └──────────┬──────────┘
                       │
                       ▼
            ┌────────────────────┐
            │  Scenario Executor │
            └────────────────────┘
```

---

## Hardware Inputs

### Hall Effect Sensors

**Purpose**: Detect magnetic field proximity (emergency triggers)

**Configuration**:
```json
"hardware": {
  "hall_sensors": [
    {
      "id": "hall_sensor_1",
      "pin": 15,
      "active_low": true
    }
  ]
}
```

**Pin Logic**:
- `active_low: true` — Sensor pulls pin LOW when triggered (common with pull-up)
- `active_low: false` — Sensor pulls pin HIGH when triggered (less common)

**Typical Use Cases**:
- Emergency shutdown when case opened
- Door/drawer close detection
- Magnetic key/card activation
- Proximity detection

### Button Input

**Purpose**: Physical button for direct triggers (alternative to encoder)

**Pin**: GP24 (also used for boot mode selection)

**Detection**: Double-click within time window

**Typical Use Cases**:
- Lock screen (double-click)
- Quick access to specific scenario
- Emergency stop/cancel

---

## Trigger Binding

Passive triggers are bound to scenarios in `config.json`:

```json
"passive": {
  "hall_sensor_1": "scenario_shutdown",
  "hall_sensor_2": "scenario_alarm",
  "btn_double": "scenario_lock"
}
```

**Binding Rules**:
- Key must match sensor ID or `btn_double`
- Value must be valid scenario name
- Missing binding = trigger does nothing
- Invalid scenario name = logged error, no crash

---

## Debouncing Logic

### Hall Sensor Debounce

```python
def _check_hall_sensors(self):
    now = time.monotonic()
    
    for idx, sensor in enumerate(self._hall_sensors):
        raw_value = sensor.value
        expected = 0 if sensor_config["active_low"] else 1
        triggered = (raw_value == expected)
        
        # State change detected
        if triggered != self._last_hall_states[idx]:
            self._last_hall_times[idx] = now
            self._last_hall_states[idx] = triggered
        
        # Debounce period passed
        elapsed_ms = (now - self._last_hall_times[idx]) * 1000
        if elapsed_ms > self._debounce_ms and triggered:
            if self._armed:
                trigger_bus.fire(sensor_id, PRIORITY_HIGH)
```

**Debounce Window**: 300ms default (configurable in `config.json` → `device.debounce_ms`)

**Why Needed**:
- Reed switches can bounce on activation
- Magnetic field fluctuations near threshold
- Mechanical vibrations

### Button Debounce

Built into CircuitPython's `DigitalInOut` when using pull resistors.

**Double-Click Detection**:
```python
def _check_button(self):
    if button_pressed:
        now = time.monotonic()
        time_since_last = now - self._btn_last_click
        
        if time_since_last < DOUBLE_CLICK_WINDOW:
            # Second click within window
            trigger_bus.fire("btn_double", PRIORITY_NORMAL)
        
        self._btn_last_click = now
```

**Double-Click Window**: Typically 500ms

---

## Priority System

Passive triggers use **PRIORITY_HIGH** to ensure emergency actions execute immediately:

```python
# Hall sensors bypass cooldown
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
            │ Timeout (>500ms)
            │ OR
            │ Second press (<500ms)
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
- `true` — Hall sensors fire triggers
- `false` — Hall sensors monitored but don't fire (safety mode)

### Hardware Configuration

```json
"hardware": {
  "hall_sensors": [
    {"id": "hall_sensor_1", "pin": 15, "active_low": true},
    {"id": "hall_sensor_2", "pin": 16, "active_low": true}
  ],
  "button_pin": 24
}
```

**Dynamic Sensors**:
- Add/remove sensors via Config Studio editor
- Changes require reboot to take effect

---

## Execution Flow Example

### Hall Sensor Trigger

```
1. Magnet approaches hall_sensor_1 (GP15)
2. Pin state changes: HIGH → LOW (active_low=true)
3. passive.py detects state change
4. Debounce timer starts (300ms)
5. State remains stable for 300ms
6. passive.py calls: trigger_bus.fire("hall_sensor_1", PRIORITY_HIGH)
7. trigger_bus checks:
   - is_busy? NO → continue
   - cooldown? BYPASSED (HIGH priority) → continue
8. trigger_bus loads scenario from config.passive["hall_sensor_1"]
9. Scenario executes: "scenario_shutdown"
10. HID commands sent to host system
11. Cooldown applied (for future NORMAL priority triggers)
```

### Button Double-Click

```
1. User presses button (GP24)
2. passive.py records timestamp: t1
3. User releases button
4. User presses button again
5. passive.py calculates: t2 - t1 = 350ms
6. Double-click detected (< 500ms window)
7. passive.py calls: trigger_bus.fire("btn_double", PRIORITY_NORMAL)
8. trigger_bus checks:
   - is_busy? NO → continue
   - cooldown? t_elapsed > 5s → continue
9. Scenario executes: "scenario_lock"
10. HID commands: WIN+L (lock screen)
```

---

## Common Patterns

### Emergency Shutdown

**Trigger**: Hall sensor on case/door
**Scenario**: Safe system shutdown

```json
"passive": {
  "hall_sensor_1": "scenario_emergency_shutdown"
},
"scenarios": {
  "scenario_emergency_shutdown": [
    {"action": "enter", "count": 3},
    {"action": "wait", "ms": 500},
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
  "hall_sensor_2": "scenario_unlock"
},
"scenarios": {
  "scenario_unlock": [
    {"action": "key", "combo": "super+l"},
    {"action": "wait", "ms": 200},
    {"action": "type", "value": "password123"},
    {"action": "key", "combo": "enter"}
  ]
}
```

**Security Note**: Passwords in plaintext config.json are insecure. Use for non-critical systems only.

### Dual-Sensor Logic

**Trigger**: Both sensors must activate
**Implementation**: Requires code modification (not supported by default)

**Pseudo-code**:
```python
# Custom logic in passive.py
if sensor_1_active and sensor_2_active:
    trigger_bus.fire("dual_trigger", PRIORITY_HIGH)
```

---

## Troubleshooting

### Sensor Not Triggering

**Check**:
1. Verify pin number matches `hardware.hall_sensors[].pin`
2. Test sensor with multimeter: resistance changes with magnet?
3. Check `active_low` setting matches sensor behavior
4. Verify `device.armed = true`
5. Check serial console for debounce messages

**Debug Output**:
```python
# Add to passive.py for debugging
print(f"[passive] Sensor {idx}: raw={sensor.value}, expected={expected}")
```

### False Triggers

**Symptoms**: Triggers fire without magnet/button press

**Causes**:
- Electromagnetic interference (EMI)
- Loose wiring (floating pins)
- Wrong `active_low` setting
- Sensor too sensitive (adjust mounting distance)

**Solutions**:
- Increase `debounce_ms` (e.g., 500ms)
- Add hardware pull-up/pull-down resistors
- Shield wires from power cables
- Use shielded/twisted pair cables for sensors

### Trigger Ignored

**Symptoms**: Sensor activates but scenario doesn't execute

**Check**:
1. Serial console: `[bus] DROP — busy` or `[bus] DROP — cooldown`
2. Verify scenario name exists in `config.json`
3. Check USB connected: `supervisor.runtime.usb_connected`
4. Verify button priority not blocked by active cooldown

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

### Memory Usage

- **Per sensor**: ~50 bytes (DigitalInOut object + state)
- **Handler overhead**: ~200 bytes (lists, timestamps)
- **Scalable**: Tested with 2 sensors, supports up to 10+

---

## Safety Considerations

### Emergency Triggers

**Design Principle**: Hall sensors bypass cooldown for safety-critical actions

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

**Alternative**: Remove sensor bindings from `passive` object

---

## Future Enhancements

### Multi-Sensor Logic

Combine multiple sensors with AND/OR logic:
```python
if sensor_1 and sensor_2:
    trigger_bus.fire("both_active")
elif sensor_1 or sensor_2:
    trigger_bus.fire("any_active")
```

### Sensor Events

Current: Only trigger on activation
Future: Trigger on deactivation, hold duration, rapid toggling

### Threshold Configuration

Hall sensors with analog output: trigger at specific field strength

---

## API Reference

### PassiveHandler Class

**Constructor**:
```python
PassiveHandler()
```

**Methods**:
```python
update()              # Poll sensors, call every main loop
startup_blink()       # LED feedback on boot
```

**Internal Methods**:
```python
_check_hall_sensors()  # Poll and debounce Hall sensors
_check_button()        # Detect button double-click
```

---

## Related Documentation

- [Active Trigger System](active-triggers.md)
- [Trigger Bus Architecture](architecture.md#trigger-system)
- [Hardware Configuration](../user/config-editor.md#hardware-pins-configuration)
