from flask import Flask
from routes import webhook_bp, transaction_bp
from bot import TelegramBot
import os
import threading

# Initialize Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(webhook_bp)
app.register_blueprint(transaction_bp)

def run_telegram_bot():
    """Run Telegram bot in a separate thread"""
    try:
        bot = TelegramBot()
        bot.run_sync()
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))

    print(f"\n{'='*50}")
    print(f"🚀 Budget Tracker API")
    print(f"{'='*50}")
    print(f"📍 Port: {port}")
    print(f"\n📊 Webhooks:")
    print(f"  • SePay:  /webhook/sepay")
    print(f"  • Email:  /webhook/email")
    print(f"\n📈 Transactions:")
    print(f"  • Stats:         /stats")
    print(f"  • Recent:        /transactions/recent")
    print(f"  • By Account:    /transactions/by-account/<account>")
    print(f"  • By Category:   /transactions/by-category/<category>")
    print(f"\n🧪 Testing:")
    print(f"  • Health:        /health")
    print(f"  • Test SePay:    /test")
    print(f"  • Test Email:    /test/email")
    print(f"\n🤖 Telegram Bot:")
    print(f"  • Starting bot in background...")
    print(f"{'='*50}\n")

    # Start Telegram bot in a separate thread
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        bot_thread.start()
        print("✅ Telegram bot thread started")
    else:
        print("⚠️  TELEGRAM_BOT_TOKEN not set - bot will not start")

    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=False)