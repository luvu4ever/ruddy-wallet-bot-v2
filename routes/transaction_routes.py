from flask import Blueprint, request, jsonify
from transaction import TransactionProcessor, EmailParser

transaction_bp = Blueprint('transaction', __name__)

# Initialize processors
processor = TransactionProcessor()
email_parser = EmailParser()

@transaction_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Budget Tracker API",
        "version": "1.0"
    }), 200

@transaction_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get transaction statistics"""
    try:
        total_response = processor.supabase.table("transactions").select("id", count="exact").execute()
        total_count = total_response.count if hasattr(total_response, 'count') else 0
        
        accounts_response = processor.supabase.table("transactions").select("account").execute()
        categories_response = processor.supabase.table("transactions").select("category").execute()
        
        account_stats = {}
        category_stats = {}
        uncategorized = 0
        
        if accounts_response.data:
            for t in accounts_response.data:
                acc = t.get("account", "Unknown")
                account_stats[acc] = account_stats.get(acc, 0) + 1
        
        if categories_response.data:
            for t in categories_response.data:
                cat = t.get("category", "Uncategorized")
                category_stats[cat] = category_stats.get(cat, 0) + 1
                if cat == "Uncategorized":
                    uncategorized += 1
        
        return jsonify({
            "total_transactions": total_count,
            "by_account": account_stats,
            "by_category": category_stats,
            "uncategorized": uncategorized,
            "categorized": total_count - uncategorized
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/transactions/recent', methods=['GET'])
def get_recent():
    """Get recent transactions"""
    try:
        limit = int(request.args.get('limit', 10))
        response = processor.supabase.table("transactions").select("*").order("transaction_date", desc=True).limit(limit).execute()
        
        return jsonify({
            "transactions": response.data,
            "count": len(response.data)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/transactions/by-account/<account>', methods=['GET'])
def get_by_account(account):
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

@transaction_bp.route('/transactions/by-category/<category>', methods=['GET'])
def get_by_category(category):
    """Get transactions for specific category"""
    try:
        response = processor.supabase.table("transactions").select("*").eq("category", category).order("transaction_date", desc=True).execute()
        
        return jsonify({
            "category": category,
            "transactions": response.data,
            "count": len(response.data)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/test', methods=['POST'])
def test_sepay():
    """Test SePay webhook processing"""
    try:
        data = request.get_json() or {
            "id": 99999,
            "gateway": "Vietcombank",
            "transactionDate": "2025-10-01 10:00:00",
            "accountNumber": "0123456789",
            "content": "test transaction",
            "transferType": "in",
            "transferAmount": 100000,
            "accumulated": 1000000
        }
        
        result = processor.process_sepay_webhook(data)
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/test/email', methods=['POST'])
def test_email():
    """Test email parsing"""
    try:
        data = request.get_json() or {
            "subject": "Thông báo giao dịch",
            "body": """
            MB Bank xin thông báo:
            Số TK: 688619102003
            Thời gian: 01/10/2025 15:30:00
            Số tiền: -250,000 VND
            Nội dung: Thanh toan Shopee
            Số dư: 4,750,000 VND
            """
        }
        
        parsed = email_parser.parse_bank_email(data.get("body", ""), data.get("subject", ""))
        
        if not parsed:
            return jsonify({"error": "Could not parse email"}), 400
        
        result = processor.process_sepay_webhook(parsed)
        
        return jsonify({
            "parsed": parsed,
            "saved": result
        }), 200 if result.get("success") else 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500