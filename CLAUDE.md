# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ruddy Wallet Bot v2** is a personal budget tracking system that combines:
- **Telegram Bot** for querying expense data (`/list`, `/category`)
- **Flask REST API** for receiving webhooks and serving transaction data
- **Webhook Processors** for SePay (bank transaction webhook) and Email (bank notification emails)
- **AI-Powered Email Parser** using Google Gemini AI to extract transaction data from bank emails
- **Supabase** as the backend database

The system automatically categorizes transactions based on patterns in the `known_receivers` table and can replace transaction content for cleaner display.

## Architecture

### Dual Process Design

The application runs **two separate processes concurrently**:

1. **Telegram Bot** (`bot_main.py`)
   - Long-polling bot using python-telegram-bot
   - Handles user commands for querying transaction data
   - Queries Supabase directly for read-only operations

2. **Flask API** (`app.py`)
   - Receives webhooks from SePay and n8n (email notifications)
   - Serves transaction data via REST endpoints
   - Writes data to Supabase via TransactionProcessor

Both processes are started together via `start.sh`:
```bash
python bot_main.py &          # Background
gunicorn app:app ...          # Foreground
```

### Data Flow

**SePay Webhook → Flask → TransactionProcessor → Supabase**
- Bank transaction webhook arrives at `/webhook/sepay`
- Verified via API key in Authorization header
- Parsed and categorized automatically
- Saved to `transactions` table

**Email → n8n → Flask → EmailParser (Gemini AI) → TransactionProcessor → Supabase**
- Bank sends email notification
- n8n forwards to `/webhook/email`
- EmailParser uses Gemini AI to extract transaction data
- Converted to SePay-compatible format and saved

**Telegram User → Bot → Supabase → Bot → User**
- `/list`: Shows expenses grouped by account type with budget tracking
- `/category {name}`: Shows all transactions for a specific category

### Key Modules

**`transaction/transaction_processor.py`** - Core transaction handling
- `TransactionProcessor` class: Main processor for all transaction operations
- `parse_sepay_transaction()`: Converts SePay webhook to internal format
- `categorize_and_format_transaction()`: Auto-categorizes using `known_receivers` table patterns
- `save_transaction()`: Saves to Supabase with duplicate detection
- Gateway name mapping (e.g., "Vietcombank" → "VCB")
- Receiver pattern cache (5-minute TTL)

**`transaction/email_parser.py`** - AI-powered email parsing
- `EmailParser` class: Uses Gemini 2.0 Flash model
- `parse_bank_email()`: Extracts structured data from Vietnamese bank emails
- `fix_mojibake()`: Fixes encoding issues using ftfy library
- Returns SePay-compatible format for unified processing

**`routes/webhook_routes.py`** - Webhook endpoints
- `/webhook/sepay`: Receives SePay transaction webhooks (requires API key)
- `/webhook/email`: Receives emails forwarded by n8n
- Both routes use TransactionProcessor for saving

**`routes/transaction_routes.py`** - Query endpoints
- `/health`: Health check
- `/stats`: Overall transaction statistics
- `/transactions/recent?limit=N`: Recent transactions
- `/transactions/by-account/<account>`: Filter by account (VCB, MB, etc.)
- `/transactions/by-category/<category>`: Filter by category
- `/test`: Test SePay webhook processing
- `/test/email`: Test email parsing

**`handlers/list_handler.py`** - `/list` command
- Groups expenses by account type (Need, Fun, Invest)
- Shows categories within each type
- Displays budget vs. actual spending with percentage
- Uses `category_mapping` table to map categories to account types
- Uses `budget_plans` table for budget amounts

**`handlers/category_handler.py`** - `/category` command
- Shows all transactions for a specific category in current month
- Displays budget tracking if available
- Lists individual transactions with dates

## Database Schema (Supabase)

