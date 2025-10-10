import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from transaction import TransactionProcessor

# Conversation states
SELECTING_QUERY_TYPE, SELECTING_ACCOUNT, SELECTING_CATEGORY, SELECTING_DATE_RANGE = range(4)

class TelegramBot:
    def __init__(self):
        """Initialize Telegram bot with transaction processor"""
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN must be set")

        self.processor = TransactionProcessor()
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
👋 Welcome to Budget Tracker Bot!

I can help you query and analyze your transactions.

📊 Available Commands:
/stats - View transaction statistics
/recent - Show recent transactions
/accounts - View transactions by account
/categories - View transactions by category
/search - Search transactions
/help - Show this help message

Let's get started! Try /stats to see your overview.
        """
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 Budget Tracker Bot Help

📊 Commands:
• /start - Welcome message
• /stats - Transaction statistics overview
• /recent [limit] - Recent transactions (default: 10)
• /accounts - List all accounts and query by account
• /categories - List all categories and query by category
• /search - Interactive search
• /help - This help message

💡 Examples:
• /recent 5 - Show last 5 transactions
• /accounts - Choose account to view
• /categories - Choose category to view

❓ Need more help? Just ask!
        """
        await update.message.reply_text(help_text)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show transaction statistics"""
        try:
            # Get total count
            total_response = self.processor.supabase.table("transactions").select("id", count="exact").execute()
            total_count = total_response.count if hasattr(total_response, 'count') else 0

            # Get account stats
            accounts_response = self.processor.supabase.table("transactions").select("account").execute()
            categories_response = self.processor.supabase.table("transactions").select("category, transfer_amount, transfer_type").execute()

            account_stats = {}
            category_stats = {}
            uncategorized = 0
            total_income = 0
            total_expense = 0

            if accounts_response.data:
                for t in accounts_response.data:
                    acc = t.get("account", "Unknown")
                    account_stats[acc] = account_stats.get(acc, 0) + 1

            if categories_response.data:
                for t in categories_response.data:
                    cat = t.get("category", "Uncategorized")
                    amount = float(t.get("transfer_amount", 0))
                    trans_type = t.get("transfer_type", "in")

                    category_stats[cat] = category_stats.get(cat, 0) + 1
                    if cat == "Uncategorized":
                        uncategorized += 1

                    if trans_type == "in":
                        total_income += amount
                    else:
                        total_expense += amount

            # Format response
            stats_message = f"""
📊 Transaction Statistics

📈 Overview:
• Total Transactions: {total_count}
• Categorized: {total_count - uncategorized}
• Uncategorized: {uncategorized}

💰 Financial Summary:
• Total Income: {total_income:,.0f} VND
• Total Expense: {total_expense:,.0f} VND
• Net: {total_income - total_expense:,.0f} VND

