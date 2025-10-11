import os
import asyncio
from telegram.ext import Application
from transaction import TransactionProcessor


class BaseTelegramBot:
    def __init__(self):
        """Initialize Telegram bot with transaction processor"""
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN must be set")

        self.processor = TransactionProcessor()
        self.application = None

    def setup_handlers(self):
        """Setup all command and message handlers - to be overridden by subclasses"""
        pass

    async def run(self):
        """Run the bot"""
        self.application = Application.builder().token(self.token).build()

        # Setup handlers
        self.setup_handlers()

        # Start the bot
        print("\n" + "="*50)
        print("🤖 Telegram Bot Started")
        print("="*50)
        print("Bot is running and waiting for messages...")
        print("="*50 + "\n")

        # Disable signal handlers when running in a thread (not main thread)
        # This prevents "set_wakeup_fd only works in main thread" error
        await self.application.run_polling(
            allowed_updates=None,
            stop_signals=None  # Disable signal handlers
        )

    def run_sync(self):
        """Run the bot synchronously (for use in threads)"""
        # Create a new event loop for this thread
        # This is necessary because gunicorn workers may already have an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run())
        finally:
            loop.close()