**`transactions`** - Main transaction log
- `account`: Simplified bank name (VCB, MB, BIDV, etc.)
- `transaction_date`: ISO 8601 timestamp
- `account_number`: Bank account number
- `code`: Transaction reference code
- `content`: Transaction description (can be replaced by known_receivers)
- `transfer_type`: "in" or "out"
- `transfer_amount`: Amount in VND
- `accumulated`: Balance after transaction (optional)
- `description`: Additional description
- `category`: Auto-assigned category from known_receivers

**`known_receivers`** - Pattern matching for auto-categorization
- `receiver_pattern`: Lowercase substring to match against transaction text
- `category`: Category to assign when matched
- `new_content`: Optional replacement content for cleaner display

**`category_mapping`** - Maps categories to account types
- `category`: Category name
- `account_type`: "Need", "Fun", "Invest", or custom

**`budget_plans`** - Budget tracking per category
- `category`: Category name
- `budget_amount`: Monthly budget limit

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with:
#   SUPABASE_URL, SUPABASE_SERVICE_KEY
#   TELEGRAM_BOT_TOKEN
#   SEPAY_API_KEY (optional, for webhook auth)
#   GEMINI_API_KEY (for email parsing)
#   PORT (default: 8080)
```

### Running

```bash
# Production (both bot and API together)
./start.sh

# Development - Bot only
python bot_main.py

# Development - API only
python app.py
# or with gunicorn:
gunicorn app:app --bind 0.0.0.0:8080 --workers 2 --timeout 120

# Test email parser standalone
python transaction/email_parser.py
```

### Testing

```bash
# Test SePay webhook
curl -X POST http://localhost:8080/test \
  -H "Content-Type: application/json" \
  -d '{"gateway": "Vietcombank", "transferAmount": 100000, "transferType": "out", "content": "test"}'

# Test email parsing
curl -X POST http://localhost:8080/test/email \
  -H "Content-Type: application/json" \
  -d '{"subject": "Thông báo giao dịch", "body": "..."}'

# Check health
curl http://localhost:8080/health

# View stats
curl http://localhost:8080/stats

# View recent transactions
curl http://localhost:8080/transactions/recent?limit=20
```

## Important Implementation Details

### Auto-Categorization Logic
The `categorize_and_format_transaction()` method:
1. Combines `content`, `description`, `receiver`, and `code` fields into one text
2. Converts to lowercase
3. Checks each pattern in `known_receivers` table
4. Returns first match with category and optional new_content
5. Uses cached patterns (5-minute TTL) to reduce database calls

### Duplicate Detection
Transactions are considered duplicates if all match:
- `transaction_date`
- `transfer_amount`
- `account_number`
- `content` (original content, before replacement)

### Gateway Name Mapping
Common Vietnamese banks are mapped to short codes in `get_account_name()`:
- Vietcombank → VCB
- MBBank/MB → MB
- BIDV → BIDV
- Techcombank → TCB
- VPBank → VPB
- ACB → ACB
- Sacombank → STB
- Agribank → AGB
- VietinBank → CTG

### Telegram Bot Error Handling
The bot has automatic restart logic in `bot_main.py`:
- Catches `Conflict` errors (another instance running)
- On general exceptions: prints traceback, waits 30 seconds, restarts
- Uses `run_polling()` for long-polling updates

### Vietnamese Text Encoding
The `EmailParser` uses `ftfy` to fix mojibake encoding issues in Vietnamese text before sending to Gemini AI.

## Environment Variables

Required:
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service role key (not anon key)
- `TELEGRAM_BOT_TOKEN`: BotFather token
- `GEMINI_API_KEY`: Google AI Studio API key

Optional:
- `SEPAY_API_KEY`: For webhook authentication (if not set, webhook is unprotected)
- `PORT`: Server port (default: 8080)

## Deployment

Configured for Railway.app via `railway.json`:
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "./start.sh",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

The `start.sh` script ensures both the Telegram bot and Flask API run concurrently.
