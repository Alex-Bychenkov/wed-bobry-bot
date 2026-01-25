# Используем alpine для минимального размера образа (~50MB vs ~150MB slim)
FROM python:3.11-alpine

WORKDIR /app

ARG TIMEZONE=Europe/Moscow
ARG NOTIFY_TIME=10:00

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    TIMEZONE=${TIMEZONE} \
    NOTIFY_TIME=${NOTIFY_TIME} \
    TZ=${TIMEZONE}

# Устанавливаем только необходимые зависимости для сборки
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && apk add --no-cache tzdata

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps \
    && rm -rf /root/.cache /tmp/*

COPY . .

# Запускаем с оптимизацией памяти
CMD ["python", "-O", "bot.py"]
