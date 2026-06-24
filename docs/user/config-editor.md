# Config Studio User Guide

## Overview

The Config Studio (`editor.html`) is a web-based graphical editor for managing Pico Commander's `config.json` file. It provides a visual interface to configure hardware pins, define input sensors and output targets, build menu hierarchies, create automation scenarios, and manage device behavior without manual JSON editing.

**Target Users**: Anyone who needs to configure Pico Commander for custom workflows, including system administrators, DevOps engineers, and homelab enthusiasts.

---

## Features

### Core Capabilities

- **Visual Menu Builder** — Drag-and-drop interface for organizing menu items and folders.
- **Scenario Editor** — Step-by-step automation sequence builder with toolboxes for different output types (HID, GPIO).
- **Hardware Configuration** — Pin assignment management for UI components, sensors, and outputs.
- **Unified Pipeline Management** — Configure `loop` modes and multiple scenarios for both menu items and passive triggers.
- **Raw JSON Editor** — Direct JSON editing with validation and auto-sync.
- **Configuration Validation** — Automatic checks for common configuration errors.
- **Backward Compatibility** — Automatically migrates older `config.json` formats to the modern structure upon loading.

---

## Getting Started

### Opening the Editor

1. Locate `editor.html` in the Pico Commander project directory.
2. Open the file in a modern web browser (Chrome, Firefox, Edge, or Safari).
3. The editor loads with a default configuration skeleton.

**Note**: This is a client-side application. All data remains in your browser until you explicitly save the configuration file.

### Loading Configuration

**Method 1: Import existing file**
1. Click **"Load config.json"** in the header.
2. Select your `config.json` file from the file picker.
3. The configuration loads automatically into all panels. If your file uses the legacy format (e.g., sensors in `hardware.hall_sensors`), the editor will automatically run `migrateToInputsFormat()` to convert it to the new `inputs` structure without data loss.

**Method 2: Start from scratch**
- The editor initializes with a minimal working configuration.
- Customize settings and build your menu structure.
- Save when ready.

---

## Interface Layout

### Header Bar
- **Pico Config Studio** branding with "PICO" badge.
- **Load config.json** button — Import configuration file.
- **Save config.json** button — Export configuration with validation.

### Left Sidebar (5 Sections)

1. **Device Configuration**
   - Global settings: Armed state, Debounce (ms), Cooldown (ms), Screen Timeout (s), Screensaver selection.
2. **Hardware Pins Configuration**
   - UI and system pins: Encoder (CLK, DT, SW), Button Pin, LED Pin, Display I2C (SDA, SCL).
3. **Inputs**
   - **Hall Sensors**: List of configured Hall sensors (ID, Pin, Active Low checkbox). Includes a "+ Add" button.
   - **Power Monitor**: Configuration for the INA226 module (Enabled, Trigger Mode, Thresholds, Cooldowns, I2C settings, Warning/Splash screen timings).
4. **Outputs Configuration**
   - **HID**: Configuration for the USB Keyboard output.
   - **GPIO**: Cards for each digital output pin. Includes pin number, Active High checkbox, Label, and a "Default Scenario" quick-link. Also contains the **Auto-Boot** subsection (enabled, interval, attempts, cooldown). Includes a "+ GPIO" button to add more outputs.
5. **Passive Sensors triggers**
   - Bindings for hardware events (Hall sensors, Power Monitor, Button Double Click).
   - Features the **Loop mode** checkbox and the Pipeline builder (see *Understanding Loop Mode* below).

### Main Workspace (3 Tabs)
- **Menu Hierarchy** — Visual menu structure editor.
- **Scenarios Editor** — Automation step builder with output-specific toolboxes.
- **Raw JSON View** — Direct configuration editing.

### Right Sidebar: Inspector
- Context-sensitive panel that appears when you click a menu item in the Menu Hierarchy tab. Allows editing item properties, pipelines, and nested contents.

---

## Tab 1: Menu Hierarchy

### Menu Structure Overview

The menu hierarchy defines what appears on the Pico Commander's OLED display. Users navigate this menu using the rotary encoder.

### Item Properties (Inspector)

Click any menu item to open the inspector on the right:

