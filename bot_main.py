import os
from telegram.ext import Application, CommandHandler
from telegram.error import Conflict
import sys
import time

from handlers.list_handler import list_command
from handlers.category_handler import category_command


def main():
    """Main function"""
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN not set")
            sys.exit(1)

        # Create application
        application = Application.builder().token(token).build()

        # Add command handlers
        application.add_handler(CommandHandler("list", list_command))
        application.add_handler(CommandHandler("category", category_command))

        # Start bot
        print("🤖 Starting Budget Tracker Bot...")
        print("📊 Commands: /list, /category")
        print("🚀 Bot is running!")

        application.run_polling()

    except Conflict:
        print("⛔ Bot conflict: Another instance is running!")
        sys.exit(1)

    except Exception as e:
        print(f"⛔ Error: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(30)
        main()


if __name__ == "__main__":
    main()
