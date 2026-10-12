# Changelog

All notable changes to Pico Commander will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses Semantic Versioning-like numbering.

---

## [2.3.0]

### Added

- **Geometric menu render mode**: New `device.display_mode` config option ("text" or "geometric"). Geometric mode displays the root menu as shapes instead of labels: 6 slots per page with forms rotating by page number (square, triangle, circle, diamond). Selected item is filled and larger (28px), others are outlined (16px). Features include time-based animations (grow/shrink 140ms, slide 180ms), non-circular navigation with bump animation at edges (6px push + spring back in 160ms, 2px wall indicator), and automatic fail-safe fallback to text mode on errors. Submenus and status screens remain text-based. Config Studio includes a "Display Render Mode" selector in Device Configuration section. Rendering optimized with `bitmaptools.fill_region` and single-refresh frames to minimize flicker.

- **Encoder Control menu item type** (`"type": "encoder_control"`): a fourth `active_menu` item type that puts the encoder into a direct-input mode instead of navigating the menu. Two output modes:
  - `output_mode: "mouse"` — fixed scroll (rotate) + right-click (press), dispatched directly through `trigger_bus.execute_output("mouse", ...)`, bypassing cooldown/busy, same pattern as `TrackballInput`.
  - `output_mode: "scenario"` — `on_rotate_right`/`on_rotate_left`/`on_click` arrays of scenario names, each run via `execute_pipeline(..., priority=PRIORITY_HIGH)` with `loop` forced `False`.
  - `scroll` action added to `output_mouse.py` (`{"action": "scroll", "wheel": N}`), using `adafruit_hid.mouse.Mouse.move(wheel=...)`.
  - New `display.show_encoder_control()` method; `wake_up_display()` made mode-aware so it redraws the control view instead of the menu if the mode is still active on screen wake.
  - Config Studio (`editor.html`): new "Direct Control" item type across all creation entry points (toolbar, context menu, folder "+" buttons), inspector panel with Mouse/Scenario toggle and three scenario-list editors (add/reorder/delete), tree badge, and two-way type-conversion field cleanup.
  - Developer docs: [Encoder Control Mode](developers/active-triggers.md#encoder-control-mode). User docs: `active_menu` Item Types, new Mouse Output section, Config Studio Direct Control guide.

### Fixed

- `editor.html`: `serializeMenuTree()` did not recognize `"type": "encoder_control"` and silently downgraded such items to plain actions (losing `output_mode`/`on_rotate_*`/`on_click`) on any unrelated tree change that triggered `saveAndSyncMenu()` (20+ call sites — drag-and-drop, label edits, deleting any other item, etc.). Added an explicit `encoder_control` branch, checked before the folder/action branches.

---

## [2.2.0]

### Added

- **Mouse output handler** (`output_mouse.py`): Adds mouse movement and button click emulation to the output pipeline.
- **Serial output handler** (`output_serial.py`): Support for sending custom string payloads via USB Serial interface.
- **Host listener utility** (`pico-host/serial_listener_simple.py`): Lightweight serial listener script for processing incoming host events.
- Developer documentation for new inputs (`docs/developers/inputs.md`) and outputs (`docs/developers/outputs.md`).

### Changed

- **Web Config Studio** (`editor.html`): Major UI redesign and visual editor updates for pipeline and device configuration.
- **Inputs Manager** (`inputs_manager.py`): Extended input handling architecture and state management logic.
- Updated configuration schemas (`config.py`, `config.json`) to support mouse and serial output parameters.

---

## [2.1.0] — Power Monitor State Machine Refactor

### Changed

- `PowerMonitorInput` rewritten as state machine: `MONITORING → TRIGGERED → SUSPENDED → SUSPENDED_WAITING`
- Removed fields `cooldown_sec` and `cancel_cooldown_sec`
- Added fields `recovery_offset_percent`, `trigger_attempts`, `trigger_attempt_interval_sec`
- USB-gating: shutdown trigger fires only when USB is connected (server is running)
- Auto-boot blocked (`blocks_auto_boot`) while system is in SUSPENDED state
- Auto-boot limited to 60-second grace period after Pico startup
- Pico starting with low battery % and no USB connection now starts directly in SUSPENDED state

### Added

- State transition logging to `/power_monitor.log` with 20KB rotation
- Initial state detection in `__init__` — determines startup state based on actual metrics

### Migration

- Remove `cooldown_sec` and `cancel_cooldown_sec` from `config.json`
- Add `recovery_offset_percent: 10`, `trigger_attempts: 3`, `trigger_attempt_interval_sec: 60`

---

## [2.0.0] — Input/Output Architecture Rewrite

Major architectural refactoring to support extensible typed inputs and outputs with unified pipeline execution engine.

### Added

- **Typed `inputs{}` configuration layer** with extensible input handlers:
  - `hall` input type for Hall effect sensors (replaces `hardware.hall_sensors[]`)
  - `power_monitor` input type for INA226 battery monitoring (replaces `hardware.ina226{}`)
  - New `InputsManager` class (`inputs_manager.py`) with unified sensor management
  - Support for per-sensor `active_low` configuration

- **Typed `outputs{}` configuration layer** with modular output handlers:
  - `hid` output type for USB keyboard emulation (`output_hid.py`)
  - `gpio` output type for relay/optocoupler control (`output_gpio.py`)
  - Base class `OutputHandler` (`output_base.py`) for extensibility
  - New `OutputsManager` in `trigger_bus.py` for centralized output execution

- **Unified pipeline execution engine**:
  - `pipeline` and `loop` configuration format for both active (menu) and passive (sensor) triggers
  - Scenario steps now include `"output"` field (defaults to `"hid"` for backward compatibility)
  - Shared execution logic between `active_menu` and `passive` triggers
  - Support for multi-output scenarios (can target different outputs in same sequence)

- **GPIO output features**:
  - `active_high` support for inverted logic (active-low relays, optocouplers)
  - New actions: `gpio_pulse`, `gpio_set`, `gpio_hold`
  - `auto_boot` feature: automatic GPIO pulse on boot when USB host not detected
    - Configurable check interval, max attempts, and retry cooldown
    - USB detection-based triggering
    - Boot-time server power management

- **Power monitoring enhancements**:
  - INA226 battery metrics with voltage/current tracking
  - Low-battery warning screen with encoder dismiss and cooldown protection
  - Splash screen HUD during screensaver with animated battery percentage count-up
  - Configurable warning thresholds and splash intervals
  - `cancel_trigger()` and `dismiss_warning()` API for user interaction

- **Configuration validation and tooling**:
  - Web-based Config Studio (`editor.html`) with visual editor
  - Drag-and-drop menu builder and scenario editor
  - Real-time validation and JSON import/export

### Changed

- **Configuration schema migration**:
  - Moved Hall sensor configuration from `hardware.hall_sensors[]` to `inputs.<id>{type: "hall"}`
  - Moved INA226 configuration from `hardware.ina226{}` to `inputs.ina226{type: "power_monitor"}`
  - Legacy paths still read for backward compatibility but not recommended

- **Scenario execution**:
  - Scenario steps now processed through `OutputsManager` instead of direct HID calls
  - `"output"` field in scenario steps determines target handler (defaults to `"hid"`)
  - `trigger_bus.fire_active()` now supports multi-output pipelines

- **GPIO implementation**:
  - `gpio_pulse` and `gpio_hold` now honor `active_high` flag for correct logical activation
  - `gpio_set` intentionally remains raw/low-level control (ignores `active_high`)
  - Initialization and cleanup now respect inactive state based on `active_high`

### Fixed

- INA226 screen components (`splash_screen.py`, `warning_screen.py`) now correctly read configuration from `inputs.ina226` instead of deprecated `hardware.ina226` path
- Config Studio title changed from "Pico Macro Pad" to "Pico Commander" for branding consistency
- GPIO outputs now properly apply `active_high` inversion in activation logic (previously always drove literal HIGH/LOW)

### Deprecated

- Legacy `"sequence"` format on `active_menu` items (use `"pipeline"` instead)
- Configuration paths `hardware.hall_sensors[]` and `hardware.ina226{}` (migrate to `inputs.<id>`)

### Removed

- `passive.py` module — superseded by `inputs_manager.py` unified architecture
  - All passive sensor logic (Hall, button, INA226) now handled through typed input handlers
  - Backward compatibility alias `PassiveHandler = InputsManager` maintained

---

## Maintaining this changelog

When making significant changes (new input/output types, config schema modifications, breaking pipeline changes, or new hardware features), add an entry here **before** the release, not post-factum. Group changes under appropriate categories: Added, Changed, Deprecated, Removed, Fixed, or Security.

## [Unreleased — previous]
### Changed files:
 CHANGELOG.md               |   3 +
 README.md                  |   2 +-
 boot.py                    |   5 +-
 code.py                    |  44 ++-
 config.json                |  35 +-
 config.py                  |  62 ++++
 display.py                 |  92 ++---
 docs/developers/inputs.md  |  20 ++
 docs/developers/outputs.md |  69 +++-
 editor.html                | 839 ++++++++++++++++++++++++++++++++++++++++-----
 inputs_manager.py          | 158 ++++++++-
 screensaver.py             |   8 +-
 trigger_bus.py             |  14 +-
 13 files changed, 1193 insertions(+), 158 deletions(-)
