# Config Editor User Guide

## Overview

The Config Studio is a web-based graphical editor for managing Pico Commander's `config.json` file. It provides a visual interface to configure hardware pins, define menu hierarchies, create automation scenarios, and manage device behavior without manual JSON editing.

**Target Users**: Anyone who needs to configure Pico Commander for custom workflows, including system administrators, DevOps engineers, and homelab enthusiasts.

---

## Features

### Core Capabilities

- **Visual Menu Builder** — Drag-and-drop interface for organizing menu items and folders
- **Scenario Editor** — Step-by-step automation sequence builder with toolbox
- **Hardware Configuration** — Pin assignment management for all connected components
- **Device Settings** — Configure timeouts, debounce, cooldown, and screensaver options
- **Raw JSON Editor** — Direct JSON editing with validation for advanced users
- **Configuration Validation** — Automatic checks for common configuration errors
- **Import/Export** — Load existing `config.json` files and save modified versions

---

## Getting Started

### Opening the Editor

1. Locate `editor.html` in the Pico Commander project directory
2. Open the file in a modern web browser (Chrome, Firefox, Edge, or Safari)
3. The editor loads with a default configuration skeleton

**Note**: This is a client-side application. All data remains in your browser until you explicitly save the configuration file.

### Loading Configuration

**Method 1: Import existing file**
1. Click **"Load config.json"** in the header
2. Select your `config.json` file from the file picker
3. Configuration loads automatically into all panels

**Method 2: Start from scratch**
- The editor initializes with a minimal working configuration
- Customize settings and build your menu structure
- Save when ready

---

## Interface Layout

### Header Bar
- **Pico Config Studio** branding
- **Load config.json** button — Import configuration file
- **Save config.json** button — Export configuration with validation

### Left Sidebar: Device & Hardware Settings
- Device configuration (armed state, timeouts, cooldown)
- Hardware pin assignments (encoder, display, sensors)
- Hall sensor management
- Passive trigger scenario bindings

### Main Workspace (Tabs)
- **Menu Hierarchy** — Visual menu structure editor
- **Scenarios Editor** — Automation step builder
- **Raw JSON View** — Direct configuration editing

### Right Sidebar: Inspector
- Item properties editor
- Sequence configuration
- Item type toggle (Action/Folder)

---

## Tab 1: Menu Hierarchy

### Menu Structure Overview

The menu hierarchy defines what appears on the Pico Commander's OLED display. Users navigate this menu using the rotary encoder.

**Two Item Types:**
- **Action** — Executes one or more scenarios when clicked
- **Folder** — Contains submenu items (nested navigation)

### Creating Menu Items

**Add Root-Level Items:**
1. Click **"+ Add Root Action"** or **"+ Add Root Folder"**
2. A new item appears in the menu tree
3. Click the item to open the inspector panel

**Add Nested Items:**
1. Select a folder item in the tree
2. In the inspector, use **"+ Action"** or **"+ Folder"** under "Add inside this folder"

### Editing Item Properties

Click any menu item to open the inspector:

| Field | Description | Required |
|-------|-------------|----------|
| **Item ID** | Unique identifier (use `a-z`, `0-9`, `_` only) | Yes |
| **Display Label** | Text shown on OLED display (max 21 chars) | Yes |
| **Item Type** | Action or Folder | Yes |

### Organizing with Drag & Drop

- **Reorder items**: Drag by the title area to change order
- **Move between folders**: Drag items into folder submenus
- **Nested dragging**: Works at any depth level

### Action Sequences

Actions can execute multiple scenarios in sequence (e.g., Stop → Start for service toggling).

**Adding Sequence Steps:**
1. Select an action item
2. In the inspector, click **"+ Add"** under "Action sequence"
3. Configure each sequence entry:
   - **Scenario** — Select from dropdown
   - **Display Name** — Text shown as next action (e.g., "Stop", "Start")

**How Sequences Work:**
- Each click executes the current step
- Automatically advances to the next step
- Loops back to the first step after the last

**Example**: Docker service control
```
Sequence:
1. Scenario: docker_stop, Name: "Stop"
2. Scenario: docker_start, Name: "Start"

User clicks item → Executes stop → Label changes to "Start"
User clicks again → Executes start → Label changes to "Stop"
```

### Context Menu (Right-Click)

Right-click any menu item for quick actions:
- **Inspect** — Open inspector panel
- **Duplicate** — Create a copy
- **Delete** — Remove item
- **Convert to Folder/Action** — Change item type

### Keyboard Shortcuts

- **Delete/Backspace** — Delete selected item (when not in input field)
- **Click item** — Select and inspect

---

## Tab 2: Scenarios Editor