| Field | Description | Required |
|-------|-------------|----------|
| **Item ID** | Unique identifier (use `a-z`, `0-9`, `_` only) | Yes |
| **Display Label** | Text shown on OLED display (max 21 chars) | Yes |
| **Item Type** | Radio toggle: Action or Folder | Yes |

### Building Pipelines

Both Action items (in the Inspector) and Passive triggers (in the left sidebar) use the **Pipeline** builder to define what scenarios execute when triggered.

**Understanding Loop Mode:**
Every pipeline has a **"Loop mode"** checkbox with a tooltip:
> *"ON: one trigger = one scenario (cycles). OFF: one trigger = all scenarios at once"*

- **Loop ON (Toggle Pattern)**: If you add "Stop" and "Start" scenarios, the first click runs "Stop". The second click runs "Start". It remembers its position.
- **Loop OFF (Chain/One-Shot Pattern)**: The trigger executes all scenarios in the list at once.

**Adding Scenarios to a Pipeline:**
1. Click the **"+ Add"** button.
2. Select a scenario from the dropdown.
3. Provide a Display Label (shown on the OLED screen as the "Next Action" hint).
4. **Constraint**: If Loop mode is OFF and you already have one scenario in the list, the "+ Add" button is **disabled** to prevent UI complexity. (To build multi-scenario loop:false chains, use the Raw JSON tab).

### Organizing with Drag & Drop

- **Reorder items**: Drag by the title area to change order.
- **Move between folders**: Drag items into folder submenus.
- **Nested dragging**: Works at any depth level.

### Folders and Hybrid Items

If an item is set to "Folder", the Inspector shows an **"Add inside this folder"** block with "+ Action" and "+ Folder" buttons. 

If an item has both a pipeline and sub-items, it acts as a **Hybrid Item**: clicking it will execute the pipeline and *then* open the folder.

---

## Tab 2: Scenarios Editor

### Scenario Structure

Scenarios are automation sequences that execute when triggered. Each scenario consists of ordered steps, and each step targets a specific Output.

### Creating and Managing Scenarios

1. Click **"+ Add Scenario"** at the bottom of the left list.
2. **"Choose Output Type" Modal**: A popup will ask you to select the primary output type for this scenario (HID or GPIO). This determines which toolbox is shown.
3. Enter a unique scenario name.
4. Click a scenario to edit its steps, or use the search box to filter.

### Step Toolboxes

Depending on the output type chosen, you will see different step buttons:

**HID Toolbox:**
- **Type text**: Types a string of text.
- **KeyPress combo**: Presses a key combination (e.g., `ctrl+c`, `super+l`).
- **Wait MS**: Pauses execution.
- **Press Enter**: Presses the Enter key `count` times.

**GPIO Toolbox:**
- **GPIO Pulse**: Sends a quick 250ms pulse (like a button press).
- **GPIO Set**: Forces the pin to an absolute HIGH or LOW state.
- **GPIO Hold**: Holds the active state for a specified duration.
- **Wait MS**: Pauses execution.

### Step Configuration

If your project has multiple outputs of the same type (e.g., two GPIO outputs), each step will have an **Output target dropdown** allowing you to select exactly which pin should execute the action.

### Reordering and Deleting Steps
- Drag steps by their left handle to reorder.
- Click the **×** button on the right side to delete.

---

## Tab 3: Raw JSON View

For advanced users who prefer direct JSON editing or need to configure complex features (like multi-step `loop: false` pipelines).

### Features
- Syntax-highlighted JSON editor.
- Real-time synchronization with the visual tabs.
- Keyboard shortcut: **Ctrl+S** to apply changes.

### Workflow
1. Switch to **Raw JSON View** tab.
2. Edit the JSON structure directly.
3. Click **"Apply Changes"** or press **Ctrl+S**.
4. The editor parses the JSON and updates the UI tabs automatically.

---

## Technical Details

### File Format (7-Section Schema)

The editor produces standard `config.json` files matching the modern unified architecture:

```json
{
  "hardware": { /* Basic UI/system pins */ },
  "inputs": { /* Hall sensors, INA226 */ },
  "outputs": { /* HID, GPIO configurations */ },
  "device": { /* Timeouts, cooldowns */ },
  "passive": { /* Sensor -> Pipeline bindings */ },
  "active_menu": [ /* Menu hierarchy */ ],
  "scenarios": { /* Scenario definitions */ }
}
```

