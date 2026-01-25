#!/bin/bash
# Скрипт для отправки тестового алерта в Alertmanager

SERVER_IP="87.247.157.122"
SERVER_USER="root"
SERVER_PASS="${SERVER_PASS:-F65NkiCBmM}"

# Определение команды SSH
if command -v sshpass &> /dev/null && [ -n "$SERVER_PASS" ]; then
    SSH_CMD="sshpass -p '$SERVER_PASS' ssh -o StrictHostKeyChecking=no -T"
else
    SSH_CMD="ssh"
fi

ALERT_NAME="${1:-TestAlert}"
SEVERITY="${2:-warning}"
SUMMARY="${3:-Тестовый алерт}"
DESCRIPTION="${4:-Это тестовое уведомление для проверки работы системы мониторинга}"

echo "📤 Отправка тестового алерта..."
echo "   Название: $ALERT_NAME"
echo "   Уровень: $SEVERITY"
echo "   Краткое описание: $SUMMARY"
echo ""

$SSH_CMD "$SERVER_USER@$SERVER_IP" << ENDSSH
cat > /tmp/test_alert.json << EOF
[
  {
    "labels": {
      "alertname": "$ALERT_NAME",
      "severity": "$SEVERITY",
      "instance": "test-server",
      "job": "test"
    },
    "annotations": {
      "summary": "$SUMMARY",
      "description": "$DESCRIPTION"
    },
    "startsAt": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
  }
]
EOF

curl -X POST http://localhost:9093/api/v1/alerts \\
  -H 'Content-Type: application/json' \\
  -d @/tmp/test_alert.json

echo ""
echo "✅ Тестовый алерт отправлен!"
echo ""
echo "⚠️  ВАЖНО: Убедитесь, что вы отправили команду /start боту @Bych_Server_Bot в Telegram,"
echo "   иначе уведомления не будут приходить!"
ENDSSH
