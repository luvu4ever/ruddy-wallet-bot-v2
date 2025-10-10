# Telegram Bot Setup Guide

## Overview
This Telegram bot allows you to query and analyze your budget tracking transactions directly from Telegram. It integrates with your existing Flask API and Supabase database.

## Features

### Available Commands
- `/start` - Welcome message and introduction
- `/help` - Show all available commands
- `/stats` - View transaction statistics overview
- `/recent [limit]` - Show recent transactions (default: 10, max: 50)
- `/accounts` - Interactive account selection and viewing
- `/categories` - Interactive category selection and viewing
- `/search <term>` - Search transactions by content

### Features
- 📊 **Statistics Dashboard**: Total transactions, income/expense summary, categorization stats
- 🏦 **Account Filtering**: View transactions grouped by bank accounts
- 🏷️ **Category Filtering**: View transactions grouped by categories
- 🔍 **Search**: Find transactions by keywords
- 💰 **Financial Summary**: Automatic income/expense calculations
- 🔘 **Interactive Buttons**: Easy navigation with inline keyboards

## Setup Instructions

### 1. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the prompts to:
   - Choose a name for your bot (e.g., "Budget Tracker Bot")
   - Choose a username (must end in 'bot', e.g., "mybudget_tracker_bot")
4. BotFather will provide you with a **bot token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token securely

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Existing variables
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_key

# Add this for Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# Optional
PORT=8080
```

### 3. Deploy to Railway

Since you're using Railway, the bot will automatically start with your Flask app.

#### Railway Environment Variables:
1. Go to your Railway project
2. Navigate to Variables tab
3. Add `TELEGRAM_BOT_TOKEN` with your bot token
4. Redeploy your service

#### Railway Configuration:
The bot runs in a separate thread alongside Flask, so no additional configuration is needed. Both services will start automatically.

### 4. Local Development

To run locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your actual values

# Run the application
python app.py
```

The bot will start automatically if `TELEGRAM_BOT_TOKEN` is set.

## Usage Examples

### 1. View Statistics
```
User: /stats

Bot: 📊 Transaction Statistics

📈 Overview:
• Total Transactions: 150
• Categorized: 120
• Uncategorized: 30

💰 Financial Summary:
• Total Income: 50,000,000 VND
• Total Expense: 35,000,000 VND
• Net: 15,000,000 VND

🏦 By Account:
• VCB: 80 transactions
• MB: 70 transactions
...
```

### 2. Recent Transactions
```
User: /recent 5

Bot: 📋 Recent 5 Transactions:

1. 💸 VCB
   10/10/2025 14:30
   250,000 VND - Thanh toan Shopee
   Category: Shopping

2. 💵 MB
   10/10/2025 10:15
   5,000,000 VND - Luong thang 10
   Category: Salary
...
```

### 3. Search Transactions
```
User: /search shopee

Bot: 🔍 Search Results for 'shopee' (3 found):

1. 💸 VCB - 10/10/2025
   250,000 VND - Thanh toan Shopee
   Category: Shopping
...
```

### 4. Browse by Account
```
User: /accounts

Bot: 🏦 Select an account:
[VCB (80)] [MB (70)] [BIDV (20)]

User: <clicks VCB>

Bot: 🏦 Transactions for VCB (Last 20):

1. 💸 10/10/2025 14:30
   250,000 VND - Thanh toan Shopee
   Category: Shopping
...

📊 Summary:
• Income: 20,000,000 VND
• Expense: 15,000,000 VND
• Net: 5,000,000 VND
```

## Architecture

### How It Works
1. **Dual Service**: Flask API and Telegram Bot run concurrently
2. **Shared Database**: Both services use the same Supabase database
3. **Transaction Processor**: Bot uses the same `TransactionProcessor` as webhooks
4. **Threading**: Bot runs in a daemon thread, won't block Flask

### File Structure
```
ruddy-wallet-bot-v2/
├── app.py                          # Main application (Flask + Bot)
├── bot/
│   ├── __init__.py
│   └── telegram_bot.py            # Telegram bot implementation
├── routes/
│   ├── webhook_routes.py
│   └── transaction_routes.py
├── transaction/
│   ├── transaction_processor.py   # Shared transaction logic
│   └── email_parser.py
├── requirements.txt
└── .env
```

## Troubleshooting

### Bot Not Starting
1. Check if `TELEGRAM_BOT_TOKEN` is set in environment variables
2. Verify the token is correct (test with BotFather)
3. Check Railway logs for error messages

### Bot Not Responding
1. Ensure the app is running (check Railway deployment)
2. Try `/start` command to wake the bot
3. Check if bot token is valid

### Commands Not Working
1. Make sure Supabase credentials are correct
2. Verify database has transactions table
3. Check Railway logs for Python errors

### Railway Deployment Issues
1. Ensure all environment variables are set
2. Check that `python-telegram-bot>=20.0` is in requirements.txt
3. Verify Railway build logs for dependency issues

## Security Notes

1. **Never commit** your `.env` file or bot token to Git
2. **Use Railway secrets** for production environment variables
3. **Consider adding** user authentication if bot will be public
4. **Limit access** to authorized users only (can add user ID check)

## Future Enhancements

Potential features to add:
- 📅 Date range filtering
- 📊 Export to CSV/Excel
- 📈 Visual charts and graphs
- 🔔 Transaction notifications
- 👥 Multi-user support with authentication
- 🌐 Internationalization (Vietnamese/English)
- 📝 Add/edit transactions via bot
- 🤖 AI-powered insights with Google Gemini

## Support

For issues or questions:
1. Check Railway logs for errors
2. Review Supabase database connection
3. Test bot token with BotFather
4. Verify all environment variables are set correctly