### Scenario Structure

Scenarios are automation sequences that execute when triggered by menu actions, Hall sensors, or button presses. Each scenario consists of ordered steps that simulate keyboard input.

### Scenario List Panel (Left)

**Creating Scenarios:**
1. Click **"+ Add Scenario"** at the bottom
2. Enter a unique scenario name (e.g., `docker_restart`)
3. The scenario appears in the list

**Managing Scenarios:**
- Click a scenario to edit its steps
- Use the search box to filter by name
- Delete button appears when scenario is selected

### Step Types

| Type | Description | Parameters |
|------|-------------|------------|
| **Type text** | Types a string of text | `value` (string) |
| **KeyPress combo** | Presses key combination | `combo` (e.g., "ctrl+c", "super+l") |
| **Wait MS** | Pauses execution | `ms` (milliseconds) |
| **Press Enter** | Presses Enter N times | `count` (number) |

### Building Step Sequences

**Method 1: Click toolbox buttons**
1. Click "Type text", "KeyPress combo", "Wait MS", or "Press Enter"
2. A new step appears in the sequence
3. Fill in the step parameters

**Method 2: Drag from toolbox**
1. Drag a tool button to the steps list
2. Position it where needed
3. Configure parameters

### Step Configuration

**Type Text:**
- Enter the text to type (e.g., `docker-compose up -d`)
- Text is typed exactly as written

**KeyPress Combo:**
- Enter key combination using `+` separator
- Examples: `ctrl+c`, `super+l`, `ctrl+shift+esc`
- Supported modifiers: `ctrl`, `alt`, `shift`, `super`/`win`

**Wait:**
- Enter delay in milliseconds
- Typical range: 100-2000ms
- Use after commands that need time to execute

**Press Enter:**
- Enter repeat count (1-10)
- Useful for skipping prompts or clearing terminal

### Reordering Steps

Drag steps by their type label to reorder within the sequence.

### Deleting Steps

- Click the **×** button on the right side of any step
- Or select a step and press **Ctrl+Delete**

### Example Scenario: Safe Shutdown

```
Scenario: scenario_shutdown
Steps:
1. Press Enter (count: 3)        — Clear terminal
2. Wait (ms: 1000)                — Wait for prompt
3. Type text: "safe_shutdown --now"
4. KeyPress: "enter"              — Execute command
```

---

## Tab 3: Raw JSON View

For advanced users who prefer direct JSON editing.

### Features

- Syntax-highlighted JSON editor
- Real-time validation
- Full configuration access
- Keyboard shortcut: **Ctrl+S** to apply changes

### Workflow

1. Switch to **Raw JSON View** tab
2. Edit the JSON structure directly
3. Click **"Apply Changes"** or use **Ctrl+S**
4. Validation runs automatically
5. Warnings appear if issues are detected

### Common Use Cases

- Bulk operations (copy/paste multiple items)
- Complex nested structures
- Precision editing of numeric values
- Troubleshooting configuration issues

---

## Left Sidebar: Configuration Panels

### Device Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| **Armed** | Enable Hall sensor triggers | `true` |
| **Hall Debounce (ms)** | Anti-bounce delay for Hall sensors | `300` |
| **Cooldown (ms)** | Minimum time between scenario executions | `5000` |
| **Screen Timeout (s)** | Seconds before screen sleeps (0 = disabled) | `15` |
| **Screensaver Mode** | Animation when timeout expires | `tesseract` |

**Screensaver Options:**
- `off` — Screen turns black
- `tesseract` — 4D hypercube rotation
- `starfield` — 3D star movement
- `matrix` — Matrix-style falling characters

### Hardware Pins Configuration

Assign GPIO pins for all hardware components:

| Component | Default Pin | Description |
|-----------|-------------|-------------|
| Encoder CLK | GP6 | Rotary encoder clock |
| Encoder DT | GP7 | Rotary encoder data |
| Encoder SW | GP8 | Rotary encoder switch |
| Button Pin | GP24 | Boot mode button |
| LED Pin | GP25 | Status LED (onboard) |
| OLED SDA | GP4 | Display I2C data |
| OLED SCL | GP5 | Display I2C clock |

**Note**: Pin numbers refer to GP (GPIO) pins on Raspberry Pi Pico.

### Hall Sensors

Define Hall effect sensor configurations:

**Adding Sensors:**
1. Click **"+ Add"** in Hall Sensors section
2. Configure each sensor:
   - **ID** — Unique identifier (e.g., `hall_sensor_1`)
   - **Pin** — GPIO pin number
   - **Active Low** — Checkbox for active-low logic

**Deleting Sensors:**
- Click the **×** button next to the sensor

