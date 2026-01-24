FROM python:3.11-alpine

WORKDIR /app

ARG TIMEZONE=Europe/Moscow
ARG NOTIFY_TIME=10:00

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIMEZONE=${TIMEZONE} \
    NOTIFY_TIME=${NOTIFY_TIME}

COPY requirements.txt ./
RUN apk add --no-cache tzdata
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
