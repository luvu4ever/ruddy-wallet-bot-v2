from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


async def list_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /list command - show categories with their expenses for current month
    """
    try:
        print(f"📥 Received /list command from user")

        # Check if update has message
        if not update.message:
            print("❌ No message in update")
            return

        # Get current month start and end dates
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1).isoformat()

        # Calculate next month for end date
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1).isoformat()
        else:
            month_end = datetime(now.year, now.month + 1, 1).isoformat()

        print(f"📅 Query range: {month_start} to {month_end}")

        # Get bot instance from context
        bot_instance = context.bot_data.get('bot_instance')
        if not bot_instance:
            print("❌ Bot instance not found in context")
            await update.message.reply_text("❌ Bot instance not found")
            return

        processor = bot_instance.processor
        print(f"✅ Processor retrieved")

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
                # Only track expenses (money going out)
                if category not in category_expenses:
                    category_expenses[category] = 0
                category_expenses[category] += amount
                total_expense += amount
            else:
                total_income += amount

        # Format response message
        message = f"📊 Expense Summary - {now.strftime('%B %Y')}\n\n"

        if not category_expenses:
            message += "No expenses recorded this month.\n\n"
        else:
            # Sort categories by expense amount (highest first)
            sorted_categories = sorted(
                category_expenses.items(),
                key=lambda x: x[1],
                reverse=True
            )

            message += "💸 Expenses by Category:\n"
            for category, amount in sorted_categories:
                percentage = (amount / total_expense * 100) if total_expense > 0 else 0
                message += f"• {category}: {amount:,.0f} VND ({percentage:.1f}%)\n"

        # Add summary
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
        if update.message:
            await update.message.reply_text(f"❌ Error fetching category expenses: {str(e)}")


def setup_categories_handlers(application, bot_instance):
    """
    Register all category-related command handlers

    Args:
        application: The telegram Application instance
        bot_instance: The bot instance to access processor
    """
    # Store bot instance in bot_data for access in handlers
    application.bot_data['bot_instance'] = bot_instance

    # Register /list command
    application.add_handler(CommandHandler("list", list_categories_command))