### Passive Sensors Triggers

Bind scenarios to passive triggers:

| Trigger | Description |
|---------|-------------|
| **Hall Sensor (ID)** | Executes when sensor is activated |
| **Button Double Click** | Executes on double-click of boot button |

Select a scenario from the dropdown for each trigger. Hall sensors bypass cooldown for emergency actions.

---

## Workflow Examples

### Example 1: Docker Service Control

**Goal**: Create a menu item to start/stop a Docker container

1. **Create Scenarios**:
   - Go to **Scenarios Editor** tab
   - Create `docker_app_stop`:
     - Press Enter (count: 3)
     - Wait (200ms)
     - Type: `docker-compose -f /opt/app/docker-compose.yml stop`
     - KeyPress: `enter`
   - Create `docker_app_start`:
     - Press Enter (count: 3)
     - Wait (200ms)
     - Type: `docker-compose -f /opt/app/docker-compose.yml start`
     - KeyPress: `enter`

2. **Create Menu Item**:
   - Go to **Menu Hierarchy** tab
   - Click **"+ Add Root Action"**
   - Set properties:
     - ID: `docker_app`
     - Label: `Docker App`
   - Add sequence:
     - Entry 1: Scenario `docker_app_stop`, Name "Stop"
     - Entry 2: Scenario `docker_app_start`, Name "Start"

3. **Save**: Click **"Save config.json"**

### Example 2: Emergency Shutdown via Hall Sensor

**Goal**: Trigger safe shutdown when Hall sensor activates

1. **Create Scenario**:
   - Go to **Scenarios Editor**
   - Create `emergency_shutdown`:
     - Press Enter (count: 3)
     - Wait (1000ms)
     - Type: `sudo shutdown -h now`
     - KeyPress: `enter`

2. **Configure Trigger**:
   - In left sidebar, find **Passive Sensors Triggers**
   - Select `emergency_shutdown` for `hall_sensor_1`

3. **Hardware Check**:
   - Verify **Hall Sensors** section has correct pin assignment
   - Ensure **Device Configuration** → **Armed** is checked

4. **Save**: Click **"Save config.json"**

### Example 3: Multi-Level Menu Organization

**Goal**: Organize services by category

1. **Create Root Folders**:
   - Add folder `servers` (Label: "Servers")
   - Add folder `monitoring` (Label: "Monitoring")

2. **Add Services to Folders**:
   - Select `servers` folder
   - Click **"+ Action"** in inspector
   - Create actions: `web_server`, `database_server`, etc.

3. **Configure Each Action**:
   - Add scenario sequences for start/stop operations

4. **Drag to Reorganize**:
   - Reorder folders and items as needed

5. **Save**: Click **"Save config.json"**

---

## Configuration Validation

The editor performs automatic validation when saving:

### Common Warnings

| Warning | Description | Fix |
|---------|-------------|-----|
| Empty text to type | Type step has no value | Add text content |
| Empty key combination | KeyPress step has no combo | Add key combination |
| Invalid wait time | Wait time is negative or missing | Set positive millisecond value |
| Invalid enter count | Count is less than 1 | Set count ≥ 1 |
| Missing ID | Menu item has no identifier | Add unique ID |
| Empty sequence | Action has no scenarios | Add at least one sequence entry or convert to folder |
| Invalid pin | Sensor pin is negative or missing | Assign valid GPIO pin number |

### Validation Behavior

- Warnings do not prevent saving
- Configuration will work, but invalid commands may not execute
- Review and fix warnings before deploying to device

---

## Deploying Configuration

### Export and Transfer

1. Click **"Save config.json"** in header
2. Browser downloads the file to your default download location
3. Copy file to Pico Commander root directory (replace existing `config.json`)
4. Reboot the device or reload code

### Verification

After deploying:
1. Check OLED display for menu structure
2. Test rotary encoder navigation
3. Execute a test scenario to verify HID output
4. Monitor for errors if connected to terminal

---

## Keyboard Shortcuts Reference

| Shortcut | Context | Action |
|----------|---------|--------|
| **Delete** / **Backspace** | Menu tab (item selected) | Delete selected menu item |
| **Delete** / **Backspace** | Scenarios tab (scenario selected) | Delete active scenario |
| **Ctrl+Delete** | Scenario step | Delete step |
| **Ctrl+S** | Raw JSON tab | Apply changes |
| **Enter** | Input fields | Confirm and blur |
| **Escape** | Context menu open | Close menu |

---

## Best Practices

### Menu Design

- **Keep labels short** — OLED displays max 21 characters
- **Organize logically** — Group related actions in folders
- **Use descriptive IDs** — Makes troubleshooting easier (e.g., `docker_nextcloud` not `item_7`)
- **Test navigation flow** — Ensure menu depth is reasonable (max 2-3 levels)

