#!/bin/bash

# Переходим в папку с Lavalink
cd ~/Documents/discord-navidrome-bot/lavalink

# Запускаем Lavalink в фоне
echo "Запуск Lavalink..."
java -jar Lavalink.jar &
LAVALINK_PID=$!

# Ждём, пока Lavalink запустится (проверяем порт 2333)
echo "Ожидание запуска Lavalink..."
while ! curl -s http://127.0.0.1:2333/version > /dev/null; do
  sleep 1
done
echo "Lavalink готов!"

# Возвращаемся в корень проекта и запускаем бота
cd ~/Documents/discord-navidrome-bot
source venv/bin/activate
echo "Запуск бота..."
python bot.py

# Когда бот остановится (Ctrl+C), останавливаем и Lavalink
kill $LAVALINK_PID
