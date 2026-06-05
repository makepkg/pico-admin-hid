# Active Trigger System

Technical documentation for the active (menu-driven) trigger system.

---

## Overview

The active trigger system handles user-initiated actions through the rotary encoder and menu navigation. These triggers execute scenarios based on explicit user selection and interaction.

### Key Characteristics

- **Synchronous** — Triggered by explicit user action (encoder click)
- **Menu-driven** — Integrated with hierarchical navigation system
- **Stateful Sequences** — Toggle between multiple scenarios per menu item
- **Visual Feedback** — OLED displays current and next actions

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    ENCODER HANDLER                        │
│                     (encoder.py)                          │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐       ┌──────────────┐                │
│  │  Rotation    │       │  Click/Press │                │
│  │  Detection   │       │  Detection   │                │
│  └──────┬───────┘       └──────┬───────┘                │
│         │                      │                         │
│         └──────────┬───────────┘                         │
│                    ▼                                     │
│         ┌────────────────────┐                           │
│         │  Event Callback    │                           │
│         └──────────┬─────────┘                           │
└────────────────────┼──────────────────────────────────────┘
                     │
                     ▼
          ┌───────────────────────┐
          │   Main Loop Handler   │
          │   (code.py callback)  │
          └──────────┬────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────┐          ┌────────────────┐
│   Rotation   │          │     Click      │
│   Handler    │          │    Handler     │
└──────┬───────┘          └────────┬───────┘
       │                           │
       ▼                           ▼
┌──────────────┐          ┌────────────────┐
│  Update Menu │          │  Item Type?    │
│   Cursor     │          └────────┬───────┘
│              │                   │
│  Animate     │          ┌────────┴────────┐
│  Swipe       │          │                 │
│              │          ▼                 ▼
│  Save State  │   ┌────────────┐   ┌────────────┐
└──────────────┘   │  Sequence  │   │  Submenu   │
                   │  Execute   │   │  Navigate  │
                   └─────┬──────┘   └────────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ trigger_bus      │
                │ .fire_active()   │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ Scenario Executor│
                └──────────────────┘
```

---

## Menu Structure

### Item Types

**1. Action Items**
- Contain `sequence` array
- Execute scenarios when clicked
- Toggle through sequence on repeated clicks

**2. Folder Items**
- Contain `submenu` array
- Navigate into folder on click
- Can optionally have `sequence` (executes before opening)

**3. Hybrid Items**
- Both `sequence` AND `submenu`
- Execute scenario, then open folder

### Menu Configuration

```json
"active_menu": [
  {
    "id": "docker_service",
    "label": "Docker App",
    "sequence": [
      {"scenario": "docker_stop", "name": "Stop"},
      {"scenario": "docker_start", "name": "Start"}
    ]
  },
  {
    "id": "servers_folder",
    "label": "Servers",
    "submenu": [
      {
        "id": "web_server",
        "label": "Web Server",
        "sequence": [...]
      }
    ]
  }
]
```

---

## Navigation System

### Menu Hierarchy

```
Root Menu
├── Item 1 (Action)
│   └── sequence: [scenario_a, scenario_b]
├── Item 2 (Folder)
│   └── submenu:
│       ├── Item 2.1 (Action)
│       └── Item 2.2 (Folder)
│           └── submenu:
│               └── Item 2.2.1 (Action)
└── Item 3 (Action)
```

**Depth Limit**: Technically unlimited, practically 3-4 levels recommended

### Navigation Stack

```python
# Stack stores (parent_menu, cursor_position) tuples
menu_stack = []

# Navigate into folder
menu_stack.append((current_menu_list, menu_cursor))
current_menu_list = item["submenu"]
menu_cursor = 0

# Navigate back (long press)
current_menu_list, menu_cursor = menu_stack.pop()
```

**Stack Example**:
```
User at Root → clicks Folder A → clicks Folder B
Stack: [(Root, 1), (Folder A, 0)]
Current: Folder B, cursor 0

User long-presses → back to Folder A
Stack: [(Root, 1)]
Current: Folder A, cursor 0

