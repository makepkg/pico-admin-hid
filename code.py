"""
code.py — главный файл, склейка всех модулей.

Порядок инициализации важен:
  1. config.load()        — конфиг и состояние
  2. trigger_bus.init()   — HID-клавиатура (ДО любых fire())
  3. display              — дисплей
  4. passive              — датчики Холла, кнопка
  5. encoder              — энкодер с callback
"""

import time
import config
import trigger_bus
from encoder import (
    EncoderHandler,
    EV_ROTATE_LEFT,
    EV_ROTATE_RIGHT,
    EV_PRESS,
    EV_LONG_PRESS,
)
from display import DisplayManager
from passive import PassiveHandler


# ── 1. Конфигурация ────────────────────────────────────────────────────────

config.load()

# Корневое меню (неизменно на протяжении всей работы)
root_menu = config.get_config().get("active_menu", [])
menu_cursor = config.get_state().get("menu_cursor", 0)

# Текущий отображаемый список (при старте равен корневому)
current_menu_list = root_menu

# Стек для навигации назад: хранит кортежи (список_родителя, позиция_курсора)
menu_stack = []

# Защита от выхода за пределы (если конфиг урезали после сохранения позиции)
if root_menu and menu_cursor >= len(root_menu):
    menu_cursor = 0
elif not root_menu:
    menu_cursor = 0

print("[main] active_menu:", len(root_menu), "items")


# ── 2. Инициализация железа ────────────────────────────────────────────────

# ОБЯЗАТЕЛЬНО до любого fire() — поднимает HID-клавиатуру
trigger_bus.init()

print("[main] Init display...")
try:
    display = DisplayManager()
    display.show_boot()
except Exception as e:
    print("[main] Display init failed:", e)
    display = None

print("[main] Init passive sensors...")
passive = PassiveHandler()
passive.startup_blink()

print("[main] Init encoder...")
encoder = EncoderHandler()


# ── 3. Вспомогательные функции ─────────────────────────────────────────────

def get_current_label():
    """Имя текущего пункта меню."""
    if not current_menu_list:
        return "No menu"
    return current_menu_list[menu_cursor].get("label", "?")


def get_current_action():
    """Имя следующего действия в sequence (для нижней строки дисплея)."""
    if not current_menu_list:
        return ""
    item = current_menu_list[menu_cursor]
    # Папка без sequence — показываем индикатор вложенного меню
    if "sequence" not in item:
        return ">> Open"
    return trigger_bus.get_next_action_name(item["id"])


def refresh_menu():
    """Перерисовать меню без анимации."""
    if display and current_menu_list:
        display.draw_menu(get_current_label(), get_current_action())


def save_cursor():
    """Сохранить позицию курсора в state.json."""
    state = config.get_state()
    state["menu_cursor"] = menu_cursor
    config.save_state()


# ── 4. Сон и заставка экрана ────────────────────────────────────────────────

last_interaction_time = time.monotonic()
screen_sleeping = False
screensaver_active = False

# Загрузка параметров таймаута и типа заставки
device_cfg = config.get_config().get("device", {})
screen_timeout = device_cfg.get("screen_timeout_s", 0)  # 0 — отключено
screensaver_name = device_cfg.get("screensaver", "off") # "off", "tesseract", "starfield", "matrix"

next_anim_t = 0.0


def wake_up_display():
    """Пробуждение экрана из любого режима ожидания."""
    global last_interaction_time, screen_sleeping, screensaver_active
    last_interaction_time = time.monotonic()
    if display:
        if screensaver_active:
            display.stop_screensaver()
            screensaver_active = False
        if screen_sleeping:
            display.wake()
            screen_sleeping = False
        refresh_menu()
    print("[main] Display awake")


# ── 5. Callback энкодера ───────────────────────────────────────────────────

def on_encoder_event(event):
    """
    Вызывается из encoder.update() при каждом событии.
    Синхронный вызов — не делать тут долгих операций.
    """
    global menu_cursor, current_menu_list, last_interaction_time, screen_sleeping, screensaver_active

    # Если экран погас или активна заставка — пробуждаем его первым действием (игнорируя клик/поворот)
    if screen_sleeping or screensaver_active:
        wake_up_display()
        return

    # Сбрасываем таймер активности
    last_interaction_time = time.monotonic()

    if event == EV_ROTATE_RIGHT:
        if not current_menu_list:
            return
        old_label   = get_current_label()
        menu_cursor = (menu_cursor + 1) % len(current_menu_list)
        new_label   = get_current_label()
        save_cursor()
        if display:
            display.animate_swipe(old_label, new_label, direction="right")
            display.draw_menu(new_label, get_current_action())

    elif event == EV_ROTATE_LEFT:
        if not current_menu_list:
            return
        old_label   = get_current_label()
        menu_cursor = (menu_cursor - 1) % len(current_menu_list)
        new_label   = get_current_label()
        save_cursor()
        if display:
            display.animate_swipe(old_label, new_label, direction="left")
            display.draw_menu(new_label, get_current_action())

    elif event == EV_PRESS:
        if not current_menu_list:
            return

        item    = current_menu_list[menu_cursor]
        item_id = item["id"]
        lbl     = item.get("label", "?")

        # 1. Если есть sequence — выполняем команду
        if "sequence" in item:
            action = get_current_action()
            if display:
                display.show_executing(lbl, action)
            trigger_bus.fire_active(item_id)

        # 2. Если есть submenu — проваливаемся внутрь
        if "submenu" in item:
            menu_stack.append((current_menu_list, menu_cursor))
            current_menu_list = item["submenu"]
            menu_cursor = 0

        # Обновляем экран
        refresh_menu()

    elif event == EV_LONG_PRESS:
        # Возврат на уровень вверх
        if menu_stack:
            current_menu_list, menu_cursor = menu_stack.pop()
            refresh_menu()
        else:
            # Уже в корне — показываем статус
            print("[main] long press — root menu")
            if display:
                display.show_status("Root Menu", "Cannot go back", "")
                time.sleep(1.0)
                refresh_menu()


# Подключаем callback — с этого момента encoder.update() будет его вызывать
encoder.set_callback(on_encoder_event)


# ── 6. Первый кадр ─────────────────────────────────────────────────────────

refresh_menu()
print("[main] Ready!")


# ── 7. Главный цикл ────────────────────────────────────────────────────────

while True:
    # Пассивная система: датчики Холла, кнопка
    passive.update()

    # Активная система: энкодер — события идут через on_encoder_event()
    encoder.update()

    # Таймер автовыключения / заставки экрана
    now = time.monotonic()
    if screen_timeout > 0 and (now - last_interaction_time) > screen_timeout:
        if not screen_sleeping and not screensaver_active:
            if screensaver_name == "off":
                if display:
                    display.sleep()
                screen_sleeping = True
                print("[main] Display sleep")
            else:
                if display:
                    display.start_screensaver(screensaver_name)
                screensaver_active = True
                print("[main] Screensaver started:", screensaver_name)

    # Обновление кадров заставки (~20 FPS)
    if screensaver_active and now >= next_anim_t:
        if display:
            display.update_screensaver()
        next_anim_t = now + 0.05

    time.sleep(0.01)
