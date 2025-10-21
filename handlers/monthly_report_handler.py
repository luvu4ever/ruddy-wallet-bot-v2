import os
from datetime import datetime, timedelta
from transaction import TransactionProcessor
from telegram import Bot
import asyncio


# Initialize processor
processor = TransactionProcessor()


def get_month_range(year, month, up_to_now=False):
    """
    Get start and end dates for a specific month

    Args:
        year: Year
        month: Month
        up_to_now: If True, end date is now() for current month (partial month)

    Returns:
        tuple: (month_start, month_end) in ISO format
    """
    month_start = datetime(year, month, 1).isoformat()

    # If this is current month and up_to_now is True, use current time
    now = datetime.now()
    if up_to_now and year == now.year and month == now.month:
        month_end = now.isoformat()
    else:
        # Calculate next month for end date
        if month == 12:
            month_end = datetime(year + 1, 1, 1).isoformat()
        else:
            month_end = datetime(year, month + 1, 1).isoformat()

    return month_start, month_end


def generate_monthly_report(year=None, month=None, up_to_now=True):
    """
    Generate monthly spending report

    Args:
        year: Year (defaults to current month)
        month: Month (defaults to current month)
        up_to_now: If True, shows data up to current moment for current month (default: True)

    Returns:
        dict with report data and formatted message
    """
    # Default to current month
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month

    month_start, month_end = get_month_range(year, month, up_to_now)
    month_name = datetime(year, month, 1).strftime('%B %Y')

    # Check if this is current month for display
    now = datetime.now()
    is_current_month = (year == now.year and month == now.month)
    if is_current_month and up_to_now:
        month_name += " (up to now)"

    print(f"📊 Generating report for {month_name}")
    print(f"📅 Query range: {month_start} to {month_end}")

    # Query transactions for the month
    response = processor.supabase.table("transactions").select(
        "category, transfer_amount, transfer_type, account"
    ).gte(
        "transaction_date", month_start
    ).lt(
        "transaction_date", month_end
    ).execute()

    print(f"📊 Found {len(response.data) if response.data else 0} transactions")

    if not response.data or len(response.data) == 0:
        return {
            "success": True,
            "month": month_name,
            "has_data": False,
            "message": f"📊 Monthly Report - {month_name}\n\nNo transactions found."
        }

    # Get category mappings
    mapping_response = processor.supabase.table("category_mapping").select("category, account_type").execute()
    category_map = {row["category"]: row["account_type"] for row in mapping_response.data} if mapping_response.data else {}

    # Get budget plans
    budget_response = processor.supabase.table("budget_plans").select("category, budget_amount").execute()
    budget_map = {row["category"]: float(row["budget_amount"]) for row in budget_response.data if row["budget_amount"]} if budget_response.data else {}

    # Calculate expenses by account type and category
    account_expenses = {}
    account_categories = {}
    total_income = 0
    total_expense = 0

    for txn in response.data:
        category = txn.get("category", "Uncategorized")
        amount = float(txn.get("transfer_amount", 0))
        transfer_type = txn.get("transfer_type", "in")

        # Map category to account_type
        account_type = category_map.get(category, "Uncategorized")

        if transfer_type == "out":
            # Money going out - add to expenses
            if account_type not in account_expenses:
                account_expenses[account_type] = 0
                account_categories[account_type] = {}

            account_expenses[account_type] += amount

            if category not in account_categories[account_type]:
                account_categories[account_type][category] = 0
            account_categories[account_type][category] += amount

            total_expense += amount
        else:
            # Money coming in
            if category.lower() == "income":
                total_income += amount
            else:
                # Refund/return
                if account_type not in account_expenses:
                    account_expenses[account_type] = 0
                    account_categories[account_type] = {}

                account_expenses[account_type] -= amount

                if category not in account_categories[account_type]:
                    account_categories[account_type][category] = 0
                account_categories[account_type][category] -= amount

                total_expense -= amount

    # Format report message
    message = f"📊 Monthly Report - {month_name}\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if not account_expenses:
        message += "No expenses recorded this month.\n\n"
    else:
        # Sort by account type
        priority = {"Need": 1, "Fun": 2, "Invest": 3}
        sorted_accounts = sorted(
            account_expenses.items(),
            key=lambda x: (priority.get(x[0], 99), -x[1])
        )

        message += "💸 Expenses by Account Type:\n\n"
        for account_type, amount in sorted_accounts:
            emoji = {
                "Need": "🏠",
                "Fun": "🎉",
                "Invest": "📈"
            }.get(account_type, "📦")

            message += f"{emoji} {account_type}: {amount:,.0f} VND\n"

            if account_type in account_categories:
                sorted_categories = sorted(
                    account_categories[account_type].items(),
                    key=lambda x: -x[1]
                )

                for category, cat_amount in sorted_categories:
                    budget = budget_map.get(category, 0)

                    if budget > 0:
                        percentage = (cat_amount / budget * 100) if budget > 0 else 0
                        message += f"  └─ {category}: {percentage:.1f}%\n"
                        message += f"     Spent: {cat_amount:,.0f} / Budget: {budget:,.0f}\n"
                    else:
                        message += f"  └─ {category}: {cat_amount:,.0f} VND\n"

                message += "\n"

    message += "━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💰 Monthly Summary:\n"
    message += f"• Income: {total_income:,.0f} VND\n"
    message += f"• Expense: {total_expense:,.0f} VND\n"
    message += f"• Net: {total_income - total_expense:,.0f} VND\n"

    if total_income > 0:
        savings_rate = ((total_income - total_expense) / total_income * 100)
        message += f"• Savings Rate: {savings_rate:.1f}%\n"

    return {
        "success": True,
        "month": month_name,
        "has_data": True,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
        "account_expenses": account_expenses,
        "message": message
    }


