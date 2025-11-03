from datetime import datetime
from transaction import TransactionProcessor
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters


# Initialize processor
processor = TransactionProcessor()


async def review_command(update, context):
    """Handle /review command - start interactive categorization of uncategorized transactions"""
    try:
        print(f"📥 Received /review command from user")

        # Fetch uncategorized transactions (null, empty, or "Uncategorized")
        response = processor.supabase.table("transactions").select(
            "*"
        ).or_(
            "category.is.null,category.eq.,category.eq.Uncategorized"
        ).order(
            "transaction_date", desc=True
        ).limit(50).execute()

        if not response.data or len(response.data) == 0:
            await update.message.reply_text(
                "✅ All transactions are categorized!\n\n"
                "No uncategorized transactions found."
            )
            return

        print(f"📊 Found {len(response.data)} uncategorized transactions")

        # Store review state in user context
        context.user_data['review_state'] = {
            'transactions': response.data,
            'current_index': 0,
            'total': len(response.data)
        }

        # Show first transaction
        await show_transaction(update, context)

    except Exception as e:
        print(f"❌ Error in /review command: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def show_transaction(update, context, edit_message=False):
    """Display current transaction with category selection buttons"""
    state = context.user_data.get('review_state')
    if not state:
        return

    current_index = state['current_index']
    transactions = state['transactions']
    total = state['total']

    if current_index >= total:
        # All done
        message = (
            "🎉 All Done!\n\n"
            f"You've reviewed all {total} uncategorized transactions.\n\n"
            "Great job keeping your budget organized!"
        )
        if edit_message and update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)

        # Clear state
        context.user_data.pop('review_state', None)
        return

    txn = transactions[current_index]

    # Format transaction details
    txn_datetime = datetime.fromisoformat(txn['transaction_date'].replace('Z', '+00:00'))
    txn_date = txn_datetime.strftime('%b %d, %Y')
    txn_time = txn_datetime.strftime('%H:%M')
    amount = f"{float(txn['transfer_amount']):,.0f} VND"
    transfer_type = "💸 Out" if txn['transfer_type'] == 'out' else "💰 In"
    content = txn.get('content', 'No description')
    account = txn.get('account', 'Unknown')

    message = (
        f"📊 Uncategorized Review ({current_index + 1}/{total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 {txn_date} {txn_time}\n"
        f"{transfer_type} {amount}\n"
        f"📝 {content}\n"
        f"🏦 {account}\n\n"
        f"Select category type:"
    )

    # Create category type buttons
    keyboard = [
        [
            InlineKeyboardButton("🏠 Need", callback_data="type_Need"),
            InlineKeyboardButton("🎉 Fun", callback_data="type_Fun"),
            InlineKeyboardButton("📈 Invest", callback_data="type_Invest"),
        ],
        [
            InlineKeyboardButton("⏭️ Skip", callback_data="action_skip"),
            InlineKeyboardButton("✅ Done", callback_data="action_done"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_message and update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )


async def button_callback(update, context):
    """Handle button clicks in review flow"""
    query = update.callback_query
    await query.answer()

    data = query.data
    state = context.user_data.get('review_state')

    if not state:
        await query.edit_message_text("❌ Review session expired. Use /review to start again.")
        return

    print(f"📲 Button clicked: {data}")

    # Handle account type selection
    if data.startswith("type_"):
        account_type = data.replace("type_", "")
        await show_categories(update, context, account_type)

    # Handle category selection
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        await categorize_transaction(update, context, category)

    # Handle content edit
    elif data.startswith("content_"):
        action = data.replace("content_", "")
        if action == "edit":
            # Ask user to send new content
            state['waiting_for_content'] = True
            await query.edit_message_text(
                "✏️ Please send the new content for this transaction:\n\n"
                "(Just type and send your message)"
            )
        elif action == "keep":
            # Skip editing, move to next transaction
            state['current_index'] += 1
            await show_transaction(update, context, edit_message=True)

    # Handle actions
    elif data.startswith("action_"):
        action = data.replace("action_", "")
        if action == "skip":
            # Move to next
            state['current_index'] += 1
            await show_transaction(update, context, edit_message=True)
        elif action == "done":
            # End review
            await query.edit_message_text(
                f"✅ Review session ended.\n\n"
                f"Reviewed: {state['current_index']}/{state['total']} transactions"
            )
            context.user_data.pop('review_state', None)

    # Handle back button
    elif data == "back":
        await show_transaction(update, context, edit_message=True)


async def show_categories(update, context, account_type):
    """Show specific categories for selected account type"""
    query = update.callback_query
    state = context.user_data['review_state']

    # Store selected account type
    state['selected_account_type'] = account_type

    # Fetch categories for this account type
    response = processor.supabase.table("category_mapping").select(
        "category"
    ).eq(
        "account_type", account_type
    ).execute()

    categories = [row['category'] for row in response.data] if response.data else []

    if not categories:
        # No categories found, just use the account type as category
        await categorize_transaction(update, context, account_type)
        return

    # Build category buttons
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(
            f"📌 {category}",
            callback_data=f"cat_{category}"
        )])

    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_index = state['current_index']
    total = state['total']
    txn = state['transactions'][current_index]

    txn_datetime = datetime.fromisoformat(txn['transaction_date'].replace('Z', '+00:00'))
    txn_date = txn_datetime.strftime('%b %d, %Y')
    txn_time = txn_datetime.strftime('%H:%M')

    message = (
        f"📊 Uncategorized Review ({current_index + 1}/{total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 {txn_date} {txn_time}\n"
        f"💰 {float(txn['transfer_amount']):,.0f} VND\n"
        f"📝 {txn.get('content', 'No description')}\n\n"
        f"Select category in {account_type}:"
    )

    await query.edit_message_text(message, reply_markup=reply_markup)