### Backward Compatibility
When loading a `config.json`, the editor automatically runs `migrateToInputsFormat()`. This detects older files that stored sensors in `hardware.hall_sensors` or `hardware.ina226` and safely moves them to the new `inputs` dictionary. 

---

## Configuration Validation

The editor performs automatic validation when saving or switching tabs. Look for the yellow warning banner at the top of the screen.

### Common Validation Messages

| Warning | Fix |
|---------|-----|
| `Empty label for menu item` | Provide a display label in the Inspector. |
| `Missing ID for menu item` | Provide a unique ID in the Inspector. |
| `Duplicate item ID: [id]` | Ensure all menu items have strictly unique IDs. |
| `Empty scenario name` | Provide a name for the scenario in the Scenarios tab. |
| `Duplicate scenario name: [name]` | Rename one of the scenarios. |
| `Pipeline references missing scenario: [name]` | Ensure the scenario selected in the pipeline actually exists. |
| `Empty text to type` | Add text to the Type step. |
| `Empty key combination` | Add a valid combo (e.g., `ctrl+c`) to the KeyPress step. |
| `Invalid wait time` | Ensure Wait MS is a positive number. |
| `Output type not determined` | Add at least one step with a selected output to enable filtering. |
| `Auto-Boot is enabled on multiple outputs` | Disable Auto-Boot on all but one GPIO output. |

---

## Workflow Examples

### Example 1: Add a PC Power Button (GPIO)

1. **Configure Output**:
   - Go to the **Outputs Configuration** sidebar.
   - Click **"+ GPIO"**.
   - Set Pin to `14`, Label to `PC Power`, and ensure Active High is checked.
   - Click the "Create default scenario" link. This auto-generates `scenario_gpio_14_pulse`.
2. **Create Menu Item**:
   - Go to the **Menu Hierarchy** tab.
   - Click **"+ Add Root Action"**.
   - Set ID to `boot_pc`, Label to `Boot PC`.
   - In the Pipeline section, ensure Loop mode is **OFF**.
   - Click **"+ Add"**, select `scenario_gpio_14_pulse`, and set the label to `Power`.
3. **Save**: Click **"Save config.json"**.

### Example 2: Emergency Shutdown via Hall Sensor

1. **Configure Input**:
   - In the **Inputs** sidebar, under Hall Sensors, click **"+ Add"**.
   - Set ID to `case_door`, Pin to `15`, Active Low to checked.
2. **Create Scenario**:
   - Go to the **Scenarios Editor** tab.
   - Click **"+ Add Scenario"**, choose **HID** output type.
   - Name it `safe_shutdown`.
   - Add steps: Press Enter (count: 3) → Wait (1000ms) → Type (`sudo shutdown -h now`) → KeyPress (`enter`).
3. **Bind Trigger**:
   - In the left sidebar, find **Passive Sensors triggers**.
   - Locate the `case_door` card.
   - Set Loop mode to **OFF**.
   - Click **"+ Add"** and select the `safe_shutdown` scenario.
4. **Save**: Click **"Save config.json"**.

---

## FAQ

**Q: Can I edit config.json directly instead of using the editor?**  
A: Yes. The editor is a convenience tool. Manual JSON editing works perfectly, and the editor's Raw JSON tab makes this easy.

**Q: Does the editor validate scenario command syntax?**  
A: No. The editor checks JSON structure and field presence, but cannot validate if shell commands (like `docker-compose`) will actually work on your target system.

**Q: Why is the "+ Add" button disabled in my pipeline?**  
A: If Loop mode is OFF, the UI restricts you to a single scenario to prevent visual clutter. If you absolutely need a multi-scenario `loop: false` chain, you can build it in the Raw JSON tab.

**Q: Can I share configurations between devices?**  
A: Yes. Save `config.json` and copy to other Pico Commander devices. Ensure hardware pin assignments match the physical wiring.

---

## Support

For issues, feature requests, or questions:

- **Documentation**: See project README and inline code comments.
- **GitHub Issues**: Report bugs or request features via project repository.

---

**Last Updated**: 2026-06-24  
**Compatible with Architecture**: Unified Pipeline, Inputs, and Outputs Engine
