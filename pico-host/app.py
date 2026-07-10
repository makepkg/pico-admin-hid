from flask import Flask, request, jsonify, send_from_directory
import json
import subprocess
import os

app = Flask(__name__, static_folder="static")
MOUNT_POINT = "/mnt/pico"
CONFIG_PATH = f"{MOUNT_POINT}/config.json"

# Флаг состояния: смонтирован ли раздел в рамках текущей сессии редактирования
mount_session_active = False

def find_circuitpy_device():
    """Находит блочное устройство с LABEL=CIRCUITPY через blkid"""
    try:
        result = subprocess.run(
            ["blkid", "-L", "CIRCUITPY"],
            capture_output=True,
            text=True,
            check=True
        )
        device = result.stdout.strip()
        if not device:
            return None
        return device
    except subprocess.CalledProcessError:
        return None

def is_mounted(device):
    """Проверяет, смонтировано ли устройство уже"""
    try:
        result = subprocess.run(
            ["mount"],
            capture_output=True,
            text=True,
            check=True
        )
        return device in result.stdout
    except subprocess.CalledProcessError:
        return False

def mount_device(device):
    """Монтирует устройство в MOUNT_POINT"""
    global mount_session_active
    
    # Создаём точку монтирования если её нет
    os.makedirs(MOUNT_POINT, exist_ok=True)
    
    # Проверяем, не смонтировано ли уже
    if is_mounted(device):
        mount_session_active = True
        return True
    
    try:
        subprocess.run(
            ["mount", device, MOUNT_POINT],
            capture_output=True,
            text=True,
            check=True
        )
        mount_session_active = True
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Ошибка монтирования {device}: {e.stderr}")

def unmount_device():
    """Размонтирует раздел"""
    global mount_session_active
    
    try:
        subprocess.run(
            ["sync"],
            check=True
        )
        subprocess.run(
            ["umount", MOUNT_POINT],
            capture_output=True,
            text=True,
            check=True
        )
        mount_session_active = False
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Ошибка размонтирования: {e.stderr}")

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.get("/api/config")
def get_config():
    """
    Находит раздел CIRCUITPY, монтирует его (если ещё не смонтирован),
    читает config.json и возвращает клиенту.
    Раздел остаётся смонтированным до POST /api/config или /api/config/cancel.
    """
    device = find_circuitpy_device()
    if not device:
        return jsonify({
            "error": "Pico не подключен или не виден системе",
            "details": "Раздел с LABEL=CIRCUITPY не найден"
        }), 503
    
    try:
        mount_device(device)
    except RuntimeError as e:
        return jsonify({
            "error": "Не удалось смонтировать раздел",
            "details": str(e)
        }), 500
    
    # Читаем config.json
    try:
        with open(CONFIG_PATH) as f:
            config_data = json.load(f)
        return jsonify(config_data)
    except FileNotFoundError:
        return jsonify({
            "error": "Файл config.json не найден на устройстве",
            "details": f"Ожидается файл: {CONFIG_PATH}"
        }), 404
    except json.JSONDecodeError as e:
        return jsonify({
            "error": "Невалидный JSON в config.json",
            "details": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Ошибка чтения config.json",
            "details": str(e)
        }), 500

@app.post("/api/config")
def save_config():
    """
    Сохраняет конфиг в config.json на уже смонтированном разделе,
    вызывает sync() и размонтирует раздел.
    Если раздел не смонтирован (не было предварительного GET) — возвращает 409.
    """
    global mount_session_active
    
    if not mount_session_active:
        return jsonify({
            "error": "Нет активной сессии редактирования",
            "details": "Сначала откройте конфигурацию через GET /api/config"
        }), 409
    
    # Записываем конфиг
    try:
        config_data = request.get_json()
        with open(CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        return jsonify({
            "error": "Ошибка записи config.json",
            "details": str(e)
        }), 500
    
    # Размонтируем
    try:
        unmount_device()
        return jsonify({
            "status": "ok",
            "unmounted": True
        })
    except RuntimeError as e:
        return jsonify({
            "error": "Конфиг записан, но не удалось размонтировать раздел",
            "details": str(e)
        }), 500

@app.post("/api/config/cancel")
def cancel_config():
    """
    Аварийное размонтирование раздела без записи конфига.
    Используется если пользователь закрыл вкладку или передумал.
    """
    global mount_session_active
    
    if not mount_session_active:
        return jsonify({
            "status": "ok",
            "message": "Раздел не был смонтирован"
        })
    
    try:
        unmount_device()
        return jsonify({
            "status": "ok",
            "unmounted": True,
            "message": "Раздел размонтирован без сохранения изменений"
        })
    except RuntimeError as e:
        return jsonify({
            "error": "Не удалось размонтировать раздел",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9191)