🏦 By Account:
"""
            for acc, count in sorted(account_stats.items(), key=lambda x: x[1], reverse=True):
                stats_message += f"• {acc}: {count} transactions\n"

            stats_message += "\n🏷️ By Category:\n"
            for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                stats_message += f"• {cat}: {count} transactions\n"

            if len(category_stats) > 10:
                stats_message += f"\n... and {len(category_stats) - 10} more categories"

            await update.message.reply_text(stats_message)

        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching stats: {str(e)}")

    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recent command - show recent transactions"""
        try:
            # Get limit from args or default to 10
            limit = 10
            if context.args and len(context.args) > 0:
                try:
                    limit = int(context.args[0])
                    limit = min(limit, 50)  # Cap at 50
                except ValueError:
                    pass

            response = self.processor.supabase.table("transactions").select("*").order("transaction_date", desc=True).limit(limit).execute()

            if not response.data:
                await update.message.reply_text("No transactions found.")
                return

            message = f"📋 Recent {len(response.data)} Transactions:\n\n"

            for i, txn in enumerate(response.data, 1):
                date = datetime.fromisoformat(txn.get("transaction_date", ""))
                amount = float(txn.get("transfer_amount", 0))
                trans_type = txn.get("transfer_type", "in")
                symbol = "💵" if trans_type == "in" else "💸"

                message += f"{i}. {symbol} {txn.get('account', 'N/A')}\n"
                message += f"   {date.strftime('%d/%m/%Y %H:%M')}\n"
                message += f"   {amount:,.0f} VND - {txn.get('content', 'No description')}\n"
                message += f"   Category: {txn.get('category', 'Uncategorized')}\n\n"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching recent transactions: {str(e)}")

    async def accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /accounts command - show account selection"""
        try:
            response = self.processor.supabase.table("transactions").select("account").execute()

            if not response.data:
                await update.message.reply_text("No accounts found.")
                return

            # Get unique accounts with counts
            account_counts = {}
            for txn in response.data:
                acc = txn.get("account", "Unknown")
                account_counts[acc] = account_counts.get(acc, 0) + 1

            # Create inline keyboard
            keyboard = []
            for acc, count in sorted(account_counts.items()):
                keyboard.append([InlineKeyboardButton(f"{acc} ({count})", callback_data=f"account:{acc}")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🏦 Select an account:", reply_markup=reply_markup)

        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching accounts: {str(e)}")

    async def categories_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /categories command - show category selection"""
        try:
            response = self.processor.supabase.table("transactions").select("category").execute()

            if not response.data:
                await update.message.reply_text("No categories found.")
                return

            # Get unique categories with counts
            category_counts = {}
            for txn in response.data:
                cat = txn.get("category", "Uncategorized")
                category_counts[cat] = category_counts.get(cat, 0) + 1

            # Create inline keyboard
            keyboard = []
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                keyboard.append([InlineKeyboardButton(f"{cat} ({count})", callback_data=f"category:{cat}")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🏷️ Select a category:", reply_markup=reply_markup)

        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching categories: {str(e)}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        data = query.data

        try:
            if data.startswith("account:"):
                account = data.split(":", 1)[1]
                await self.show_account_transactions(query, account)

            elif data.startswith("category:"):
                category = data.split(":", 1)[1]
                await self.show_category_transactions(query, category)

        except Exception as e:
            await query.message.reply_text(f"❌ Error: {str(e)}")

    async def show_account_transactions(self, query, account: str):
        """Show transactions for a specific account"""
        try:
            response = self.processor.supabase.table("transactions").select("*").eq("account", account).order("transaction_date", desc=True).limit(20).execute()

            if not response.data:
                await query.message.reply_text(f"No transactions found for {account}")
                return

            message = f"🏦 Transactions for {account} (Last 20):\n\n"

            total_in = 0
            total_out = 0

            for i, txn in enumerate(response.data, 1):
                date = datetime.fromisoformat(txn.get("transaction_date", ""))
                amount = float(txn.get("transfer_amount", 0))
                trans_type = txn.get("transfer_type", "in")
                symbol = "💵" if trans_type == "in" else "💸"

                if trans_type == "in":
                    total_in += amount
                else:
                    total_out += amount

                message += f"{i}. {symbol} {date.strftime('%d/%m/%Y %H:%M')}\n"
                message += f"   {amount:,.0f} VND - {txn.get('content', 'No description')}\n"
                message += f"   Category: {txn.get('category', 'Uncategorized')}\n\n"

            message += f"\n📊 Summary:\n"
            message += f"• Income: {total_in:,.0f} VND\n"
            message += f"• Expense: {total_out:,.0f} VND\n"
            message += f"• Net: {total_in - total_out:,.0f} VND"

            await query.message.reply_text(message)

        except Exception as e:
            await query.message.reply_text(f"❌ Error: {str(e)}")

    async def show_category_transactions(self, query, category: str):
        """Show transactions for a specific category"""
        try:
            response = self.processor.supabase.table("transactions").select("*").eq("category", category).order("transaction_date", desc=True).limit(20).execute()

            if not response.data:
                await query.message.reply_text(f"No transactions found for {category}")
                return

            message = f"🏷️ Transactions for {category} (Last 20):\n\n"

            total_amount = 0

            for i, txn in enumerate(response.data, 1):
                date = datetime.fromisoformat(txn.get("transaction_date", ""))
                amount = float(txn.get("transfer_amount", 0))
                trans_type = txn.get("transfer_type", "in")
                symbol = "💵" if trans_type == "in" else "💸"

                if trans_type == "out":
                    total_amount += amount

                message += f"{i}. {symbol} {txn.get('account', 'N/A')} - {date.strftime('%d/%m/%Y')}\n"
                message += f"   {amount:,.0f} VND - {txn.get('content', 'No description')}\n\n"

            message += f"\n💰 Total Spent: {total_amount:,.0f} VND"

            await query.message.reply_text(message)

        except Exception as e:
            await query.message.reply_text(f"❌ Error: {str(e)}")

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command - search transactions by content"""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Please provide a search term.\nExample: /search shopee")
            return

        search_term = " ".join(context.args).lower()

        try:
            # Get all transactions (you might want to add pagination for large datasets)
            response = self.processor.supabase.table("transactions").select("*").order("transaction_date", desc=True).execute()

            if not response.data:
                await update.message.reply_text("No transactions found.")
                return

            # Filter by search term
            matches = []
            for txn in response.data:
                content = (txn.get("content", "") or "").lower()
                description = (txn.get("description", "") or "").lower()

                if search_term in content or search_term in description:
                    matches.append(txn)

            if not matches:
                await update.message.reply_text(f"No transactions found matching '{search_term}'")
                return

            # Limit to 20 results
            matches = matches[:20]

            message = f"🔍 Search Results for '{search_term}' ({len(matches)} found):\n\n"

            for i, txn in enumerate(matches, 1):
                date = datetime.fromisoformat(txn.get("transaction_date", ""))
                amount = float(txn.get("transfer_amount", 0))
                trans_type = txn.get("transfer_type", "in")
                symbol = "💵" if trans_type == "in" else "💸"

                message += f"{i}. {symbol} {txn.get('account', 'N/A')} - {date.strftime('%d/%m/%Y')}\n"
                message += f"   {amount:,.0f} VND - {txn.get('content', 'No description')}\n"
                message += f"   Category: {txn.get('category', 'Uncategorized')}\n\n"

            if len(matches) == 20:
                message += "\n(Showing first 20 results)"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text(f"❌ Error searching: {str(e)}")

    def setup_handlers(self):
        """Setup all command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("recent", self.recent_command))
        self.application.add_handler(CommandHandler("accounts", self.accounts_command))
        self.application.add_handler(CommandHandler("categories", self.categories_command))
        self.application.add_handler(CommandHandler("search", self.search_command))

        # Callback query handler for buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

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

        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def run_sync(self):
        """Run the bot synchronously (for use in threads)"""
        asyncio.run(self.run())
