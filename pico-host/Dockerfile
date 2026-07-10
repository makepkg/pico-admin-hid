FROM python:3.12-slim

# Устанавливаем необходимые утилиты для работы с блочными устройствами
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Flask
RUN pip install flask

# Копируем файлы приложения
COPY app.py /app.py
COPY static /static

CMD ["python3", "/app.py"]
