#!/bin/bash

# Start Telegram bot in background
python bot_main.py &

# Start Flask API in foreground
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
