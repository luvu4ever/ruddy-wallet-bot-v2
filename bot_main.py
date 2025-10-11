import os
from telegram.ext import Application, CommandHandler
from telegram.error import Conflict
from datetime import datetime
from transaction import TransactionProcessor
import sys
import time


# Initialize processor
processor = TransactionProcessor()


async def list_command(update, context):
    """Handle /list command - show categories with expenses for current month"""
    try:
        print(f"📥 Received /list command from user")

        # Get current month start and end dates
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1).isoformat()

        # Calculate next month for end date
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1).isoformat()
        else:
            month_end = datetime(now.year, now.month + 1, 1).isoformat()

        print(f"📅 Query range: {month_start} to {month_end}")

        # Query transactions for current month
        response = processor.supabase.table("transactions").select(
            "category, transfer_amount, transfer_type"
        ).gte(
            "transaction_date", month_start
        ).lt(
            "transaction_date", month_end
        ).execute()

        print(f"📊 Found {len(response.data) if response.data else 0} transactions")

        if not response.data or len(response.data) == 0:
            await update.message.reply_text(
                f"📊 No transactions found for {now.strftime('%B %Y')}"
            )
            return

        # Calculate expenses by category
        category_expenses = {}
        total_income = 0
        total_expense = 0

        for txn in response.data:
            category = txn.get("category", "Uncategorized")
            amount = float(txn.get("transfer_amount", 0))
            transfer_type = txn.get("transfer_type", "in")

            if transfer_type == "out":
                if category not in category_expenses:
                    category_expenses[category] = 0
                category_expenses[category] += amount
                total_expense += amount
            else:
                total_income += amount

        # Format response
        message = f"📊 Expense Summary - {now.strftime('%B %Y')}\n\n"

        if not category_expenses:
            message += "No expenses recorded this month.\n\n"
        else:
            sorted_categories = sorted(
                category_expenses.items(),
                key=lambda x: x[1],
                reverse=True
            )

            message += "💸 Expenses by Category:\n"
            for category, amount in sorted_categories:
                percentage = (amount / total_expense * 100) if total_expense > 0 else 0
                message += f"• {category}: {amount:,.0f} VND ({percentage:.1f}%)\n"

        message += f"\n💰 Monthly Summary:\n"
        message += f"• Total Income: {total_income:,.0f} VND\n"
        message += f"• Total Expense: {total_expense:,.0f} VND\n"
        message += f"• Net: {total_income - total_expense:,.0f} VND\n"

        print(f"✅ Sending response to user")
        await update.message.reply_text(message)
        print(f"✅ Response sent successfully")

    except Exception as e:
        print(f"❌ Error in /list command: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error: {str(e)}")


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

        # Start bot
        print("🤖 Starting Budget Tracker Bot...")
        print("📊 Commands: /list")
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
