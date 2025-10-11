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
    """Handle /list command - show expenses grouped by account type for current month"""
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

        # Get category mappings
        mapping_response = processor.supabase.table("category_mapping").select("category, account_type").execute()
        category_map = {row["category"]: row["account_type"] for row in mapping_response.data} if mapping_response.data else {}

        print(f"📋 Loaded {len(category_map)} category mappings")

        # Get budget plans (assuming user_id is stored somewhere, using a default for now)
        # TODO: Get actual user_id from context or environment
        budget_response = processor.supabase.table("budget_plans").select("category, budget_amount").execute()
        budget_map = {row["category"]: float(row["budget_amount"]) for row in budget_response.data if row["budget_amount"]} if budget_response.data else {}

        print(f"💵 Loaded {len(budget_map)} budget plans")

        # Calculate expenses by account type and category
        account_expenses = {}
        account_categories = {}  # Track categories within each account type
        total_income = 0
        total_expense = 0

        for txn in response.data:
            category = txn.get("category", "Uncategorized")
            amount = float(txn.get("transfer_amount", 0))
            transfer_type = txn.get("transfer_type", "in")

            if transfer_type == "out":
                # Map category to account_type
                account_type = category_map.get(category, "Uncategorized")

                # Track account type totals
                if account_type not in account_expenses:
                    account_expenses[account_type] = 0
                    account_categories[account_type] = {}

                account_expenses[account_type] += amount

                # Track category totals within account type
                if category not in account_categories[account_type]:
                    account_categories[account_type][category] = 0
                account_categories[account_type][category] += amount

                total_expense += amount
            else:
                total_income += amount

        # Format response
        message = f"📊 Expense Summary - {now.strftime('%B %Y')}\n\n"

        if not account_expenses:
            message += "No expenses recorded this month.\n\n"
        else:
            # Sort by account type (Need, Fun, Invest, then others)
            priority = {"Need": 1, "Fun": 2, "Invest": 3}
            sorted_accounts = sorted(
                account_expenses.items(),
                key=lambda x: (priority.get(x[0], 99), -x[1])
            )

            message += "💸 Expenses by Account Type:\n"
            for account_type, amount in sorted_accounts:
                # Add emoji for each type
                emoji = {
                    "Need": "🏠",
                    "Fun": "🎉",
                    "Invest": "📈"
                }.get(account_type, "📦")

                message += f"\n{emoji} {account_type}: {amount:,.0f} VND\n"

                # Show categories under this account type
                if account_type in account_categories:
                    # Sort categories by amount (descending)
                    sorted_categories = sorted(
                        account_categories[account_type].items(),
                        key=lambda x: -x[1]
                    )

                    for category, cat_amount in sorted_categories:
                        # Get budget for this category
                        budget = budget_map.get(category, 0)
                        remaining = budget - cat_amount

                        if budget > 0:
                            percentage = (cat_amount / budget * 100) if budget > 0 else 0
                            message += f"  └─ {category}: {percentage:.1f}%\n"
                            message += f"     Spent: {cat_amount:,.0f} VND\n"
                            message += f"     Left: {remaining:,.0f} VND\n"
                        else:
                            message += f"  └─ {category}: {cat_amount:,.0f} VND\n"

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