async def summarymonth_command(update, context):
    """
    Handle /summarymonth command - show monthly report

    Usage:
        /summarymonth - Current month (up to now)
        /summarymonth 10/2025 - Specific month
        /summarymonth 10 - Specific month in current year
    """
    try:
        print(f"📥 Received /summarymonth command from user")

        year = None
        month = None

        # Parse optional month parameter
        if context.args and len(context.args) > 0:
            month_arg = context.args[0]

            try:
                # Try parsing MM/YYYY format
                if '/' in month_arg:
                    parts = month_arg.split('/')
                    month = int(parts[0])
                    year = int(parts[1])
                else:
                    # Just month number, use current year
                    month = int(month_arg)
                    year = datetime.now().year

                # Validate month
                if month < 1 or month > 12:
                    await update.message.reply_text("❌ Invalid month. Use 1-12.")
                    return

                print(f"📅 Requested report for {month}/{year}")

            except (ValueError, IndexError):
                await update.message.reply_text(
                    "❌ Invalid format. Use:\n"
                    "/summarymonth - current month\n"
                    "/summarymonth 10/2025 - specific month/year\n"
                    "/summarymonth 10 - month in current year"
                )
                return

        # Generate report
        report = generate_monthly_report(year, month)

        if report["success"]:
            await update.message.reply_text(report["message"])
            print(f"✅ Sent monthly report for {report['month']}")
        else:
            await update.message.reply_text("❌ Failed to generate report")

    except Exception as e:
        print(f"❌ Error in /summarymonth command: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def send_telegram_report(message):
    """Send report via Telegram to configured chat"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)
        print(f"✅ Report sent to Telegram successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")
        return False


async def send_monthly_report():
    """Generate and send monthly report (called by cron on 1st of month)"""
    try:
        print("🚀 Starting monthly report generation...")

        # Cron runs on 1st of month, so report on previous month (complete data)
        now = datetime.now()
        first_day_this_month = datetime(now.year, now.month, 1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)

        # Generate report for previous month (complete, not up_to_now)
        report = generate_monthly_report(
            year=last_day_prev_month.year,
            month=last_day_prev_month.month,
            up_to_now=False  # Full month data since it's already complete
        )

        if report["success"]:
            # Send to Telegram
            await send_telegram_report(report["message"])

            print(f"✅ Monthly report completed for {report['month']}")
            return report
        else:
            print("❌ Failed to generate report")
            return None

    except Exception as e:
        print(f"❌ Error generating monthly report: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test the report generation
    report = asyncio.run(send_monthly_report())
    if report:
        print("\n" + report["message"])
