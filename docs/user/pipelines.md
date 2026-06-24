# Automation and Pipelines

This document is a conceptual guide for Pico Commander users. Its goal is to bridge the gap between "I understand the individual config fields" (which are covered in `configuration-guide.md`) and "I know how to mentally build a working automation from scratch". 

Here, we will break down what a pipeline consists of, how it relates to triggers (inputs/menus) and outputs (USB/GPIO), and how to properly "weave" all of this together.

---

## The Big Picture

Any automation in Pico Commander consists of four layers. Here is a simple text diagram of how they form a chain, in the order of "what happens first":

```text
  TRIGGER (what starts it)    →  PIPELINE (what executes)        →  SCENARIO (what actions are taken)             →  OUTPUT (where the result lands) 
  encoder click on menu item     ["scenario_a", "scenario_b"]       [{"output":"hid", "action":"type", ...}, ...]    USB HID keyboard 
  Hall sensor / button / ina     loop: true or false                mix of hid + gpio steps in one scenario          GPIO pin (relay/optocoupler) 
```

To explain each entity in plain language:
* **Trigger** — the physical or software event that the device reacts to. For example, clicking an encoder on a menu item, a Hall sensor tripping, or a battery voltage drop.
* **Pipeline** — a list of scenarios tied to a specific trigger, along with a rule (`loop`) that tells the engine exactly how to iterate through this list.
* **Scenario** — a specific, reusable list of steps (instructions) describing exactly what needs to be done.
* **Output** — what physically happens at the moment a step is executed. This could be a virtual keystroke on the connected host (PC) or a real electrical signal on a GPIO pin (a relay clicking).

---

## Two Places Pipelines Live

It's important to understand that a pipeline is not a separate, global "thing" or a dedicated section in the config. It is a **field** that appears in two different places in `config.json`, but it always has the exact same shape: `{"pipeline": [...], "loop": bool}`.

1. **`active_menu[].pipeline`** — tied to a menu item. It triggers only on an explicit encoder click by the user.
2. **`passive.<input_id>`** — tied to a hardware input (e.g., a Hall sensor, INA226 power monitor, or a button). It triggers automatically when the sensor detects an event.

The execution mechanism for both is **exactly the same**. Under the hood, the same `execute_pipeline()` function handles both cases. The only difference is *what exactly* issues the command to start.

---

## loop: true vs loop: false — Choose Wisely

The `loop` flag is the central fork in the pipeline logic that everyone writing a config must clearly understand.

### `loop: true` (Cycle)
Each trigger event executes exactly **ONE** scenario from the list in order, and remembers where it stopped. This state is saved in the `state.json` file and survives a device reboot.
This is perfectly suited for the "Start/Stop" (toggle) pattern.

**Example from `config.json` (Nextcloud control):**
```json
{
  "id": "nextcloud",
  "label": "Nextcloud",
  "pipeline": [
    {"scenario": "scenario_nextcloud_stop", "label": "Stop"},
    {"scenario": "scenario_nextcloud_start", "label": "Start"}
  ],
  "loop": true
}
```
**What will happen:**
* **First click:** `scenario_nextcloud_stop` is executed (stops the container).
* **Second click:** `scenario_nextcloud_start` is executed (starts the container).
* **Third click:** the engine reached the end of the list and loops back to the beginning — `scenario_nextcloud_stop` executes again.

### `loop: false` (The Whole Chain at Once)
Each trigger event executes **ALL** scenarios from the list sequentially, all at once. The device does not remember anything between triggers.
This is used for the "single emergency command" or "one-shot action" pattern.

**Example from `config.json` (case intrusion sensor):**
```json
"hall_sensor_1": {
  "pipeline": ["scenario_shutdown"],
  "loop": false
}
```

Technically, the engine supports executing **multiple** scenarios in a row when `loop: false`. 
*(A made-up, but realistic example)*: Imagine that when the case intrusion sensor trips, you want to first log the event (print a Warning to the host), and then shut down the system with another scenario. This would look like a `loop: false` pipeline with two scenarios: `["scenario_log_alert", "scenario_shutdown"]`. They will both execute one after the other on a single Hall sensor trip.

> **Important Caveat:** Currently, you can only assemble such a pipeline (non-looping, with more than one scenario) **via Raw JSON** or by directly editing `config.json`. The "+Add" button in the Config Studio visual editor currently restricts non-looping pipelines to exactly one scenario.

---

## Scenario = The Actual Recipe

A scenario is a list of steps, where each step represents a single action on a specific output. 

Take a look at a real scenario from the config that weaves together commands for the keyboard (HID) and physical pins (GPIO) in a single list:

