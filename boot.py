import storage
import board
import digitalio
import usb_hid

# GP24 — кнопка USR на плате
# ЗАЖМИ USR при подключении → USB writable (можно копировать файлы)
# Не зажимай USR → FS read-only для USB, writable для кода
btn = digitalio.DigitalInOut(board.GP24)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

if not btn.value:  # USR ЗАЖАТА → USB writable
    storage.remount("/", readonly=False)

usb_hid.enable([usb_hid.Device.KEYBOARD])
