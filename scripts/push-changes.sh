#!/bin/bash
# Скрипт для отправки изменений в новую ветку

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверяем, есть ли изменения
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}Нет изменений для коммита${NC}"
    exit 0
fi

# Получаем название ветки от пользователя или генерируем
if [ -n "$1" ]; then
    BRANCH_NAME="$1"
else
    # Генерируем имя ветки на основе даты
    BRANCH_NAME="update/$(date +%Y-%m-%d-%H%M)"
fi

# Получаем сообщение коммита
if [ -n "$2" ]; then
    COMMIT_MSG="$2"
else
    echo -e "${YELLOW}Введите описание изменений:${NC}"
    read -r COMMIT_MSG
    if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="Обновление $(date +%Y-%m-%d)"
    fi
fi

echo ""
echo "📋 Текущие изменения:"
git status --short
echo ""

# Убедимся, что мы на main и он актуален
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Вы не на ветке main. Переключаюсь..."
    git stash
    git checkout main
    git pull origin main
    git stash pop || true
fi

# Создаём новую ветку
echo "🌿 Создаю ветку: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

# Добавляем и коммитим изменения
git add .
git commit -m "$COMMIT_MSG"

# Пушим в удалённый репозиторий
echo "📤 Отправляю в GitHub..."
git push -u origin "$BRANCH_NAME"

echo ""
echo -e "${GREEN}✅ Готово!${NC}"
echo ""
echo "Следующие шаги:"
echo "1. Перейдите на GitHub: https://github.com/Alex-Bychenkov/wed-bobry-bot"
echo "2. Создайте Pull Request из ветки '$BRANCH_NAME' в 'main'"
echo "3. Проверьте изменения и нажмите 'Merge'"
echo "4. Запустите деплой: Actions → Deploy to Server → Run workflow"
echo ""

# Возвращаемся на main
git checkout main
