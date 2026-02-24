#!/bin/bash
# Start Telegram Bot with caffeinate to prevent macOS sleep
# Usage: ./start_bot.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_FILE="/tmp/telegram_bot.log"
PID_FILE="/tmp/telegram_bot.pid"

cd "$SCRIPT_DIR"

# Kill existing bot if running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Stopping existing bot (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
fi

# Also kill any orphaned processes
pkill -f "telegram_bot.py" 2>/dev/null
sleep 1

echo "Starting Telegram Bot with caffeinate..."
echo "Python: $VENV_PYTHON"
echo "Log file: $LOG_FILE"

# Start bot with caffeinate to prevent idle/system sleep
nohup caffeinate -is "$VENV_PYTHON" telegram_bot.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Save PID
echo $BOT_PID > "$PID_FILE"

echo "Bot started with PID: $BOT_PID"
echo "To view logs: tail -f $LOG_FILE"
echo "To stop: ./stop_bot.sh"
