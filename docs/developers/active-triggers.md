# Active Trigger System

Technical documentation for the active (menu-driven) trigger system.

---

## Overview

The active trigger system handles user-initiated actions through the rotary encoder and menu navigation. These triggers execute scenarios based on explicit user selection and interaction.

### Key Characteristics

- **Synchronous** — Triggered by explicit user action (encoder click)
- **Menu-driven** — Integrated with hierarchical navigation system
- **Unified Pipeline** — Shares the same execution engine (`execute_pipeline()`) as passive triggers
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
└──────────────┘   │  Pipeline  │   │  Submenu   │
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
                │ execute_pipeline()│
                └──────────────────┘
```

---

## Pipeline System

Active triggers are defined by a `pipeline` of scenarios and a `loop` flag. This system replaced the legacy `"sequence"` format, although the engine still supports `"sequence"` for backward compatibility.

### `loop: true` (Toggle Pattern)
One click executes exactly **one** scenario from the pipeline. The system tracks the current position in `state.json`. The next click will execute the next scenario in the pipeline, wrapping around to the beginning.

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
*Note: In the new pipeline format, the display name field is `"label"`. In the legacy sequence format, it was `"name"`.*

### `loop: false` (Chain / One-Shot Pattern)
One click executes the **entire** pipeline of scenarios sequentially at once. The system does not track position.

```json
{
  "id": "backup_now",
  "label": "Run Backup",
  "pipeline": [
    {"scenario": "backup_prepare", "label": "Prepare"},
    {"scenario": "backup_execute", "label": "Execute"},
    {"scenario": "backup_cleanup", "label": "Cleanup"}
  ],
  "loop": false
}
```

---

## Menu Structure

### Item Types

**1. Action Items**
- Contain `pipeline` and `loop`
- Execute scenarios when clicked
- Can toggle through the pipeline (`loop: true`) or execute all (`loop: false`)

**2. Folder Items**
- Contain `submenu` array
- Navigate into folder on click

**3. Hybrid Items**
- Both `pipeline` AND `submenu`
- `code.py` checks both independently: it will execute the pipeline scenarios first, then navigate into the folder.

**4. Encoder Control Items**
- Contain `"type": "encoder_control"` and `output_mode` (`"mouse"` or `"scenario"`)
- On click, the encoder switches from menu navigation into a direct-control mode instead of opening a submenu or firing a pipeline in the usual sense
- See [Encoder Control Mode](#encoder-control-mode) below for the full behavior

### Menu Configuration

```json
"active_menu": [
  {
    "id": "docker_service",
    "label": "Docker App",
    "pipeline": [ ... ],
    "loop": true
  },
  {
    "id": "servers_folder",
    "label": "Servers",
    "submenu": [
      {
        "id": "web_server",
        "label": "Web Server",
        "pipeline": [ ... ],
        "loop": false
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
│   └── pipeline: [scenario_a, scenario_b]
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

---

## Encoder Control Mode

Encoder Control is a fourth menu item type (`"type": "encoder_control"`) that temporarily repurposes the encoder from menu navigation into a direct-input device — a scroll wheel, a pointer button, or a trigger for arbitrary scenarios on rotation/click — without leaving the menu hierarchy.

### Why It Exists

Normal menu items require entering a submenu and clicking a specific entry for each action. For continuous or repetitive interactions — scrolling a page, paging through something with arrow keys — that's unnecessary friction. Encoder Control turns rotation itself into the action.

### Configuration

```json
{
  "id": "browser_scroll",
  "label": "Browser Scroll",
  "type": "encoder_control",
  "output_mode": "mouse"
}
```

```json
{
  "id": "video_control",
  "label": "Video Control",
  "type": "encoder_control",
  "output_mode": "scenario",
  "on_rotate_right": ["scenario_arrow_right"],
  "on_rotate_left": ["scenario_arrow_left", "scenario_show_osd"],
  "on_click": ["scenario_pause"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | string | Yes | Must be `"encoder_control"` |
| `output_mode` | string | Yes | `"mouse"` or `"scenario"` |
| `pipeline` | array | No | Optional entry-action, executed once on click before the mode activates. Uses the standard pipeline mechanism (see [Pipeline System](#pipeline-system)) but is always treated as `loop: false` regardless of the `loop` value in config. |
| `on_rotate_right` | array of scenario names | Only if `output_mode: "scenario"` | Scenarios run on clockwise rotation |
| `on_rotate_left` | array of scenario names | Only if `output_mode: "scenario"` | Scenarios run on counter-clockwise rotation |
| `on_click` | array of scenario names | Only if `output_mode: "scenario"` | Scenarios run on short click |

Unlike `active_menu[].pipeline`, the three `on_rotate_*`/`on_click` fields are plain arrays of scenario names — not `{"scenario": ..., "label": ...}` objects — because the on-screen label during execution is always the fixed event name (`-> Right` / `-> Left` / `-> Click`), not a per-entry label.

### Entering and Exiting

Entering does **not** push onto the navigation stack the way a folder does:

```python
# On EV_PRESS for an encoder_control item:
if item.get("type") == "encoder_control":
    encoder_control_item = item
    _enter_encoder_control_display(item)
    return
# current_menu_list / menu_cursor / menu_stack are left untouched
```

Because the cursor position is never moved, exiting (long press) requires no stack `pop()` — `refresh_menu()` simply redraws whatever `current_menu_list[menu_cursor]` already was, which is the parent item the user entered from.

### `output_mode: "mouse"` — Direct Output

Fixed, non-configurable mapping, dispatched through `trigger_bus.execute_output("mouse", ...)` — the same direct-call path used by `TrackballInput` (see [Outputs Guide — Direct-Call Pattern](outputs.md#direct-call-pattern-trackball-input)). This bypasses cooldown and the busy/priority queue entirely, because it never goes through `execute_pipeline()`.

| Event | Action |
|---|---|
| Rotate right | `{"action": "scroll", "wheel": 3}` |
| Rotate left | `{"action": "scroll", "wheel": -3}` |
| Click | `{"action": "click", "button": "right"}` |

There is no configuration for direction, step size, or button — this mode is intentionally hardcoded for minimal latency and minimal surface area. If a different button or step is needed, use `output_mode: "scenario"` instead.

### `output_mode: "scenario"` — Pipeline Output

Each event independently calls `execute_pipeline()` directly (not through `fire_active()`, since there is no `submenu`-aware item lookup needed here):

```python
trigger_bus.execute_pipeline(
    {"pipeline": item["on_rotate_right"], "loop": False},
    trigger_id=f"encoder_ctrl_{item['id']}_{event}",
    priority=trigger_bus.PRIORITY_HIGH
)
```

`loop` is always forced to `False` — looping has no meaning for a per-event trigger. `PRIORITY_HIGH` is used to bypass the standard cooldown, following the same precedent already established for `TrackballInput` in `click_mode: "scenario"` (see [Passive Trigger System](passive-triggers.md)) — frequent, user-driven interactions are an accepted use of `PRIORITY_HIGH`, not only hardware emergencies. The busy flag still applies: if a pipeline from one event is still executing, a rapid second rotation is dropped rather than queued.

**Keep these pipelines short.** `execute_pipeline()` runs synchronously in the main loop; a `wait` step inside it blocks `inputs.update()` for its duration, which means Hall sensor and power-monitor polling pause too. This is an existing system-wide property (any executing pipeline has always blocked input polling), but Encoder Control makes it easy to trigger repeatedly in quick succession. For continuous, high-frequency interaction, prefer `output_mode: "mouse"` instead — `execute_output()` never blocks the main loop.

### Display Feedback

- **On entry** (and again on wake from screen sleep/screensaver, if the mode is still active): `display.show_encoder_control(label, mode_type)` shows the item's label and `"Mouse"` or `"Scenario"`.
- **`output_mode: "scenario"`, per event**: `display.show_executing(label, event_label)` — reuses the same call used by ordinary menu actions, so it shows for exactly as long as the triggered pipeline actually takes to run.
- **`output_mode: "mouse"`**: no per-event indicator. The effect (an actual scroll, an actual click) is immediately visible on the host, and adding a transient on-screen indicator here would require the mode's execution path to touch the main loop's timing — an explicit, deliberate tradeoff **not** implemented.
- A pending caveat: the `show_executing()` text in scenario mode does not auto-clear back to the mode's background view after the pipeline finishes — it holds until the next event. Cosmetic only.

### Known Constraints

- No `submenu`: `encoder_control` items cannot contain child items. Converting an existing folder with items into `encoder_control` (via the Config Studio inspector) requires confirming deletion of its contents, the same confirmation already used for folder→action conversion.
- No `loop: true` anywhere in this item type — neither on the optional entry `pipeline`, nor on `on_rotate_*`/`on_click`.
- Mouse mode's button/direction/step are not configurable, by design.

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
        # Pass menu state to display for geometric render mode
        display.set_menu_state(menu_cursor, len(current_menu_list), len(menu_stack))
        display.animate_swipe(old_label, new_label, "right")
        save_cursor()
    
    elif event == EV_PRESS:
        item = current_menu_list[menu_cursor]
        
        # Execute pipeline/sequence if exists
        if "pipeline" in item or "sequence" in item:
            display.show_executing(item["label"], action_name)
            trigger_bus.fire_active(item["id"])
        
        # Navigate into submenu if exists
        if "submenu" in item:
            menu_stack.append((current_menu_list, menu_cursor))
            current_menu_list = item["submenu"]
            menu_cursor = 0
        
        refresh_menu()
```

---

## Trigger Execution

### Fire Active Flow

When `trigger_bus.fire_active(item_id)` is called, it acts as a facade that normalizes the menu item configuration and passes it to the unified pipeline engine.

```python
def fire_active(item_id):
    item = _find_item(config["active_menu"], item_id)
    
    # Path 1: New Pipeline Format
    if "pipeline" in item:
        # execute_pipeline handles busy flags, cooldowns, and loop branching
        return execute_pipeline(item, f"active_{item_id}", PRIORITY_NORMAL)
    
    # Path 2: Legacy Sequence Format (Fallback)
    sequence = item.get("sequence", [])
    
    # Convert sequence to pipeline format
    pipeline = [_resolve_seq_entry(entry)[0] for entry in sequence]
    pipeline_config = {
        "pipeline": pipeline,
        "loop": True  # sequence was always a toggle loop
    }
    
    return execute_pipeline(pipeline_config, f"active_{item_id}", PRIORITY_NORMAL)
```

### Recursive Item Search

Menu items can be nested arbitrarily deep. The trigger bus searches recursively to find the item by its globally unique `id`.

---

## State Persistence

### What Gets Saved (`state.json`)

**Menu Cursor Position**:
```json
{
  "menu_cursor": 3  // Currently at 4th item (0-indexed)
}
```
- Saved on every rotation.
- Restored on boot.
- Per-level (not saved when traversing into a submenu).

**Trigger Positions (New Mechanism)**:
```json
{
  "trigger_positions": {
    "active_docker_service": 1,
    "passive_hall_sensor_1": 0
  }
}
```
- Tracks positions for `loop: true` pipelines.
- Prefixed with `active_` or `passive_` based on the trigger source.

**Sequence Positions (Legacy Mechanism)**:
```json
{
  "seq_positions": {
    "legacy_item_id": 2
  }
}
```
- Used **only** for menu items still using the legacy `"sequence"` format.
- Keys are the bare `item_id`.

### File Write Behavior

**Normal Boot Mode**:
- File system writable from code
- `state.json` auto-created/updated
- USB drive read-only from host

**Development Boot Mode** (GP24 held during boot):
- File system read-only from code
- `state.json` changes not saved
- USB drive writable from host for editing

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

### Dynamic Next Action Hint

The `get_next_action_name(item_id)` function determines what shows up on the third line (`-> Start`):

- **Pipeline + `loop: true`**: Shows the `label` of the scenario at the current `trigger_positions` index. (Changes after every click).
- **Pipeline + `loop: false`**: **Always** shows the `label` of the first scenario (`pipeline[0]`). Since all scenarios execute at once, there is no "next" state to track.
- **Legacy Sequence**: Shows the `name` of the scenario at the current `seq_positions` index.

---

## Conflict Resolution

### Cooldown Enforcement

Active triggers respect cooldowns (unlike passive HIGH priority triggers):

```python
if now < _cooldown_until:
    print("[bus] DROP — cooldown")
    return False
```

**Purpose**: Prevent rapid repeated execution from encoder bounce or accidental double-clicks.
**Duration**: 5000ms default (configurable via `device.cooldown_ms`).

### Busy Flag

```python
if _busy:
    print("[bus] DROP — busy")
    return False
```

**Purpose**: Prevent overlapping scenario execution.

---

## Interaction Patterns

### Toggle Pattern (`loop: true`)

**Use Case**: Start/Stop services

```json
{
  "id": "service_toggle",
  "label": "My Service",
  "pipeline": [
    {"scenario": "service_stop", "label": "Stop"},
    {"scenario": "service_start", "label": "Start"}
  ],
  "loop": true
}
```

### Chain Pattern (`loop: false`)

**Use Case**: Execute multiple discrete scenarios in order on a single click.

```json
{
  "id": "complex_macro",
  "label": "Deploy App",
  "pipeline": [
    {"scenario": "pull_repo", "label": "Pulling..."},
    {"scenario": "build_image", "label": "Building..."},
    {"scenario": "start_container", "label": "Starting..."}
  ],
  "loop": false
}
```
*⚠️ **Note**: Currently, this specific case (multiple scenarios with `loop: false`) can only be authored by hand-editing `config.json`. The Config Studio UI limits non-loop pipelines to a single scenario via the UI constraints.*

### One-Shot Pattern (`loop: false`)

**Use Case**: Single-action commands

```json
{
  "id": "backup_now",
  "label": "Run Backup",
  "pipeline": [
    {"scenario": "backup_full", "label": "Execute"}
  ],
  "loop": false
}
```

---

## Advanced Features

### Hybrid Items

```json
{
  "id": "servers_with_action",
  "label": "Servers",
  "pipeline": [
    {"scenario": "refresh_status", "label": "Refresh"}
  ],
  "loop": false,
  "submenu": [...]
}
```

**Behavior**:
1. Click → Execute "refresh_status" scenario.
2. After execution → Open submenu automatically.
3. User sees updated status in subfolder.

---

## Troubleshooting

### Scenario Doesn't Execute

**Symptoms**: Click encoder, nothing happens

**Check**:
1. Serial console: `[bus] DROP — busy` or cooldown message
2. Verify item has `pipeline` in config.json
3. Check scenario exists in `scenarios` object
4. Verify USB connected (if using HID output)

### Menu Cursor Resets

**Symptoms**: Position doesn't persist across reboots

**Causes**:
- Booted in Development Mode (GP24 held)
- state.json not writable

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

---

## API Reference

### Trigger Bus Active Trigger API

**Functions**:
```python
trigger_bus.fire_active(item_id)              # Façade for menu item triggers
trigger_bus.execute_pipeline(config, id, pri) # Core unified pipeline engine
trigger_bus.fire_scenario(name)               # Direct execution (used for auto-boot)
trigger_bus.get_next_action_name(item_id)     # Preview next action (non-destructive)
```

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

---

## Related Documentation

- [Passive Trigger System](passive-triggers.md)
- [Trigger Bus Architecture](architecture.md#trigger-system)
- [Pipeline Configuration Guide](../user/pipelines.md)
- [Outputs System Guide](outputs.md)
- [Menu Configuration Guide](../user/config-editor.md#tab-1-menu-hierarchy)
