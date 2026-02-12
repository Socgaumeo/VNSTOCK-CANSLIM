#!/bin/bash
# Stop Telegram Bot
# Usage: ./stop_bot.sh

PID_FILE="/tmp/telegram_bot.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping bot (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Bot stopped."
    else
        echo "Bot not running (stale PID file)."
        rm -f "$PID_FILE"
    fi
else
    # Try to find by process name
    PIDS=$(pgrep -f "telegram_bot.py")
    if [ -n "$PIDS" ]; then
        echo "Found bot processes: $PIDS"
        kill $PIDS
        echo "Bot stopped."
    else
        echo "No bot process found."
    fi
fi
