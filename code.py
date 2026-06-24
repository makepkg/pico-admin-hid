"""
code.py — главный файл, склейка всех модулей.

Порядок инициализации важен:
  1. config.load()        — конфиг и состояние
  2. trigger_bus.init()   — HID-клавиатура (ДО любых fire())
  3. display              — дисплей
  4. inputs_manager       — датчики (Hall, INA226, кнопка) через InputsManager
  5. encoder              — энкодер с callback
  6. warning_screen       — варнинг оверлей (низкий заряд)
  7. splash_screen        — HUD батареи во время скринсейвера
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
from inputs_manager import InputsManager
from splash_trigger import SplashTrigger
from splash_screen import SplashScreen
from warning_screen import WarningScreen


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

splash_trigger = SplashTrigger()
splash_screen = SplashScreen(display._disp) if display else None
warning_screen = WarningScreen(display._disp) if display else None

print("[main] Init inputs manager (Hall sensors, INA226, button)...")
inputs = InputsManager(i2c=display.i2c if display else None)
inputs.startup_blink()

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
        # Если сплеш активен — он сам восстановит root_group, форсируем hide
        if splash_screen and splash_screen.is_active:
            splash_screen._hide()
            
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

    # ── Warning screen interception ───────────────────────────────────
    if warning_screen and warning_screen.is_active:
        if event == EV_PRESS:
            # Центр: отменить триггер, показать CANCELED
            inputs.cancel_ina_trigger()
            warning_screen.show_canceled()
        elif event in (EV_ROTATE_LEFT, EV_ROTATE_RIGHT):
            # Скролл: dismiss warning без cooldown (snooze до восстановления батареи)
            inputs.dismiss_ina_warning()
            warning_screen.hide()
        # EV_LONG_PRESS — пропускаем в обычную логику
        if event != EV_LONG_PRESS:
            return   # блокируем обычную обработку
    # ── конец перехвата ───────────────────────────────────────────

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
        if display:
            display.animate_swipe(old_label, new_label, direction="right")
            display.draw_menu(new_label, get_current_action())

    elif event == EV_ROTATE_LEFT:
        if not current_menu_list:
            return
        old_label   = get_current_label()
        menu_cursor = (menu_cursor - 1) % len(current_menu_list)
        new_label   = get_current_label()
        if display:
            display.animate_swipe(old_label, new_label, direction="left")
            display.draw_menu(new_label, get_current_action())

    elif event == EV_PRESS:
        if not current_menu_list:
            return

        item    = current_menu_list[menu_cursor]
        item_id = item["id"]
        lbl     = item.get("label", "?")

        # 1. Если есть sequence или pipeline — выполняем команду
        if "sequence" in item or "pipeline" in item:
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


# ── 7. Auto-Boot при отсутствии USB ────────────────────────────────────────

import supervisor

# ── 7. Auto-Boot Configuration ─────────────────────────────────────────────
# Ищем GPIO output с включенным auto_boot

auto_boot_enabled = False
auto_boot_next_check = time.monotonic() + 5
auto_boot_in_progress = False
auto_boot_last_attempt = 0
auto_boot_attempt_start = 0
auto_boot_output_name = None
check_interval = 15  # default, переопределяется из config
max_attempts = 2     # default, переопределяется из config
retry_cooldown_min = 5

outputs_cfg = config.get_config().get("outputs", {})

for output_name, output_cfg in outputs_cfg.items():
    # Ищем GPIO output с auto_boot секцией
    if output_cfg.get("type") != "gpio":
        continue
    
    auto_boot_cfg = output_cfg.get("auto_boot")
    if not auto_boot_cfg:
        continue
    
    if not auto_boot_cfg.get("enabled", False):
        continue
    
    # Проверка что сам output включен
    if not output_cfg.get("enabled", False):
        print(f"[auto_boot] WARNING: output '{output_name}' has auto_boot enabled but output itself is disabled — SKIPPED")
        continue
    
    # Нашли активный auto_boot
    auto_boot_enabled = True
    auto_boot_output_name = output_name
    check_interval = auto_boot_cfg.get("check_interval_s", 15)
    max_attempts = auto_boot_cfg.get("max_attempts", 2)
    retry_cooldown_min = auto_boot_cfg.get("retry_cooldown_min", 5)
    
    print(f"[auto_boot] Enabled: check_interval={check_interval}s, attempts={max_attempts}, retry_cooldown={retry_cooldown_min}min")
    print(f"[auto_boot] Output: '{output_name}' (GPIO pin {output_cfg.get('pin')})")
    print(f"[auto_boot] Will execute gpio_pulse directly on output")
    print(f"[auto_boot] First check in 5 seconds...")
    
    break  # Используем только первый найденный

if not auto_boot_enabled:
    print("[auto_boot] Disabled (no GPIO output with auto_boot.enabled found)")



# ── 8. Главный цикл ────────────────────────────────────────────────────────

while True:
    # Inputs system: датчики, кнопка
    inputs.update()

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
                splash_trigger.reset_timer()  # Сброс таймера при входе в screensaver
                print("[main] Screensaver started:", screensaver_name)

    # Обновление кадров заставки (~20 FPS)
    ina_warning_blocking = warning_screen and warning_screen.is_active
    if screensaver_active and now >= next_anim_t and not ina_warning_blocking:
        if display:
            display.update_screensaver()
        next_anim_t = now + 0.05

    # --- INA226 Warning logic ---
    if warning_screen and inputs.ina_warning_active:
        if not warning_screen.is_active:
            pct = inputs.ina_warning_percent or 0
            warning_screen.show(pct)

    if warning_screen and warning_screen.is_active:
        warning_screen.tick()

    # --- INA226 Splash logic ---
    is_idle = screensaver_active or screen_sleeping

    if not ina_warning_blocking:
        if splash_screen and splash_screen.is_active:
            splash_screen.tick()
        else:
            # Check INA226 availability before triggering splash
            power_monitor = inputs.get_power_monitor("ina226")
            ina_available = power_monitor is not None and power_monitor.available
            
            if splash_screen and splash_trigger.tick(is_idle, ina_available):
                # Если дисплей спал — разбудить перед показом
                if screen_sleeping:
                    display.wake()
                    screen_sleeping = False
                
                # Get metrics from power monitor
                if power_monitor:
                    metrics = power_monitor.get_metrics()
                    if metrics is not None:
                        splash_screen.show(metrics)

    # --- Auto-Boot циклическая проверка ---
    try:
        if auto_boot_enabled and not auto_boot_in_progress and now >= auto_boot_next_check:
            # Проверяем USB ДО начала цикла
            usb_state = supervisor.runtime.usb_connected
            
            # Логирование начала проверки (первый раз — очистить лог)
            try:
                log_mode = "w" if auto_boot_last_attempt == 0 and auto_boot_next_check <= now + 10 else "a"
                with open("/auto_boot_log.txt", log_mode) as log:
                    if log_mode == "w":
                        log.write(f"=== AUTO_BOOT LOG START ({now:.1f}s) ===\n")
                    log.write(f"[{now:.1f}] Check: usb={usb_state}, next_check={auto_boot_next_check:.1f}\n")
            except:
                pass
            
            if usb_state:
                print(f"[auto_boot] USB connected — skipping cycle")
                auto_boot_next_check = now + 15  # Проверять каждые 15 сек пока USB подключен
            else:
                # Начинаем новый цикл проверки
                auto_boot_in_progress = True
                auto_boot_last_attempt = 0  # Сброс счётчика
                auto_boot_attempt_start = now
                
                print(f"[auto_boot] Starting check cycle (retry_cooldown={retry_cooldown_min}min)")
                
                # Логирование старта цикла
                try:
                    with open("/auto_boot_log.txt", "a") as log:
                        log.write(f"[{now:.1f}] CYCLE START: usb={usb_state}\n")
                except:
                    pass
        
        if auto_boot_enabled and auto_boot_in_progress:
            # Вычисляем текущую попытку по времени
            elapsed = now - auto_boot_attempt_start
            current_attempt = int(elapsed / check_interval) + 1
            
            # Новая попытка: current_attempt больше чем last_attempt
            if current_attempt > auto_boot_last_attempt:
                auto_boot_last_attempt = current_attempt
                
                usb_state = supervisor.runtime.usb_connected
                
                # Логирование попытки
                try:
                    with open("/auto_boot_log.txt", "a") as log:
                        log.write(f"[{now:.1f}] Attempt {current_attempt}/{max_attempts}: usb={usb_state}, elapsed={elapsed:.1f}s\n")
                except:
                    pass
                
                # Проверяем USB
                if usb_state:
                    print(f"[auto_boot] USB connected — cycle canceled")
                    auto_boot_in_progress = False
                    # Следующая проверка через retry_cooldown
                    auto_boot_next_check = now + (retry_cooldown_min * 60)
                    print(f"[auto_boot] Next check in {retry_cooldown_min} minutes")
                    
                    # Логирование отмены
                    try:
                        with open("/auto_boot_log.txt", "a") as log:
                            log.write(f"[{now:.1f}] CYCLE CANCELED: USB detected\n")
                    except:
                        pass
                
                elif current_attempt <= max_attempts:
                    print(f"[auto_boot] Attempt {current_attempt}/{max_attempts}: USB not connected")
                    
                    # Последняя попытка — запускаем сценарий
                    if current_attempt == max_attempts:
                        print(f"[auto_boot] Max attempts reached — triggering GPIO pulse on '{auto_boot_output_name}'")
                        
                        # Логирование запуска
                        try:
                            with open("/auto_boot_log.txt", "a") as log:
                                log.write(f"[{now:.1f}] TRIGGERING GPIO: {auto_boot_output_name}\n")
                        except:
                            pass
                        
                        if display:
                            display.show_status("Auto-Boot", "Starting server...", "")
                            time.sleep(1.5)
                            refresh_menu()
                        
                        # Вызываем execute через публичный API
                        success = trigger_bus.execute_output(auto_boot_output_name, {"action": "gpio_pulse"})
                        
                        if success:
                            print(f"[auto_boot] GPIO pulse executed successfully")
                        else:
                            print(f"[auto_boot] WARNING: GPIO pulse failed")
                        
                        # Логирование завершения
                        try:
                            with open("/auto_boot_log.txt", "a") as log:
                                log.write(f"[{now:.1f}] GPIO PULSE {'SUCCESS' if success else 'FAILED'}\n")
                        except:
                            pass
                        
                        auto_boot_in_progress = False
                        # Следующая проверка через retry_cooldown
                        auto_boot_next_check = now + (retry_cooldown_min * 60)
                        print(f"[auto_boot] Next check in {retry_cooldown_min} minutes")
    
    except Exception as e:
        # Критическая ошибка в auto_boot
        try:
            with open("/auto_boot_log.txt", "a") as log:
                log.write(f"[{now:.1f}] ERROR: {e}\n")
        except:
            pass
        print(f"[auto_boot] CRITICAL ERROR:", e)
        auto_boot_in_progress = False
        auto_boot_next_check = now + 60  # Повтор через минуту при ошибке

    time.sleep(0.01)

