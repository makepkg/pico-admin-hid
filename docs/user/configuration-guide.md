# Configuration Guide

Complete guide to `config.json` structure, principles, and best practices.

---

## Table of Contents

- [Overview](#overview)
- [File Structure](#file-structure)
- [Hardware Section](#hardware-section)
- [Inputs Section](#inputs-section)
- [Outputs Section](#outputs-section)
- [Device Section](#device-section)
- [Passive Section](#passive-section)
- [Active Menu Section](#active-menu-section)
- [Scenarios Section](#scenarios-section)
- [State Persistence](#state-persistence)
- [Validation Rules](#validation-rules)
- [Best Practices](#best-practices)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

### What is config.json?

`config.json` is the central configuration file that defines:
- Hardware pin assignments
- Input sensors and Output targets
- Device behavior settings
- Menu structure and navigation
- Automation scenarios and pipeline bindings

### Configuration Principles

1. **Single Source of Truth** — All configuration in one file
2. **Human-Readable** — JSON format with clear structure
3. **Validatable** — Config Studio editor validates on save
4. **Hot-Reloadable** — Changes apply on device reboot
5. **Version-Controlled** — Easy to track changes in git

### Files Involved

| File | Purpose | Writable From |
|------|---------|---------------|
| `config.json` | Static configuration | USB (dev mode) or Config Studio |
| `state.json` | Runtime state (auto-generated) | Code (normal mode) |
| `boot_out.txt` | CircuitPython info (auto-generated) | System |

**Important**: Edit `config.json` only. Never manually edit `state.json` (managed by code).

---

## File Structure

### Top-Level Schema

The configuration file must contain the following 7 top-level keys:

```json
{
  "hardware": { },      // Basic UI/system pin assignments (encoder, display, button)
  "inputs": { },        // Hardware sensors (Hall, INA226) configuration
  "outputs": { },       // Action targets (USB HID, GPIO pins)
  "device": { },        // Global behavior settings (cooldown, timeouts)
  "passive": { },       // Sensor/Button bindings to scenario pipelines
  "active_menu": [ ],   // Rotary encoder menu hierarchy
  "scenarios": { }      // Definitions of steps to execute
}
```

Empty sections must use `{}` or `[]`.

---

## Hardware Section

### Purpose
Defines GPIO pin assignments for the core UI and system components. 
*(Note: Sensors like Hall effect or INA226 are now configured in the [Inputs Section](#inputs-section)).*

### Schema

```json
"hardware": {
  "button_pin": number,        // Boot button pin (GP24)
  "led_pin": number,           // Status LED pin (GP25)
  "encoder_clk": number,       // Encoder clock pin
  "encoder_dt": number,        // Encoder data pin
  "encoder_sw": number,        // Encoder switch pin
  "display_sda": number,       // OLED I2C data pin
  "display_scl": number        // OLED I2C clock pin
}
```

### Default Assignments
```json
"hardware": {
  "button_pin": 24,
  "led_pin": 25,
  "encoder_clk": 6,
  "encoder_dt": 7,
  "encoder_sw": 8,
  "display_sda": 4,
  "display_scl": 5
}
```

---

## Inputs Section

### Purpose
Defines hardware sensors that can generate passive triggers.

### Schema Structure
```json
"inputs": {
  "input_id": { ... }
}
```
The key (`"input_id"`) acts as the unique identifier used later in the `passive` section.

### 1. Hall Sensors
Detects magnetic field proximity (typically used for emergency triggers like opening a case).

```json
"inputs": {
  "hall_sensor_1": {
    "type": "hall",
    "pin": 15,
    "active_low": true
  }
}
```
- `type`: Must be `"hall"`.
- `pin`: GPIO pin number.
- `active_low`: `true` means the sensor pulls the pin LOW when the magnet is present.

### 2. Power Monitor (INA226)
Monitors battery voltage/current over I2C and fires a trigger when battery is critically low.

```json
"inputs": {
  "ina226": {
    "type": "power_monitor",
    "enabled": true,
    "trigger_mode": "percent",
    "threshold_percent": 15,
    "threshold_voltage": 16.5,
    "warning_offset_percent": 5,
    "recovery_offset_percent": 10,
    "trigger_attempts": 3,
    "trigger_attempt_interval_sec": 60,
    "read_interval_sec": 5.0,
    "warning_enabled": true,
    "warning_blink_interval": 0.5,
    "warning_canceled_display_sec": 2.0,
    "splash_interval_sec": 30,
    "splash_duration_sec": 6,
    "battery_max_v": 21.0,
    "battery_min_v": 15.0,
    "shunt_ohms": 0.1,
    "i2c_address": 64
  }
}
```
- `type`: Must be `"power_monitor"`.
- `trigger_mode`: `"percent"` or `"voltage"`.
- `recovery_offset_percent`: Additional % above threshold required before resuming normal monitoring after recovery. Prevents re-triggering immediately after the battery recovers. Default: `10`.
- `trigger_attempts`: Maximum number of shutdown attempts before the system enters SUSPENDED state and stops retrying. Default: `3`.
- `trigger_attempt_interval_sec`: Seconds between retry attempts when the server does not respond to shutdown. Default: `60`.
- `warning_offset_percent`: Adds this value to the threshold to show a warning before triggering (e.g., threshold 15% → warning starts at 20%).
- `splash_duration_sec`: How long the battery HUD stays on screen during screensaver.

---

## Outputs Section

### Purpose
Defines the targets where scenario actions are executed.

### Schema Structure
```json
"outputs": {
  "output_name": { ... }
}
```

### 1. HID Output
Sends keystrokes to the connected host computer via USB.

```json
"outputs": {
  "hid": {
    "type": "hid",
    "enabled": true,
    "usb_layout": "us"
  }
}
```

### 2. GPIO Output
Controls a physical digital pin (e.g., relay, optocoupler).

```json
"outputs": {
  "opto_pwr": {
    "type": "gpio",
    "enabled": true,
    "pin": 14,
    "active_high": true,
    "label": "PC Power Button",
    "default_scenario": "scenario_opto_pwr_pulse"
  }
}
```
- `type`: Must be `"gpio"`.
- `active_high`: Defines the electrical level for the "active" state.
- `default_scenario`: A UI convention used by Config Studio to auto-generate a 1-step scenario for this output.

### 3. Auto-Boot (Inside GPIO Output)
Automatically pulses a GPIO pin if the USB connection is not detected after boot.
*(Note: Supported on only **one** GPIO output at a time).*

```json
"outputs": {
  "opto_pwr": {
    "type": "gpio",
    "pin": 14,
    "auto_boot": {
      "enabled": true,
      "check_interval_s": 15,
      "max_attempts": 2,
      "retry_cooldown_min": 5
    }
  }
}
```

---

## Device Section

### Purpose
Controls global device behavior and timing parameters.

### Schema
```json
"device": {
  "armed": true,
  "debounce_ms": 300,
  "cooldown_ms": 5000,
  "screen_timeout_s": 15,
  "screensaver": "tesseract"
}
```
- `armed`: Master switch for Hall sensor triggers.
- `debounce_ms`: Anti-bounce delay for sensors.
- `cooldown_ms`: Global cooldown between active scenario executions to prevent spam.
- `screen_timeout_s`: Seconds of inactivity before screen sleeps or screensaver starts.
- `screensaver`: `"off"`, `"tesseract"`, `"starfield"`, or `"matrix"`.

---

## Passive Section

### Purpose
Binds hardware input IDs to scenario pipelines.

### Schema
```json
"passive": {
  "hall_sensor_1": {
    "pipeline": ["scenario_emergency_shutdown"],
    "loop": false
  },
  "btn_double": {
    "pipeline": ["scenario_lock_screen"],
    "loop": false
  }
}
```

**Pipeline execution modes**:
- `loop: false` — Executes the entire list of scenarios sequentially at once.
- `loop: true` — Executes exactly one scenario per trigger event, advancing to the next one on the next trigger.

*(Note: The legacy string format `"hall_sensor_1": "scenario_name"` is still supported for backward compatibility, but the `pipeline` object is the modern standard).*

---

## Active Menu Section

### Purpose
Defines hierarchical menu structure for encoder navigation.

### Schema
```json
"active_menu": [
  {
    "id": "string",
    "label": "string",
    "pipeline": [ ],
    "loop": boolean,
    "submenu": [ ]
  }
]
```

### Item Types

**1. Action Item** (executes scenarios):
```json
{
  "id": "docker_service",
  "label": "Docker App",
  "pipeline": [
    {"scenario": "docker_stop", "label": "Stop"},
    {"scenario": "docker_start", "label": "Start"}
  ],
  "loop": true
}
```
*(With `loop: true`, each click toggles to the next scenario).*

**2. Folder Item** (nested menu):
```json
{
  "id": "servers",
  "label": "Servers",
  "submenu": [
    {
      "id": "web_server",
      "label": "Web Server",
      "pipeline": ["web_start"],
      "loop": false
    }
  ]
}
```

**3. Hybrid Item** (executes then opens folder):
```json
{
  "id": "refresh_folder",
  "label": "Monitoring",
  "pipeline": [
    {"scenario": "refresh_status", "label": "Refresh"}
  ],
  "loop": false,
  "submenu": [ ... ]
}
```

---

## Scenarios Section

### Purpose
Maps scenario names to command steps. Each step can target a specific `output`.

### Schema
```json
"scenarios": {
  "scenario_name": [
    {
      "output": "string",    // Target output (default: "hid")
      "action": "string",    // Action type
      // ...parameters
    }
  ]
}
```

### Action Types (HID Output)

- `type`: Types text.
  ```json
  {"output": "hid", "action": "type", "value": "docker-compose up"}
  ```
- `key`: Presses key combinations.
  ```json
  {"output": "hid", "action": "key", "combo": "ctrl+c"}
  ```
- `enter`: Presses the Enter key `count` times (1-10).
  ```json
  {"output": "hid", "action": "enter", "count": 3}
  ```

### Action Types (GPIO Output)

- `gpio_pulse`: 250ms pulse (simulates a button press).
  ```json
  {"output": "opto_pwr", "action": "gpio_pulse"}
  ```
- `gpio_hold`: Hold active state for `duration_ms`.
  ```json
  {"output": "opto_pwr", "action": "gpio_hold", "duration_ms": 1000}
  ```
- `gpio_set`: Sets raw electrical level (`"high"`/`"low"`), bypassing `active_high`.
  ```json
  {"output": "opto_pwr", "action": "gpio_set", "value": "high"}
  ```

### Pause Execution
Use the short-hand `wait` command to pause between steps.
```json
{"wait": 500}
```
*(The legacy `{"action": "wait", "ms": 500}` format is also supported).*

---

## State Persistence

### `state.json` Structure
**Auto-generated file** (do not edit manually):

```json
{
  "menu_cursor": 2,
  "trigger_positions": {
    "active_docker_service": 1,
    "passive_hall_sensor_1": 0
  },
  "seq_positions": {
    "legacy_item": 1
  }
}
```

- `menu_cursor`: Current menu index.
- `trigger_positions`: Current execution index for pipelines with `loop: true`. Keys are prefixed with `active_` or `passive_`.
- `seq_positions`: Legacy tracking for old `sequence` configurations.

---

## Validation Rules

The Config Studio (`editor.html`) validates the configuration to prevent runtime errors:

1. **JSON Syntax** — Ensures valid JSON format.
2. **Missing Scenarios** — Warns if a pipeline references a scenario that doesn't exist in the `scenarios` section.
3. **Missing Outputs** — Warns if a scenario step references an output that isn't defined in `outputs`.
4. **Invalid Keys** — Warns if a HID `key` action uses unsupported keys.
5. **Auto-Boot Limit** — Ensures only one output has auto-boot enabled.
6. **Unique IDs** — Validates that menu item IDs are unique.

---

## Best Practices

**Group Related Items**:
Use folders (`submenu`) to group related actions (e.g., all Docker containers in one folder).

**Use Descriptive IDs**:
- Good: `"nextcloud_restart"`, `"backup_daily"`
- Bad: `"item1"`, `"test"`

**Scenario Design**:
- Clear the terminal before typing commands: `{"action": "enter", "count": 3}`
- Add `{"wait": 200}` after pressing enter before typing the next command.
- Use absolute paths in terminal commands (`cd /opt/app && docker-compose restart`).

---

## Examples

### Minimal Configuration
A complete, valid, minimal configuration that prints "Hello World".

```json
{
  "hardware": {
    "button_pin": 24,
    "led_pin": 25,
    "encoder_clk": 6,
    "encoder_dt": 7,
    "encoder_sw": 8,
    "display_sda": 4,
    "display_scl": 5
  },
  "inputs": {},
  "outputs": {
    "hid": {
      "type": "hid",
      "enabled": true,
      "usb_layout": "us"
    }
  },
  "device": {
    "armed": false,
    "debounce_ms": 300,
    "cooldown_ms": 5000,
    "screen_timeout_s": 0,
    "screensaver": "off"
  },
  "passive": {},
  "active_menu": [
    {
      "id": "hello",
      "label": "Hello World",
      "pipeline": [
        {"scenario": "say_hello", "label": "Run"}
      ],
      "loop": false
    }
  ],
  "scenarios": {
    "say_hello": [
      {"output": "hid", "action": "type", "value": "echo Hello, World!"},
      {"output": "hid", "action": "key", "combo": "enter"}
    ]
  }
}
```

### Homelab Configuration
A comprehensive configuration with sensors, GPIO control, auto-boot, and a toggle menu.

```json
{
  "hardware": {
    "button_pin": 24,
    "led_pin": 25,
    "encoder_clk": 6,
    "encoder_dt": 7,
    "encoder_sw": 8,
    "display_sda": 4,
    "display_scl": 5
  },
  "inputs": {
    "case_door": {
      "type": "hall",
      "pin": 15,
      "active_low": true
    }
  },
  "outputs": {
    "hid": {
      "type": "hid",
      "enabled": true,
      "usb_layout": "us"
    },
    "pc_power": {
      "type": "gpio",
      "enabled": true,
      "pin": 14,
      "active_high": true,
      "label": "PC Power Button",
      "auto_boot": {
        "enabled": true,
        "check_interval_s": 15,
        "max_attempts": 2,
        "retry_cooldown_min": 5
      }
    }
  },
  "device": {
    "armed": true,
    "debounce_ms": 300,
    "cooldown_ms": 5000,
    "screen_timeout_s": 30,
    "screensaver": "tesseract"
  },
  "passive": {
    "case_door": {
      "pipeline": ["scenario_safe_shutdown"],
      "loop": false
    }
  },
  "active_menu": [
    {
      "id": "turn_on_pc",
      "label": "Boot PC",
      "pipeline": [
        {"scenario": "scenario_pulse_power", "label": "Power"}
      ],
      "loop": false
    },
    {
      "id": "docker_service",
      "label": "Docker App",
      "pipeline": [
        {"scenario": "scenario_docker_stop", "label": "Stop"},
        {"scenario": "scenario_docker_start", "label": "Start"}
      ],
      "loop": true
    }
  ],
  "scenarios": {
    "scenario_safe_shutdown": [
      {"output": "hid", "action": "enter", "count": 3},
      {"wait": 500},
      {"output": "hid", "action": "type", "value": "sudo shutdown -h now"},
      {"output": "hid", "action": "key", "combo": "enter"}
    ],
    "scenario_pulse_power": [
      {"output": "pc_power", "action": "gpio_pulse"}
    ],
    "scenario_docker_stop": [
      {"output": "hid", "action": "enter", "count": 3},
      {"output": "hid", "action": "type", "value": "docker-compose stop"},
      {"output": "hid", "action": "key", "combo": "enter"}
    ],
    "scenario_docker_start": [
      {"output": "hid", "action": "enter", "count": 3},
      {"output": "hid", "action": "type", "value": "docker-compose start"},
      {"output": "hid", "action": "key", "combo": "enter"}
    ]
  }
}
```

---

## Troubleshooting

### Hall Sensors Not Working
1. Check that the ID in `inputs.<id>` matches the ID bound in the `passive` section.
2. Verify `device.armed` is `true`.
3. Check the serial console to ensure the hardware is actually triggering.

### Scenarios Not Executing
1. Verify the scenario name in `active_menu[].pipeline[].scenario` exactly matches the key in the `scenarios` object.
2. Check if a cooldown is active (`[bus] DROP — cooldown` in the console).
3. If using HID actions, ensure the USB is connected to a host device.

### State Not Saving
If the menu cursor or toggle state resets on reboot, you might be booting in Development Mode. Do not hold the GP24 button while plugging in the device.

---
*Last Updated: 2026-06-24*  
*Architecture: Unified Pipeline, Inputs, and Outputs Engine*