User long-presses → back to Root
Stack: []
Current: Root, cursor 1
```

---

## Encoder Events

### Event Types

| Event | Trigger | Purpose |
|-------|---------|---------|
| `EV_ROTATE_LEFT` | Counter-clockwise | Previous menu item |
| `EV_ROTATE_RIGHT` | Clockwise | Next menu item |
| `EV_PRESS` | Short click (<1s) | Execute/Enter |
| `EV_LONG_PRESS` | Hold ≥1s | Back to parent |

### Event Processing

```python
def on_encoder_event(event):
    # Wake display if sleeping
    if screen_sleeping or screensaver_active:
        wake_up_display()
        return  # Consume event
    
    if event == EV_ROTATE_RIGHT:
        menu_cursor = (menu_cursor + 1) % len(current_menu_list)
        display.animate_swipe(old_label, new_label, "right")
        save_cursor()
    
    elif event == EV_ROTATE_LEFT:
        menu_cursor = (menu_cursor - 1) % len(current_menu_list)
        display.animate_swipe(old_label, new_label, "left")
        save_cursor()
    
    elif event == EV_PRESS:
        item = current_menu_list[menu_cursor]
        
        # Execute sequence if exists
        if "sequence" in item:
            display.show_executing(item["label"], action_name)
            trigger_bus.fire_active(item["id"])
        
        # Navigate into submenu if exists
        if "submenu" in item:
            menu_stack.append((current_menu_list, menu_cursor))
            current_menu_list = item["submenu"]
            menu_cursor = 0
        
        refresh_menu()
    
    elif event == EV_LONG_PRESS:
        if menu_stack:
            current_menu_list, menu_cursor = menu_stack.pop()
            refresh_menu()
```

---

## Sequence System

### Sequence Behavior

Sequences allow **toggling** between multiple scenarios with repeated clicks:

```json
"sequence": [
  {"scenario": "service_stop", "name": "Stop"},
  {"scenario": "service_start", "name": "Start"},
  {"scenario": "service_restart", "name": "Restart"}
]
```

**User Experience**:
```
Click 1: Execute "service_stop"    → Display shows "Start" (next)
Click 2: Execute "service_start"   → Display shows "Restart" (next)
Click 3: Execute "service_restart" → Display shows "Stop" (loops back)
Click 4: Execute "service_stop"    → ...
```

### Sequence State Persistence

```json
// state.json
{
  "menu_cursor": 2,
  "seq_positions": {
    "docker_service": 1,    // Currently at index 1 (Start)
    "n8n_service": 0        // Currently at index 0 (Stop)
  }
}
```

**State Management**:
```python
# Load current position
positions = state.get("seq_positions", {})
pos = positions.get(item_id, 0) % len(sequence)

# Get scenario at current position
scenario_entry = sequence[pos]
scenario_name = scenario_entry["scenario"]

# Execute scenario
trigger_bus.fire_active(item_id)

# Advance position
positions[item_id] = (pos + 1) % len(sequence)
config.save_state()
```

### Sequence Entry Format

**Simple Format** (string):
```json
"sequence": ["scenario_name"]
```
- Scenario name only
- Display name = scenario name

**Detailed Format** (object):
```json
"sequence": [
  {
    "scenario": "scenario_name",
    "name": "Display Name"
  }
]
```
- Custom display name
- More descriptive for UI

---

## Trigger Execution

### Fire Active Flow

```python
def fire_active(item_id):
    # 1. Check anti-conflict rules
    if not _can_fire(PRIORITY_NORMAL):
        return False
    
    # 2. Find menu item by ID (recursive search)
    item = _find_item(config["active_menu"], item_id)
    if not item:
        return False
    
    # 3. Get sequence
    sequence = item.get("sequence", [])
    if not sequence:
        return False
    
    # 4. Load current sequence position
    positions = state.get("seq_positions", {})
    pos = positions.get(item_id, 0) % len(sequence)
    
    # 5. Resolve scenario name
    entry = sequence[pos]
    scenario_name = entry["scenario"] if isinstance(entry, dict) else entry
    
    # 6. Set busy flag
    _busy = True
    
    try:
        # 7. Execute scenario
        _run_scenario(scenario_name)
        
        # 8. Advance sequence position
        positions[item_id] = (pos + 1) % len(sequence)
        config.save_state()
    
    finally:
        # 9. Clear busy flag
        _busy = False
        
        # 10. Apply cooldown
        _apply_cooldown()
    
    return True
