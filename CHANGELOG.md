# Changelog

All notable changes to Pico Commander will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses Semantic Versioning-like numbering.

---

## [Unreleased] — Input/Output Architecture Rewrite

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
