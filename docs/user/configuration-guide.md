# Configuration Guide

Complete guide to `config.json` structure, principles, and best practices.

---

## Table of Contents

- [Overview](#overview)
- [File Structure](#file-structure)
- [Hardware Section](#hardware-section)
- [Device Section](#device-section)
- [Passive Section](#passive-section)
- [Active Menu Section](#active-menu-section)
- [Scenarios Section](#scenarios-section)
- [State Persistence](#state-persistence)
- [Validation Rules](#validation-rules)
- [Best Practices](#best-practices)
- [Examples](#examples)

---

## Overview

### What is config.json?

`config.json` is the central configuration file that defines:
- Hardware pin assignments
- Device behavior settings
- Menu structure and navigation
- Automation scenarios
- Trigger bindings

### Configuration Principles

1. **Single Source of Truth** — All configuration in one file
2. **Human-Readable** — JSON format with clear structure
3. **Validatable** — Config Studio editor validates on save
4. **Hot-Reloadable** — Changes apply on device reboot
5. **Version-Controlled** — Easy to track changes in git

### Files Involved

| File | Purpose | Writable From |
|------|---------|---------------|
| `config.json` | Static configuration | USB (dev mode) or editor |
| `state.json` | Runtime state (auto-generated) | Code (normal mode) |
| `boot_out.txt` | CircuitPython info (auto-generated) | System |

**Important**: Edit `config.json` only. Never manually edit `state.json` (managed by code).

---

## File Structure

### Top-Level Schema

```json
{
  "hardware": { },      // Pin assignments for all components
  "device": { },        // Behavior settings (cooldown, timeouts)
  "passive": { },       // Trigger → Scenario bindings
  "active_menu": [ ],   // Menu hierarchy array
  "scenarios": { }      // Scenario name → steps mapping
}
```

All five sections are **required**. Empty sections must use `{}` or `[]`.

---

## Hardware Section

### Purpose

Defines GPIO pin assignments for all physical components.

### Schema

```json
"hardware": {
  "hall_sensors": [
    {
      "id": "string",          // Unique identifier
      "pin": number,           // GPIO pin number
      "active_low": boolean    // Logic level (true/false)
    }
  ],
  "button_pin": number,        // Boot button pin
  "led_pin": number,           // Status LED pin
  "encoder_clk": number,       // Encoder clock pin
  "encoder_dt": number,        // Encoder data pin
  "encoder_sw": number,        // Encoder switch pin
  "display_sda": number,       // OLED I2C data pin
  "display_scl": number        // OLED I2C clock pin
}
```

### Hall Sensors

**Multiple sensors supported** (array):

```json
"hall_sensors": [
  {
    "id": "hall_sensor_1",
    "pin": 15,
    "active_low": true
  },
  {
    "id": "hall_sensor_2",
    "pin": 16,
    "active_low": true
  }
]
```

**Properties**:
- `id` (string, required) — Unique identifier used in `passive` section
- `pin` (number, required) — GPIO pin number (0-29 for Pico)
- `active_low` (boolean, required) — Signal logic:
  - `true` — Sensor pulls LOW when triggered (common with pull-up resistors)
  - `false` — Sensor pulls HIGH when triggered (less common)

**Pin Selection**:
- Use any free GPIO pin
- Avoid pins used by I2C (GP4, GP5 by default)
- Avoid pins used by encoder (GP6, GP7, GP8 by default)
- Standard pins: GP15, GP16 (not used by other components)

### Other Hardware Pins

**Default Assignments**:
```json
"button_pin": 24,      // GP24 (boot button on Pico)
"led_pin": 25,         // GP25 (onboard LED)
"encoder_clk": 6,      // GP6
"encoder_dt": 7,       // GP7
"encoder_sw": 8,       // GP8
"display_sda": 4,      // GP4 (I2C0 SDA)
"display_scl": 5       // GP5 (I2C0 SCL)
```

**Changing Pins**:
- Verify hardware wiring matches new assignments
- Encoder: CLK/DT can be swapped if rotation direction inverted
- Display: Must use I2C-capable pins (GP0/GP1, GP2/GP3, GP4/GP5, etc.)

### Hardware Validation

**Rules**:
1. All pin numbers must be 0-29 (Pico GPIO range)
2. No duplicate pin assignments (each pin used once)
3. Sensor IDs must be unique
4. I2C pins must be valid I2C pairs

---

## Device Section

### Purpose

Controls device-wide behavior and timing parameters.

### Schema

```json
"device": {
  "armed": boolean,               // Enable/disable Hall sensors
  "debounce_ms": number,          // Anti-bounce delay (milliseconds)
  "cooldown_ms": number,          // Anti-spam delay (milliseconds)
  "screen_timeout_s": number,     // Screen sleep timeout (seconds)
  "screensaver": "string"         // Screensaver mode
}
```

### Properties

#### `armed` (boolean)

**Purpose**: Master switch for Hall sensor triggers

**Values**:
- `true` — Hall sensors fire scenarios when triggered
- `false` — Hall sensors monitored but don't execute scenarios (safety mode)

**Use Cases**:
- `false` during maintenance/testing
- `false` when sensors wired but not configured
- `true` for production use

**Example**:
```json
"armed": true
```

#### `debounce_ms` (number)

**Purpose**: Anti-bounce delay for Hall sensors

**Range**: 50-1000 ms (typical: 300 ms)

**Behavior**: After Hall sensor state changes, wait this duration before confirming trigger. Prevents false triggers from:
- Reed switch mechanical bounce
- Magnetic field fluctuations
- Electrical noise

**Values**:
- Lower (100-200 ms) — Faster response, more false triggers
- Higher (500-1000 ms) — Slower response, fewer false triggers

**Example**:
```json
"debounce_ms": 300
```

#### `cooldown_ms` (number)

**Purpose**: Minimum time between scenario executions

**Range**: 1000-10000 ms (typical: 5000 ms)

**Behavior**: After scenario completes, reject all NORMAL priority triggers until cooldown expires. Prevents:
- Accidental double-clicks
- Encoder bounce
- Rapid repeated execution

**Priority Override**: HIGH priority triggers (Hall sensors) bypass cooldown.

**Values**:
- Lower (1000-3000 ms) — Allow rapid successive commands
- Higher (5000-10000 ms) — Prevent accidental multi-execution

**Example**:
```json
"cooldown_ms": 5000
```

#### `screen_timeout_s` (number)

**Purpose**: Auto-sleep timeout in seconds

**Range**: 0 (disabled) or 5-300 seconds

**Behavior**:
- `0` — Screen never sleeps
- `> 0` — After timeout with no interaction, screen sleeps or screensaver starts

**Sleep vs Screensaver**: Determined by `screensaver` setting:
- `screensaver: "off"` → Screen turns off (blank)
- `screensaver: "tesseract"` → Animation plays

**Example**:
```json
"screen_timeout_s": 15
```

#### `screensaver` (string)

**Purpose**: Screen behavior after timeout

**Values**:
- `"off"` — Screen turns black (saves power)
- `"tesseract"` — 4D hypercube rotation animation
- `"starfield"` — 3D starfield movement
- `"matrix"` — Matrix-style falling characters

**Performance**: Animations use ~5-10% CPU at 20 FPS.

**Example**:
```json
"screensaver": "tesseract"
```

### Complete Device Example

```json
"device": {
  "armed": true,
  "debounce_ms": 300,
  "cooldown_ms": 5000,
  "screen_timeout_s": 15,
  "screensaver": "tesseract"
}
```

---

## Passive Section

### Purpose

Binds hardware triggers to scenario names.

### Schema

```json
"passive": {
  "trigger_id": "scenario_name",
  "hall_sensor_1": "scenario_shutdown",
  "hall_sensor_2": "scenario_alarm",
  "btn_double": "scenario_lock"
}
```

### Trigger Types

| Trigger ID | Source | Priority |
|------------|--------|----------|
| `hall_sensor_*` | Hall sensor activation | HIGH (bypasses cooldown) |
| `btn_double` | Button double-click | NORMAL (respects cooldown) |

**Hall sensor IDs** must match `hardware.hall_sensors[].id`.

### Binding Rules

1. **Key** = Trigger ID (from hardware or built-in)
2. **Value** = Scenario name (must exist in `scenarios` section)
3. Missing trigger = No action on activation
4. Invalid scenario name = Error logged, no crash

### Examples

**Hall Sensor Emergency Shutdown**:
```json
"passive": {
  "hall_sensor_1": "scenario_emergency_shutdown"
}
```

**Button Lock Screen**:
```json
"passive": {
  "btn_double": "scenario_lock_screen"
}
```

**Multiple Triggers**:
```json
"passive": {
  "hall_sensor_1": "scenario_shutdown",
  "hall_sensor_2": "scenario_alert",
  "btn_double": "scenario_lock"
}
```

**No Bindings** (disable triggers):
```json
"passive": {}
```

---

## Active Menu Section

### Purpose

Defines hierarchical menu structure for encoder navigation.

### Schema

```json
"active_menu": [
  {
    "id": "string",           // Unique identifier (required)
    "label": "string",        // Display text (required)
    "sequence": [ ],          // Action sequence (optional)
    "submenu": [ ]            // Nested items (optional)
  }
]
```

### Item Types

**Action Item** (has sequence):
```json
{
  "id": "docker_service",
  "label": "Docker App",
  "sequence": [
    {"scenario": "docker_stop", "name": "Stop"},
    {"scenario": "docker_start", "name": "Start"}
  ]
}
```

**Folder Item** (has submenu):
```json
{
  "id": "servers",
  "label": "Servers",
  "submenu": [
    {
      "id": "web_server",
      "label": "Web Server",
      "sequence": [...]
    }
  ]
}
```

**Hybrid Item** (has both):
```json
{
  "id": "refresh_folder",
  "label": "Monitoring",
  "sequence": [
    {"scenario": "refresh_status", "name": "Refresh"}
  ],
  "submenu": [...]
}
```
Clicking executes sequence, then opens submenu.

### Item Properties

#### `id` (string, required)

**Purpose**: Unique identifier for the item

**Rules**:
- Must be unique across entire menu tree
- Use lowercase, numbers, underscores: `a-z`, `0-9`, `_`
- No spaces or special characters
- Length: 3-50 characters

**Used For**:
- State persistence (remembering sequence position)
- Recursive item search in trigger bus

**Examples**:
- Good: `"docker_nextcloud"`, `"server_1"`, `"backup_daily"`
- Bad: `"Docker-Nextcloud"`, `"server #1"`, `"backup daily"`

#### `label` (string, required)

**Purpose**: Text shown on OLED display

**Rules**:
- Max 21 characters (display width limitation)
- Can include spaces and special characters
- Longer text truncated with `~` (e.g., `Very Long Label Name~`)

**Examples**:
- `"Docker Service"`
- `"🔒 Lock Screen"`
- `"Backup → Cloud"`

#### `sequence` (array, optional)

**Purpose**: Defines actions executed on click

**Format**: Array of sequence entries

**Sequence Entry Formats**:

**Simple Format** (string):
```json
"sequence": ["scenario_name"]
```
Display name = scenario name

**Detailed Format** (object):
```json
"sequence": [
  {
    "scenario": "scenario_name",
    "name": "Display Name"
  }
]
```
Custom display name for next action preview

**Toggle Pattern** (multiple entries):
```json
"sequence": [
  {"scenario": "service_stop", "name": "Stop"},
  {"scenario": "service_start", "name": "Start"}
]
```
Clicking cycles through: Stop → Start → Stop → ...

**Multi-Action Pattern**:
```json
"sequence": [
  {"scenario": "service_stop", "name": "Stop"},
  {"scenario": "service_start", "name": "Start"},
  {"scenario": "service_restart", "name": "Restart"},
  {"scenario": "service_status", "name": "Status"}
]
```
Cycles through all actions: Stop → Start → Restart → Status → Stop → ...

#### `submenu` (array, optional)

**Purpose**: Nested menu items (folder contents)

**Format**: Array of menu items (same schema as parent)

**Nesting**: Theoretically unlimited, practically 2-4 levels recommended

**Example**:
```json
{
  "id": "servers",
  "label": "Servers",
  "submenu": [
    {
      "id": "web",
      "label": "Web Server",
      "sequence": [...]
    },
    {
      "id": "database",
      "label": "Database",
      "submenu": [
        {
          "id": "mysql",
          "label": "MySQL",
          "sequence": [...]
        }
      ]
    }
  ]
}
```

### Navigation Behavior

**Rotation**:
- Right → Next item (wraps to first)
- Left → Previous item (wraps to last)

**Click**:
- Action item → Execute sequence
- Folder item → Enter submenu
- Hybrid item → Execute, then enter submenu

**Long Press** (≥1 second):
- Navigate back to parent menu
- At root → Show status message

---

## Scenarios Section

### Purpose

Maps scenario names to command sequences.

### Schema

```json
"scenarios": {
  "scenario_name": [
    {
      "action": "string",    // Action type
      // ...action-specific parameters
    }
  ]
}
```

### Action Types

#### 1. `type` — Type Text

**Purpose**: Types a string character by character

**Parameters**:
- `value` (string, required) — Text to type

**Example**:
```json
{"action": "type", "value": "docker-compose restart"}
```

**Behavior**:
- Types one character at a time
- Speed: ~50ms per character
- Respects keyboard layout (US layout used)

**Use Cases**:
- Terminal commands
- Passwords (insecure, use with caution)
- Text input automation

#### 2. `key` — Press Key Combination

**Purpose**: Presses one or more keys simultaneously

**Parameters**:
- `combo` (string, required) — Key combination with `+` separator

**Example**:
```json
{"action": "key", "combo": "ctrl+c"}
```

**Supported Modifiers**:
- `ctrl` — Control key
- `alt` — Alt key
- `shift` — Shift key
- `super` or `win` — Windows/Command key

**Supported Keys**:
- Letters: `a-z`
- Numbers: `0-9`
- Function keys: `f1-f12`
- Special: `enter`, `escape`, `space`, `tab`, `backspace`, `delete`
- Arrows: `up`, `down`, `left`, `right`

**Combination Examples**:
```json
{"action": "key", "combo": "super+l"}          // Lock screen (Windows)
{"action": "key", "combo": "ctrl+alt+delete"}  // Task manager
{"action": "key", "combo": "alt+f4"}           // Close window
{"action": "key", "combo": "ctrl+shift+esc"}   // Task manager direct
```

**Behavior**:
- All keys pressed simultaneously
- Released after ~50ms
- Case-insensitive combo string

#### 3. `wait` — Pause Execution

**Purpose**: Delays next action by specified milliseconds

**Parameters**:
- `ms` (number, required) — Milliseconds to wait

**Example**:
```json
{"action": "wait", "ms": 1000}
```

**Typical Values**:
- `100-200` ms — Between rapid commands
- `500-1000` ms — Wait for prompts to appear
- `2000-5000` ms — Wait for services to start

**Use Cases**:
- Wait for terminal prompt
- Wait for application to open
- Delay before typing password
- Service startup time

#### 4. `enter` — Press Enter Key

**Purpose**: Presses Enter key one or more times

**Parameters**:
- `count` (number, required) — Number of times to press (1-10)

**Example**:
```json
{"action": "enter", "count": 3}
```

**Behavior**:
- Presses Enter `count` times
- 50ms delay between presses
- Useful for clearing terminal or skipping prompts

**Use Cases**:
- Clear terminal scrollback: `count: 3`
- Skip confirmation prompts: `count: 2`
- Submit form: `count: 1`

### Complete Scenario Examples

**Docker Service Control**:
```json
"scenario_docker_restart": [
  {"action": "enter", "count": 3},
  {"action": "wait", "ms": 200},
  {"action": "type", "value": "cd /opt/myapp && docker-compose restart"},
  {"action": "key", "combo": "enter"}
]
```

**Lock Screen**:
```json
"scenario_lock": [
  {"action": "key", "combo": "super+l"}
]
```

**Safe Shutdown**:
```json
"scenario_shutdown": [
  {"action": "enter", "count": 3},
  {"action": "wait", "ms": 1000},
  {"action": "type", "value": "sudo shutdown -h now"},
  {"action": "key", "combo": "enter"}
]
```

**Complex Multi-Step**:
```json
"scenario_backup": [
  {"action": "enter", "count": 3},
  {"action": "type", "value": "cd /backups"},
  {"action": "key", "combo": "enter"},
  {"action": "wait", "ms": 500},
  {"action": "type", "value": "bash backup.sh"},
  {"action": "key", "combo": "enter"},
  {"action": "wait", "ms": 2000},
  {"action": "type", "value": "echo 'Backup complete'"},
  {"action": "key", "combo": "enter"}
]
```

---

## State Persistence

### state.json Structure

**Auto-generated file** (do not edit manually):

```json
{
  "menu_cursor": 2,
  "seq_positions": {
    "docker_service": 1,
    "n8n_service": 0
  }
}
```

### Properties

#### `menu_cursor` (number)

Current menu item index (0-based)

**Saved**: On every encoder rotation  
**Restored**: On boot  
**Scope**: Top-level menu only (not submenu positions)

#### `seq_positions` (object)

Tracks current position in each item's sequence

**Key**: Item ID  
**Value**: Current index in sequence array (0-based)

**Saved**: After scenario execution  
**Restored**: On boot  
**Behavior**: Allows toggle pattern to remember state across reboots

**Example**:
```json
"seq_positions": {
  "docker_app": 1
}
```
Means: Next click executes `sequence[1]` (e.g., "Start" if Stop was last)

### File Writes

**Normal Mode** (GP24 not held during boot):
- File system writable from code
- `state.json` auto-created and updated
- USB drive read-only

**Development Mode** (GP24 held during boot):
- File system read-only from code
- `state.json` changes not saved
- USB drive writable for editing files

---

## Validation Rules

### Config Studio Validation

The web editor validates:

1. **JSON Syntax** — Valid JSON format
2. **Required Sections** — All 5 sections present
3. **Pin Ranges** — GPIO pins 0-29
4. **Unique IDs** — No duplicate item IDs
5. **Scenario References** — Scenarios exist in `scenarios` section
6. **Sensor References** — Hall sensor IDs match bindings

### Runtime Validation

Code performs:

1. **File Exists** — `config.json` present
2. **JSON Parse** — Valid JSON structure
3. **Graceful Degradation** — Missing optional fields use defaults

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named adafruit_*` | Missing libraries | Install libraries in `lib/` |
| `Invalid JSON` | Syntax error | Use editor validator |
| `Scenario not found` | Typo in scenario name | Verify name matches exactly |
| `Pin * already in use` | Duplicate pin | Assign unique pins |
| State not saving | Wrong boot mode | Boot without GP24 held |

---

## Best Practices

### Organization

**Group Related Items**:
```json
"active_menu": [
  {
    "id": "services_folder",
    "label": "Services",
    "submenu": [
      {"id": "docker", "label": "Docker", "sequence": [...]},
      {"id": "nginx", "label": "Nginx", "sequence": [...]}
    ]
  }
]
```

**Use Descriptive IDs**:
- Good: `"nextcloud_restart"`, `"backup_daily"`
- Bad: `"item1"`, `"test"`, `"x"`

### Naming Conventions

**IDs**: `lowercase_with_underscores`  
**Labels**: `Title Case` or `Sentence case`  
**Scenarios**: `scenario_descriptive_name`

### Scenario Design

**Always Clear Terminal First**:
```json
{"action": "enter", "count": 3}
```

**Add Waits After Commands**:
```json
{"action": "key", "combo": "enter"},
{"action": "wait", "ms": 500}
```

**Use Absolute Paths**:
```json
{"action": "type", "value": "cd /opt/app && docker-compose restart"}
```
Avoid relying on current directory.

**Test Commands Manually First**:
Before adding to scenario, verify command works in terminal.

### Security

**Avoid Plaintext Passwords**:
```json
// BAD:
{"action": "type", "value": "password123"}

// BETTER:
// Use SSH keys, sudo NOPASSWD, or keyring integration
```

**Limit Emergency Trigger Scope**:
Hall sensors bypass cooldown — bind only to safe scenarios:
```json
"passive": {
  "hall_sensor_1": "scenario_safe_shutdown"  // OK
  // NOT: "scenario_delete_all_data"  // Too dangerous
}
```

### Performance

**Limit Scenario Length**:
- Max 10-15 steps per scenario
- Long scenarios block input processing
- Split complex workflows into multiple menu items

**Optimize Wait Times**:
- Don't wait longer than necessary
- Test minimum required delays

### Backup

**Version Control**:
```bash
git add config.json
git commit -m "Add Nextcloud service control"
```

**Keep Working Copies**:
```bash
cp config.json config.backup.json
```

**Document Changes**:
Use git commit messages to track what changed and why.

---

## Examples

### Minimal Configuration

```json
{
  "hardware": {
    "hall_sensors": [],
    "button_pin": 24,
    "led_pin": 25,
    "encoder_clk": 6,
    "encoder_dt": 7,
    "encoder_sw": 8,
    "display_sda": 4,
    "display_scl": 5
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
      "sequence": [
        {"scenario": "say_hello", "name": "Run"}
      ]
    }
  ],
  "scenarios": {
    "say_hello": [
      {"action": "type", "value": "echo Hello, World!"},
      {"action": "key", "combo": "enter"}
    ]
  }
}
```

### Homelab Configuration

```json
{
  "hardware": {
    "hall_sensors": [
      {"id": "hall_sensor_1", "pin": 15, "active_low": true}
    ],
    "button_pin": 24,
    "led_pin": 25,
    "encoder_clk": 6,
    "encoder_dt": 7,
    "encoder_sw": 8,
    "display_sda": 4,
    "display_scl": 5
  },
  "device": {
    "armed": true,
    "debounce_ms": 300,
    "cooldown_ms": 5000,
    "screen_timeout_s": 30,
    "screensaver": "tesseract"
  },
  "passive": {
    "hall_sensor_1": "scenario_emergency_shutdown",
    "btn_double": "scenario_lock"
  },
  "active_menu": [
    {
      "id": "nextcloud",
      "label": "Nextcloud",
      "sequence": [
        {"scenario": "nextcloud_stop", "name": "Stop"},
        {"scenario": "nextcloud_start", "name": "Start"}
      ]
    },
    {
      "id": "monitoring",
      "label": "Monitoring",
      "submenu": [
        {
          "id": "grafana",
          "label": "Grafana",
          "sequence": [
            {"scenario": "grafana_stop", "name": "Stop"},
            {"scenario": "grafana_start", "name": "Start"}
          ]
        },
        {
          "id": "prometheus",
          "label": "Prometheus",
          "sequence": [
            {"scenario": "prometheus_stop", "name": "Stop"},
            {"scenario": "prometheus_start", "name": "Start"}
          ]
        }
      ]
    }
  ],
  "scenarios": {
    "nextcloud_stop": [
      {"action": "enter", "count": 3},
      {"action": "wait", "ms": 200},
      {"action": "type", "value": "cd /opt/nextcloud && docker-compose stop"},
      {"action": "key", "combo": "enter"}
    ],
    "nextcloud_start": [
      {"action": "enter", "count": 3},
      {"action": "wait", "ms": 200},
      {"action": "type", "value": "cd /opt/nextcloud && docker-compose start"},
      {"action": "key", "combo": "enter"}
    ],
    "grafana_stop": [
      {"action": "enter", "count": 3},
      {"action": "type", "value": "sudo systemctl stop grafana-server"},
      {"action": "key", "combo": "enter"}
    ],
    "grafana_start": [
      {"action": "enter", "count": 3},
      {"action": "type", "value": "sudo systemctl start grafana-server"},
      {"action": "key", "combo": "enter"}
    ],
    "prometheus_stop": [
      {"action": "enter", "count": 3},
      {"action": "type", "value": "sudo systemctl stop prometheus"},
      {"action": "key", "combo": "enter"}
    ],
    "prometheus_start": [
      {"action": "enter", "count": 3},
      {"action": "type", "value": "sudo systemctl start prometheus"},
      {"action": "key", "combo": "enter"}
    ],
    "scenario_emergency_shutdown": [
      {"action": "enter", "count": 3},
      {"action": "wait", "ms": 1000},
      {"action": "type", "value": "sudo shutdown -h now"},
      {"action": "key", "combo": "enter"}
    ],
    "scenario_lock": [
      {"action": "key", "combo": "super+l"}
    ]
  }
}
```

---

## Related Documentation

- [Config Editor Guide](config-editor.md) — Visual configuration tool
- [Quick Start](../../QUICK_START.md) — Getting started guide
- [Architecture](../developers/architecture.md) — Technical details

---

## Troubleshooting

### Config Not Loading

**Symptom**: Device boots but shows errors

**Check**:
1. Verify `config.json` exists on CIRCUITPY root
2. Validate JSON syntax (use Config Studio editor)
3. Check serial console for error messages

### Scenarios Don't Execute

**Symptom**: Click encoder, nothing happens

**Check**:
1. Verify scenario name in sequence matches `scenarios` section (case-sensitive)
2. Check USB connected (LED blinks on boot)
3. Wait for cooldown to expire (5 seconds default)
4. Check serial console: `[bus] DROP — cooldown` or busy message

### State Not Saving

**Symptom**: Menu position resets on reboot

**Check**:
1. Boot in Normal Mode (don't hold GP24 button)
2. Verify CIRCUITPY drive writable from code
3. Check `state.json` exists and updates

### Hall Sensors Not Working

**Symptom**: Sensor triggers don't execute

**Check**:
1. `device.armed` is `true`
2. Sensor ID in `passive` matches `hardware.hall_sensors[].id`
3. Verify sensor wiring and `active_low` setting
4. Check serial console for trigger messages

---

**Last Updated**: 2024  
**Config Version**: 1.0  
**Compatible with**: Pico Commander 1.0+