async def categorize_transaction(update, context, category):
    """Categorize the current transaction"""
    query = update.callback_query
    state = context.user_data['review_state']
    current_index = state['current_index']
    txn = state['transactions'][current_index]

    # Update transaction category
    processor.supabase.table("transactions").update({
        "category": category
    }).eq("id", txn['id']).execute()

    print(f"✅ Categorized transaction {txn['id']} as {category}")

    # Store categorization info
    state['last_category'] = category
    state['last_content'] = txn.get('content', '')

    # Ask if user wants to edit content
    await ask_edit_content(update, context)


async def ask_edit_content(update, context):
    """Ask if user wants to edit transaction content"""
    query = update.callback_query
    state = context.user_data['review_state']

    current_content = state.get('last_content', '')
    category = state.get('last_category', '')

    message = (
        f"✅ Categorized as {category}!\n\n"
        f"Current content:\n"
        f"📝 {current_content}\n\n"
        f"Do you want to edit the content?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit Content", callback_data="content_edit"),
            InlineKeyboardButton("⏭️ Keep & Continue", callback_data="content_keep"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup)


async def handle_content_input(update, context):
    """Handle text message when user is editing content"""
    state = context.user_data.get('review_state')

    # Check if we're waiting for content input
    if not state or not state.get('waiting_for_content'):
        return  # Not in review mode or not waiting for input

    # Get the new content
    new_content = update.message.text.strip()

    if not new_content:
        await update.message.reply_text("❌ Content cannot be empty. Please send the new content:")
        return

    # Update transaction content
    current_index = state['current_index']
    txn = state['transactions'][current_index]

    processor.supabase.table("transactions").update({
        "content": new_content
    }).eq("id", txn['id']).execute()

    print(f"✏️ Updated content for transaction {txn['id']}: {new_content}")

    # Update state
    state['last_content'] = new_content
    state['waiting_for_content'] = False

    # Show confirmation and move to next transaction
    await update.message.reply_text(
        f"✅ Content updated to:\n📝 {new_content}"
    )

    # Move to next transaction
    state['current_index'] += 1
    await show_transaction(update, context)
