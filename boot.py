import storage
import board
import digitalio
import usb_hid
import usb_cdc

usb_cdc.enable(console=True, data=True)

# GP24 — кнопка USR на плате
# ЗАЖМИ USR при подключении → USB writable (можно копировать файлы)
# Не зажимай USR → FS read-only для USB, writable для кода
btn = digitalio.DigitalInOut(board.GP24)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

if not btn.value:  # USR ЗАЖАТА → USB writable
    storage.remount("/", readonly=False)

usb_hid.enable([usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE])