```

### Recursive Item Search

Menu items can be nested arbitrarily deep. Trigger bus searches recursively:

```python
def _find_item(menu, item_id):
    for item in menu:
        # Match found
        if item["id"] == item_id:
            return item
        
        # Search submenu
        if "submenu" in item:
            found = _find_item(item["submenu"], item_id)
            if found:
                return found
    
    return None
```

**Why Needed**: 
- Item IDs must be globally unique
- User might click item deep in hierarchy
- Sequence state persists across navigation

---

## Display Feedback

### Menu Display

```
┌────────────────────────────────┐
│ < MENU >                       │  Header
│ Docker Service                 │  Current item label
│ -> Start                       │  Next action hint
└────────────────────────────────┘
```

### Execution Display

```
┌────────────────────────────────┐
│ Running...                     │  Feedback
│ Docker Service                 │  Item being executed
│ Start                          │  Action being executed
└────────────────────────────────┘
```

### Swipe Animation

**6-Frame Horizontal Slide**:
```
Frame 0: [Old Label]              [New Label off-screen]
Frame 1: [Old    ]  Label]        [New Label        ]
Frame 2:     [Old Label]          [  New Label      ]
Frame 3:        [Old Label]       [    New Label    ]
Frame 4:           [Old Label]    [      New Label  ]
Frame 5:              [Old Label] [        New Label]
Frame 6:                          [New Label]
```

**Duration**: ~132ms (6 frames × 22ms)

---

## State Persistence

### What Gets Saved

**Menu Cursor Position**:
```json
{
  "menu_cursor": 3  // Currently at 4th item (0-indexed)
}
```
- Saved on every rotation
- Restored on boot
- Per-level (not saved when in submenu)

**Sequence Positions**:
```json
{
  "seq_positions": {
    "item_id_1": 2,
    "item_id_2": 0
  }
}
```
- Saved after every sequence execution
- Restored on boot
- Persists across power cycles

### Save Timing

```python
# Cursor save: immediate on rotation
def on_encoder_event(EV_ROTATE_*):
    menu_cursor = ...
    save_cursor()  # Writes state.json

# Sequence save: after scenario completes
def fire_active(item_id):
    execute_scenario()
    positions[item_id] = new_pos
    config.save_state()  # Writes state.json
```

### File Write Behavior

**Normal Boot Mode**:
- File system writable from code
- state.json auto-created/updated
- USB drive read-only

**Development Boot Mode** (GP24 held):
- File system read-only from code
- state.json changes not saved
- USB drive writable for editing

---

## Conflict Resolution

### Cooldown Enforcement

Active triggers respect cooldown (unlike passive HIGH priority):

```python
if now < _cooldown_until:
    print("[bus] DROP — cooldown")
    return False
```

**Purpose**: Prevent rapid repeated execution from encoder bounce or accidental double-clicks

**Duration**: 5000ms default (configurable via `device.cooldown_ms`)

### Busy Flag

```python
if _busy:
    print("[bus] DROP — busy")
    return False
