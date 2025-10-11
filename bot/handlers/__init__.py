"""
Telegram bot command handlers
Each handler module manages a specific command or set of related commands
"""

from .categories import setup_categories_handlers

__all__ = ['setup_categories_handlers']
