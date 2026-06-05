# Support

Thank you for using **Pico Commander**! This document provides guidance on how to get help with the project.

---

## 📚 Documentation

Before opening an issue, please check the available documentation:

### User Guides
- **[README.md](../README.md)** - Project overview, installation, and quick start
- **[QUICK_START.md](../QUICK_START.md)** - 10-minute setup guide
- **[Configuration Guide](../docs/user/configuration-guide.md)** - Complete config.json reference
- **[Config Editor Guide](../docs/user/config-editor.md)** - Visual editor instructions

### Developer Documentation
- **[Architecture](../docs/developers/architecture.md)** - System design and modules
- **[Passive Triggers](../docs/developers/passive-triggers.md)** - Hardware trigger system
- **[Active Triggers](../docs/developers/active-triggers.md)** - Menu trigger system

### Resources
- **[Video Demo](https://youtu.be/huUQviQJ-Cw)** - Watch the project in action
- **[Example Configuration](../config.json)** - Reference implementation

---

## 🐛 Found a Bug?

If you've discovered a bug, please help us fix it by:

1. **Check existing issues** - Search [open issues](https://github.com/USERNAME/pico-admin-hid/issues) to see if it's already reported
2. **Create a bug report** - If not found, [open a new issue](https://github.com/USERNAME/pico-admin-hid/issues/new)

### Bug Report Template

When reporting a bug, please include:

**Environment:**
- CircuitPython version (from `boot_out.txt`)
- Raspberry Pi Pico or Pico W
- Library versions (Adafruit bundle version)
- Operating system (if USB-related)

**Describe the bug:**
- Clear description of what happened
- Expected behavior vs actual behavior
- Steps to reproduce

**Configuration:**
- Relevant sections of your `config.json`
- Hardware wiring (if different from default)

**Logs/Errors:**
- Error messages from serial console
- Traceback if available

**Example:**
```
Environment:
- CircuitPython 9.0.5
- Raspberry Pi Pico
- Adafruit Bundle 9.x-20240601
- Windows 11

Bug:
OLED display shows corrupted characters when menu items have special symbols.

Steps to reproduce:
1. Add menu item with label "Test → Item"
2. Navigate to that item
3. Display shows garbled text

Expected: Arrow symbol renders correctly
Actual: Random characters appear
```

---

## 💡 Feature Request?

Have an idea to improve Pico Commander?

1. **Check existing requests** - Browse [issues labeled "enhancement"](https://github.com/USERNAME/pico-admin-hid/labels/enhancement)
2. **Submit your idea** - [Open a feature request](https://github.com/USERNAME/pico-admin-hid/issues/new)

### Feature Request Template

Please describe:
- **Use case** - What problem does this solve?
- **Proposed solution** - How should it work?
- **Alternatives** - Other ways you've considered
- **Additional context** - Examples, mockups, references

---

## ❓ Questions & Help

### Installation Issues

**Problem:** CircuitPython not recognized
- **Solution:** Reflash UF2 firmware, try different USB cable/port
- **Guide:** [Installation Step 1](../README.md#step-1-flash-circuitpython-firmware)

**Problem:** "No module named..." error
- **Solution:** Verify library files in `lib/` folder match your CircuitPython version
- **Guide:** [Installation Step 2](../README.md#step-2-install-required-libraries)

**Problem:** OLED display blank
- **Solution:** Check I2C wiring (SDA→GP4, SCL→GP5), verify address 0x3C
- **Test:** Use I2C scanner script to detect display

**Problem:** Encoder doesn't respond
- **Solution:** Verify pin configuration in `config.json` matches physical wiring
- **Check:** `encoder_clk`, `encoder_dt`, `encoder_sw` settings

### Configuration Issues

**Problem:** Scenarios don't execute
- **Solution:** Check USB connection is active, verify scenario name in menu `sequence`
- **Debug:** Open text editor on computer, test if keystrokes appear

**Problem:** Menu navigation broken
- **Solution:** Validate `config.json` syntax (use Config Editor or online JSON validator)
- **Check:** Ensure `active_menu` array structure is correct

**Problem:** Hall sensors not triggering
- **Solution:** Check `device.armed` is `true`, verify sensor polarity (active-low/high)
- **Test:** Watch serial console for trigger events

### Hardware Issues

**Problem:** Device not detected as USB HID
- **Solution:** Verify `boot.py` enables HID with `usb_hid.enable()`
- **Reboot:** Try Normal Mode (boot without GP24 button pressed)

**Problem:** High power consumption
- **Solution:** Enable screensaver with shorter timeout, reduce OLED brightness
- **Setting:** `device.screen_timeout_s` in `config.json`

---

## 🔍 Troubleshooting Checklist

Before asking for help, verify:

- [ ] CircuitPython version 9.0+ installed
- [ ] All 3 libraries copied to `CIRCUITPY/lib/`
- [ ] All `.py` files copied to CIRCUITPY root
- [ ] `config.json` has valid JSON syntax
- [ ] Hardware pins match `config.json` settings
- [ ] USB cable supports data transfer (not power-only)
- [ ] Booted in correct mode (Normal for runtime, Dev for editing)
- [ ] Serial console checked for error messages

---

## 💬 Community Discussion

For general questions, usage tips, and community support:

- **GitHub Discussions** - Coming soon
- **Issues** - [Open an issue](https://github.com/USERNAME/pico-admin-hid/issues) with `[Question]` tag

---

## 🤝 Contributing

Want to help improve Pico Commander?

- **Report bugs** - Help us identify issues
- **Submit PRs** - Code contributions welcome
- **Improve docs** - Fix typos, add examples, clarify instructions
- **Share use cases** - Tell us how you're using the project

See [CONTRIBUTORS.md](../CONTRIBUTORS.md) for contribution guidelines.

---

## 📧 Direct Contact

For sensitive issues (security vulnerabilities, licensing questions):

- **GitHub Issues** - Preferred for all public support
- **Email** - (Add your email if you want direct contact)

**Response time:** Best effort, typically within 48-72 hours for GitHub issues.

---

## 💰 Support Development

If Pico Commander helped you, consider supporting development:

**USDT BEP-20**: `0xd03499C9c6100Af624603b4D6fb185A65694745C`  
**USDT TRC-20**: `TUAzeSrKeDYbt6HCs9PL6q1t5amHHdnnwR`  
**USDT SOLANA**: `2cecCCh8pzUNmEpjLQ3aa9sfPL5KXqANrmSfiiDWubCj`

Or simply ⭐ **star the repository** to show your support!

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](../LICENSE) for details.

---

**Thank you for using Pico Commander!** 🎮