```

**Purpose**: Prevent overlapping scenario execution

**Behavior**:
- Set at start of `fire_active()`
- Cleared in `finally` block (guaranteed)
- Rejects all triggers (active and passive) during execution

---

## Interaction Patterns

### Toggle Pattern

**Use Case**: Start/Stop services

```json
{
  "id": "service_toggle",
  "label": "My Service",
  "sequence": [
    {"scenario": "service_stop", "name": "Stop"},
    {"scenario": "service_start", "name": "Start"}
  ]
}
```

**User Flow**:
1. Navigate to "My Service"
2. Click → Executes stop → Display shows "Start"
3. Click → Executes start → Display shows "Stop"
4. Click → Executes stop → ...

### Multi-Action Pattern

**Use Case**: Service lifecycle management

```json
{
  "id": "service_mgmt",
  "label": "Web Server",
  "sequence": [
    {"scenario": "web_stop", "name": "Stop"},
    {"scenario": "web_start", "name": "Start"},
    {"scenario": "web_restart", "name": "Restart"},
    {"scenario": "web_status", "name": "Status"}
  ]
}
```

### One-Shot Pattern

**Use Case**: Single-action commands

```json
{
  "id": "backup_now",
  "label": "Run Backup",
  "sequence": [
    {"scenario": "backup_full", "name": "Execute"}
  ]
}
```

**Behavior**: Always executes same scenario, cycles back to self

---

## Advanced Features

### Hybrid Items

```json
{
  "id": "servers_with_action",
  "label": "Servers",
  "sequence": [
    {"scenario": "refresh_status", "name": "Refresh"}
  ],
  "submenu": [...]
}
```

**Behavior**:
1. Click → Execute "refresh_status"
2. After execution → Open submenu automatically
3. User sees updated status in subfolder

### Dynamic Next Action

Display shows next action without executing:

```python
def get_next_action_name(item_id):
    # Non-destructive: doesn't advance sequence
    positions = state.get("seq_positions", {})
    pos = positions.get(item_id, 0)
    entry = sequence[pos]
    return entry["name"]
```

**Used For**:
- Display footer line
- User preview of next click
- No side effects

---

## Troubleshooting

### Scenario Doesn't Execute

**Symptoms**: Click encoder, nothing happens

**Check**:
1. Serial console: `[bus] DROP — busy` or cooldown message
2. Verify item has `sequence` in config.json
3. Check scenario exists in `scenarios` object
4. Verify USB connected

### Wrong Scenario Executes

**Symptoms**: Click executes unexpected scenario

**Causes**:
- Sequence position saved incorrectly
- Duplicate item IDs in menu

**Solutions**:
1. Delete state.json and reboot (resets positions)
2. Verify all item IDs are unique
3. Check `seq_positions` in state.json

### Menu Cursor Resets

**Symptoms**: Position doesn't persist across reboots

**Causes**:
- Booted in Development Mode (GP24 held)
- state.json not writable

**Solution**: Boot in Normal Mode (don't hold GP24)

### Sequence Loops Too Fast

**Symptoms**: Clicks execute multiple scenarios rapidly

**Causes**:
- Encoder bounce
- Cooldown disabled or too short

**Solutions**:
1. Increase `device.cooldown_ms` (e.g., 8000)
2. Check encoder wiring quality
3. Add hardware debounce capacitor

---

## Performance Characteristics

### Response Time

| Action | Latency | Notes |
|--------|---------|-------|
| Rotation detection | ~10ms | Main loop cycle |
| Animation duration | ~132ms | 6-frame swipe |
| Click to execution | ~20ms | Callback + trigger bus |
| Total user latency | ~150ms | Perceived delay |

### Memory Usage

- **Menu tree**: ~100-500 bytes per item (depends on label length)
- **Navigation stack**: ~20 bytes per level
- **State persistence**: ~50-200 bytes (depends on item count)

---

## API Reference

### EncoderHandler Class

**Constructor**:
```python
EncoderHandler()
```

**Methods**:
```python
set_callback(cb)   # Register event handler
update()           # Poll encoder, call every loop
```

**Events**:
```python
EV_ROTATE_LEFT
EV_ROTATE_RIGHT
EV_PRESS
EV_LONG_PRESS
```

### Trigger Bus Active Trigger API

**Functions**:
```python
trigger_bus.fire_active(item_id)              # Execute menu item sequence
trigger_bus.get_next_action_name(item_id)     # Preview next action (non-destructive)
```

---

## Related Documentation

- [Passive Trigger System](passive-triggers.md)
- [Trigger Bus Architecture](architecture.md#trigger-system)
- [Menu Configuration Guide](../user/config-editor.md#tab-1-menu-hierarchy)