```json
"scenario_test_opto_pulse": [
  {"output": "hid", "action": "type", "value": "Pressing nettop button..."},
  {"output": "hid", "action": "key", "combo": "enter"},
  {"wait": 500},
  {"output": "opto_pwr", "action": "gpio_pulse"},
  {"wait": 500},
  {"output": "hid", "action": "type", "value": "Button released!"},
  {"output": "hid", "action": "key", "combo": "enter"}
]
```

**Line-by-line breakdown:**
1. Print a message to the host.
2. Press the Enter key.
3. Wait 500 milliseconds (half a second). *Note the short form `{"wait": 500}` — this is preferred over the older `{"action": "wait", "ms": 500}`, although the old one still works for backward compatibility.*
4. Pulse a physical GPIO pin (send a pulse to the optocoupler).
5. Wait 500 milliseconds again.
6. Print a second message.
7. Press Enter again.

This is exactly what **"weaving"** is: a single scenario can control both the keyboard and a physical pin in whatever order you need. You simply write out the recipe step by step.

---

## Output = Where It Actually Lands

A quick reminder (full details are in `configuration-guide.md`): output is what actually "fires" into the real world.
* Either it's emulating keystrokes on a USB-connected computer (`hid`).
* Or it's controlling a physical pin (`gpio` — relay, optocoupler, or whatever is connected to the Pico).

Each output has its own unique name, defined in the `config["outputs"]` block (for example, `"hid"`, `"opto_pwr"`). In each scenario step, you must specify this name in the `"output"` field.
**If the `"output"` field is omitted**, the engine will use `"hid"` by default — this is done intentionally for backward compatibility with older scenario formats.

---

## Composition Recipes

Here are a few ready-made patterns: when to use them and what to configure.

1. **Toggle a service (Start/Stop switch)**
   * **Where:** `active_menu`.
   * **Setup:** `loop: true`, 2 scenarios in the `pipeline`. Bound to a menu item for manual control.

2. **One-shot emergency action**
   * **Where:** `passive` (Hall sensor or INA226).
   * **Setup:** `loop: false`, 1 scenario in the `pipeline`. Important: for hardware sensors like Hall or INA226, the system automatically applies a `PRIORITY_HIGH` status (which hijacks control and executes immediately), so you don't need to configure this separately.

3. **Multi-step chain on a single trigger**
   * **Where:** Any trigger.
   * **Setup:** `loop: false`.
   * **Choice:** What's better — multiple scenarios in the pipeline (see the Raw JSON caveat above) OR one long scenario with a ton of steps? 
     * *Break it down into multiple scenarios* if a block of steps (like a logging scenario) will be reused in other pipelines.
     * *Write one long scenario* if it's a one-off, unique sequence that won't be used anywhere else.

4. **Mixed HID + GPIO scenario**
   * **Where:** In the `scenarios` block.
   * **Setup:** A single scenario containing steps with different `"output"` field values (like the `scenario_test_opto_pulse` broken down above).

5. **Power-on automation (auto_boot)**
   * **Where:** In the `outputs` block.
   * **Setup:** This is a separate auto-boot mechanic that **does not use pipelines at all**. It is configured directly inside the configuration of a specific GPIO output. Look for details in `configuration-guide.md`.

---

## Common Mistakes

1. **Forgetting to specify `output` in a step.**
   If you wanted to click a relay (`gpio`) but forgot to write `"output": "opto_pwr"`, the default `hid` will trigger. As a result, weird keystrokes will fly into the computer, and the relay won't click.
2. **Trying to build `loop: false` from multiple scenarios via the GUI.**
   Config Studio won't let you do this through the visual interface yet. Switch to the Raw JSON mode and edit the array manually.
3. **Confusion with pipeline item formats.**
   In `active_menu` (when `loop: true` is on), pipeline items are often written as objects: `{"scenario": "scenario_name", "label": "Display Name"}`. But in `passive`, it's usually just strings: `"scenario_shutdown"`. Don't confuse the `label` field (used to display status on the screen) with the technical `scenario` field (the reference to the key in the `scenarios` block).

---

## Related Documentation

* [configuration-guide.md](configuration-guide.md) — complete field schema for `config.json`.
* [config-editor.md](config-editor.md) — how to build a configuration in the UI.
* [active-triggers.md](../developers/active-triggers.md) / [passive-triggers.md](../developers/passive-triggers.md) — how it works "under the hood" in the code.
* [outputs.md](../developers/outputs.md) / [inputs.md](../developers/inputs.md) — how to add a new output/input.
