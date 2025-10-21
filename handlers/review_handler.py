from datetime import datetime
from transaction import TransactionProcessor
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Initialize processor
processor = TransactionProcessor()


async def review_command(update, context):
    """Handle /review command - start interactive categorization of uncategorized transactions"""
    try:
        print(f"📥 Received /review command from user")

        # Fetch uncategorized transactions
        response = processor.supabase.table("transactions").select(
            "*"
        ).is_(
            "category", "null"
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
    txn_date = datetime.fromisoformat(txn['transaction_date'].replace('Z', '+00:00')).strftime('%b %d, %Y')
    amount = f"{float(txn['transfer_amount']):,.0f} VND"
    transfer_type = "💸 Out" if txn['transfer_type'] == 'out' else "💰 In"
    content = txn.get('content', 'No description')
    account = txn.get('account', 'Unknown')

    message = (
        f"📊 Uncategorized Review ({current_index + 1}/{total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 {txn_date}\n"
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

    # Handle pattern save
    elif data.startswith("pattern_"):
        action = data.replace("pattern_", "")
        await handle_pattern_save(update, context, action == "yes")

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

    message = (
        f"📊 Uncategorized Review ({current_index + 1}/{total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
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

    # Store categorization info for pattern save prompt
    state['last_category'] = category
    state['last_content'] = txn.get('content', '')

    # Ask about pattern saving
    await ask_pattern_save(update, context)


async def ask_pattern_save(update, context):
    """Ask if user wants to save categorization pattern"""
    query = update.callback_query
    state = context.user_data['review_state']

    content = state.get('last_content', '')
    category = state.get('last_category', '')

    # Extract potential pattern (first word or first few chars)
    pattern_suggestion = content.split()[0] if content else ''
    if len(pattern_suggestion) < 3:
        # If too short, skip pattern save and move to next
        state['current_index'] += 1
        await show_transaction(update, context, edit_message=True)
        return

    message = (
        f"✅ Categorized as {category}!\n\n"
        f"💡 Save pattern for future?\n"
        f'"{pattern_suggestion}" → {category}\n\n'
        f"This will auto-categorize similar transactions."
    )

    keyboard = [
        [
            InlineKeyboardButton("💾 Yes, Save Pattern", callback_data="pattern_yes"),
            InlineKeyboardButton("❌ No, Just Once", callback_data="pattern_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup)


async def handle_pattern_save(update, context, save_pattern):
    """Handle pattern save decision"""
    query = update.callback_query
    state = context.user_data['review_state']

    if save_pattern:
        content = state.get('last_content', '')
        category = state.get('last_category', '')

        # Extract pattern (first word)
        pattern = content.split()[0].lower() if content else ''

        if pattern:
            # Check if pattern already exists
            existing = processor.supabase.table("known_receivers").select("*").eq(
                "receiver_pattern", pattern
            ).execute()

            if not existing.data or len(existing.data) == 0:
                # Save new pattern
                processor.supabase.table("known_receivers").insert({
                    "receiver_pattern": pattern,
                    "category": category,
                    "new_content": None
                }).execute()

                print(f"💾 Saved pattern: {pattern} → {category}")
            else:
                print(f"ℹ️ Pattern {pattern} already exists")

    # Move to next transaction
    state['current_index'] += 1
    await show_transaction(update, context, edit_message=True)
