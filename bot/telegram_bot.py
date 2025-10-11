from .base_bot import BaseTelegramBot
from .handlers import setup_categories_handlers


class TelegramBot(BaseTelegramBot):
    """
    Main Telegram bot class that integrates all command handlers
    """

    def setup_handlers(self):
        """Setup all command and message handlers"""
        # Setup categories handlers (includes /list command)
        setup_categories_handlers(self.application, self)
