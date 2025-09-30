from flask import Flask, request, jsonify
from transaction_processor import TransactionProcessor
import os
from functools import wraps

app = Flask(__name__)
processor = TransactionProcessor()

# Get SePay API Key from environment
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")

def verify_sepay_api_key(f):
    """
    Decorator to verify SePay API Key from Authorization header
    Expected format: "Authorization: Apikey YOUR_API_KEY"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        # SePay sends: "Apikey YOUR_API_KEY"
        if not auth_header.startswith('Apikey '):
            return jsonify({"error": "Invalid Authorization format"}), 401
        
        api_key = auth_header.replace('Apikey ', '').strip()
        
        if api_key != SEPAY_API_KEY:
            return jsonify({"error": "Invalid API Key"}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/webhook/sepay', methods=['POST'])
@verify_sepay_api_key
def receive_sepay_transaction():
    """
    Endpoint to receive transaction data from SePay webhook
    
    Expected Authorization header: "Apikey YOUR_API_KEY"
    Expected body: JSON with SePay transaction data
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Log received transaction
        print(f"\n--- Received SePay Transaction ---")
        print(f"ID: {data.get('id')}")
        print(f"Gateway: {data.get('gateway')}")
        print(f"Amount: {data.get('transferAmount'):,} VND")
        print(f"Type: {data.get('transferType')}")
        print(f"Content: {data.get('content')}")
        
        # Process the transaction
        result = processor.process_sepay_webhook(data)
        
        if result.get("success"):
            status_code = 200
            if result.get("duplicate"):
                print(f"⚠ Duplicate transaction skipped")
            else:
                print(f"✓ Transaction processed successfully")
        else:
            status_code = 500
            print(f"✗ Transaction processing failed: {result.get('error')}")
        
        return jsonify(result), status_code
        
    except Exception as e:
        print(f"✗ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Budget Tracker API",
        "version": "1.0"
    }), 200

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get transaction statistics grouped by account and category"""
    try:
        # Get total transactions
        total_response = processor.supabase.table("transactions").select("id", count="exact").execute()
        total_count = total_response.count if hasattr(total_response, 'count') else 0
        
        # Get transactions by account
        accounts_response = processor.supabase.table("transactions").select("account, transfer_amount").execute()
        
        # Calculate stats
        account_stats = {}
        category_stats = {}
        uncategorized_count = 0
        
        if accounts_response.data:
            for transaction in accounts_response.data:
                account = transaction.get("account", "Unknown")
                
                if account not in account_stats:
                    account_stats[account] = 0
                account_stats[account] += 1
        
        # Get category distribution
        categories_response = processor.supabase.table("transactions").select("category").execute()
        
        if categories_response.data:
            for transaction in categories_response.data:
                category = transaction.get("category", "Uncategorized")
                
                if category not in category_stats:
                    category_stats[category] = 0
                category_stats[category] += 1
                
                if category == "Uncategorized":
                    uncategorized_count += 1
        
        return jsonify({
            "total_transactions": total_count,
            "by_account": account_stats,
            "by_category": category_stats,
            "uncategorized": uncategorized_count,
            "categorized": total_count - uncategorized_count
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/recent', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions (last 10)"""
    try:
        limit = int(request.args.get('limit', 10))
        
        response = processor.supabase.table("transactions").select("*").order("transaction_date", desc=True).limit(limit).execute()
        
        return jsonify({
            "transactions": response.data,
            "count": len(response.data)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/by-account/<account>', methods=['GET'])
def get_transactions_by_account(account):
    """Get transactions for specific account"""
    try:
        response = processor.supabase.table("transactions").select("*").eq("account", account).order("transaction_date", desc=True).execute()
        
        return jsonify({
            "account": account,
            "transactions": response.data,
            "count": len(response.data)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['POST'])
def test_transaction():
    """
    Test endpoint to manually send a transaction (no auth required)
    Useful for testing during development
    """
    try:
        data = request.get_json()
        
        # Add sample data if not provided
        if not data:
            data = {
                "id": 99999,
                "gateway": "Vietcombank",
                "transactionDate": "2025-09-30 10:00:00",
                "accountNumber": "0123456789",
                "code": None,
                "content": "test transaction",
                "transferType": "in",
                "transferAmount": 100000,
                "accumulated": 1000000,
                "subAccount": None,
                "referenceCode": "TEST123",
                "description": "Test transaction"
            }
        
        result = processor.process_sepay_webhook(data)
        return jsonify(result), 200 if result.get("success") else 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"\n🚀 Starting Budget Tracker API on port {port}")
    print(f"📊 Webhook endpoint: /webhook/sepay")
    print(f"🔍 Health check: /health")
    print(f"📈 Stats: /stats")
    print(f"📋 Recent: /transactions/recent")
    print(f"🧪 Test: /test\n")
    app.run(host='0.0.0.0', port=port, debug=False)