from datetime import datetime
from transaction import TransactionProcessor


# Initialize processor
processor = TransactionProcessor()


async def category_command(update, context):
    """Handle /category command - show all expenses for a specific category"""
    try:
        print(f"📥 Received /category command from user")

        # Check if category name is provided
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ Please provide a category name.\n"
                "Usage: /category {category_name}\n"
                "Example: /category Groceries"
            )
            return

        # Get category name from arguments (join in case of spaces)
        category_name = " ".join(context.args)
        print(f"🔍 Searching for category: {category_name}")

        # Get current month start and end dates
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1).isoformat()

        # Calculate next month for end date
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1).isoformat()
        else:
            month_end = datetime(now.year, now.month + 1, 1).isoformat()

        print(f"📅 Query range: {month_start} to {month_end}")

        # Query transactions for this category in current month
        response = processor.supabase.table("transactions").select(
            "transaction_date, transfer_amount, transfer_type, content"
        ).eq(
            "category", category_name
        ).gte(
            "transaction_date", month_start
        ).lt(
            "transaction_date", month_end
        ).order(
            "transaction_date", desc=True
        ).execute()

        print(f"📊 Found {len(response.data) if response.data else 0} transactions")

        if not response.data or len(response.data) == 0:
            await update.message.reply_text(
                f"📊 No transactions found for category '{category_name}' in {now.strftime('%B %Y')}"
            )
            return

        # Get budget for this category
        budget_response = processor.supabase.table("budget_plans").select(
            "budget_amount"
        ).eq(
            "category", category_name
        ).execute()

        budget = 0
        if budget_response.data and len(budget_response.data) > 0:
            budget = float(budget_response.data[0].get("budget_amount", 0))

        # Calculate total spent
        total_spent = 0
        expenses = []

        for txn in response.data:
            if txn.get("transfer_type") == "out":
                amount = float(txn.get("transfer_amount", 0))
                total_spent += amount
                expenses.append({
                    "date": txn.get("transaction_date"),
                    "amount": amount,
                    "content": txn.get("content", "")
                })

        # Format response
        message = f"📋 Category: {category_name}\n"
        message += f"📅 Period: {now.strftime('%B %Y')}\n\n"

        if budget > 0:
            remaining = budget - total_spent
            percentage = (total_spent / budget * 100) if budget > 0 else 0
            message += f"💰 Budget: {budget:,.0f} VND\n"
            message += f"💸 Spent: {total_spent:,.0f} VND ({percentage:.1f}%)\n"
            message += f"💵 Remaining: {remaining:,.0f} VND\n\n"
        else:
            message += f"💸 Total Spent: {total_spent:,.0f} VND\n"
            message += f"💡 No budget set for this category\n\n"

        if expenses:
            message += f"📝 Transactions ({len(expenses)}):\n"
            for expense in expenses:
                date_obj = datetime.fromisoformat(expense["date"].replace("Z", "+00:00"))
                date_str = date_obj.strftime("%d/%m")

                # Show content if it's shorter than 5 words
                content = expense.get("content", "")
                if content and len(content.split()) < 5:
                    message += f"  • {date_str}: {expense['amount']:,.0f} VND - {content}\n"
                else:
                    message += f"  • {date_str}: {expense['amount']:,.0f} VND\n"

        print(f"✅ Sending response to user")
        await update.message.reply_text(message)
        print(f"✅ Response sent successfully")

    except Exception as e:
        print(f"❌ Error in /category command: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error: {str(e)}")