### Scenario Design

- **Add delays** — Wait steps prevent command overlap
- **Clear terminal first** — Press Enter 3 times to ensure clean prompt
- **Test commands manually** — Verify syntax before adding to scenario
- **Use absolute paths** — Avoid relying on current working directory
- **Chain carefully** — Long scenarios may timeout on slow systems

### Hardware Configuration

- **Document pin changes** — Keep notes if you modify default pins
- **Verify pull resistors** — Hall sensors and buttons need proper pull configuration
- **Test individually** — Test each sensor before deploying full config
- **Label wires** — Physical labels match IDs in configuration

### Maintenance

- **Backup configurations** — Save working `config.json` versions
- **Validate before deploy** — Use validation warnings to catch issues
- **Version control** — Track changes in git for complex setups
- **Comment via IDs** — Use descriptive IDs as documentation (JSON has no comments)

---

## Troubleshooting

### Editor Issues

**Problem**: Load button doesn't respond
- **Solution**: Check browser console for errors, refresh page, ensure file input element is not blocked

**Problem**: Configuration doesn't save changes
- **Solution**: Click "Apply Changes" in Raw JSON tab, verify tab switching syncs data

**Problem**: Drag-and-drop not working
- **Solution**: Ensure SortableJS library loaded (check network tab), try different browser

### Configuration Issues

**Problem**: Menu item doesn't appear on device
- **Solution**: Verify ID is unique, check `active_menu` array in Raw JSON, ensure label is set

**Problem**: Scenario doesn't execute
- **Solution**: Check scenario is bound to menu item sequence, verify scenario exists in `scenarios` object, test commands manually

**Problem**: Hall sensor doesn't trigger
- **Solution**: Verify pin assignment matches hardware, check `armed` is true, ensure trigger is bound in `passive` object, test sensor with multimeter

### Validation Warnings

**Problem**: "Empty sequence" warning
- **Solution**: Add at least one scenario to the action's sequence, or remove the empty sequence field and convert to folder

**Problem**: "Missing ID" warning
- **Solution**: Open inspector for the item, set unique ID in the ID field

**Problem**: "Invalid pin number" warning
- **Solution**: Open Hall Sensors section, ensure pin values are valid GPIO numbers (0-29 for Pico)

---

## Technical Details

### File Format

The editor produces standard `config.json` files with this structure:

```json
{
  "hardware": { /* Pin assignments */ },
  "device": { /* Behavior settings */ },
  "passive": { /* Trigger → Scenario bindings */ },
  "active_menu": [ /* Menu hierarchy array */ ],
  "scenarios": { /* Scenario name → steps mapping */ }
}
```

### Browser Compatibility

**Tested Browsers:**
- Chrome/Chromium 90+
- Firefox 88+
- Edge 90+
- Safari 14+

**Required Features:**
- ES6 JavaScript
- Drag and Drop API
- FileReader API
- CSS Grid and Flexbox

### External Dependencies

- **SortableJS** (1.15.0) — Drag-and-drop library (loaded from CDN)
- **Google Fonts** — Outfit and JetBrains Mono (loaded from CDN)

**Offline Usage:**
Download dependencies and update `<script>` and `<link>` tags to local paths.

### Security Note

This is a client-side application. No data is transmitted to external servers. All configuration editing happens locally in your browser. The "Load" and "Save" buttons use browser file APIs only.

---

## FAQ

**Q: Can I edit config.json directly instead of using the editor?**  
A: Yes. The editor is a convenience tool. Manual JSON editing works if you prefer text editors.

**Q: Does the editor validate scenario command syntax?**  
A: No. The editor checks JSON structure and field presence, but cannot validate if shell commands will work on your target system.

**Q: Can I share configurations between devices?**  
A: Yes. Save `config.json` and copy to other Pico Commander devices. Ensure hardware pin assignments match.

**Q: What happens if I load an invalid JSON file?**  
A: The editor displays an error message and does not load the file. Fix JSON syntax and try again.

**Q: Can I undo changes?**  
A: The editor does not have built-in undo. Reload the original file or use version control (git) for config files.

**Q: Is the editor required to use Pico Commander?**  
A: No. You can manually create and edit `config.json` files. The editor simplifies configuration management.

---

## Support

For issues, feature requests, or questions:

- **Documentation**: See project README and inline code comments
- **GitHub Issues**: Report bugs or request features via project repository
- **Community**: Check project discussions for user tips and examples

---

**Last Updated**: 2024  
**Editor Version**: 1.0  
**Compatible with**: Pico Commander 1.0+
