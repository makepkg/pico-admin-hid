import storage
import board
import digitalio
import usb_hid

# GP24 — кнопка.
# Если ЗАЖАТА во время boot → USB остаётся writable (режим разработки, файлы можно копировать)
# Если НЕ зажата           → ФС writable для кода (state.json сохраняется в рантайме)
btn = digitalio.DigitalInOut(board.GP24)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

if btn.value:  # btn.value=True → кнопка НЕ нажата
    storage.remount("/", readonly=False)

usb_hid.enable([usb_hid.Device.KEYBOARD])
