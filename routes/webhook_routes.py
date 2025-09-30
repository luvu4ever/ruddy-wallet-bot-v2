from flask import Blueprint, request, jsonify
from transaction import TransactionProcessor, EmailParser
import os
from functools import wraps

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

# Initialize processors
processor = TransactionProcessor()
email_parser = EmailParser()

# Get SePay API Key from environment
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")

def verify_sepay_api_key(f):
    """Decorator to verify SePay API Key from Authorization header"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        if not auth_header.startswith('Apikey '):
            return jsonify({"error": "Invalid Authorization format"}), 401
        
        api_key = auth_header.replace('Apikey ', '').strip()
        
        if api_key != SEPAY_API_KEY:
            return jsonify({"error": "Invalid API Key"}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

@webhook_bp.route('/sepay', methods=['POST'])
@verify_sepay_api_key
def receive_sepay():
    """
    SePay webhook endpoint
    Receives transaction data from SePay
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        print(f"\n--- SePay Transaction ---")
        print(f"ID: {data.get('id')}")
        print(f"Gateway: {data.get('gateway')}")
        print(f"Amount: {data.get('transferAmount'):,} VND")
        print(f"Type: {data.get('transferType')}")
        print(f"Content: {data.get('content')}")
        
        result = processor.process_sepay_webhook(data)
        
        if result.get("success"):
            if result.get("duplicate"):
                print(f"⚠ Duplicate skipped")
            else:
                print(f"✓ Saved successfully")
            
            return jsonify({
                "success": True,
                "message": result.get("message"),
                "category": result.get("category")
            }), 200
        else:
            print(f"✗ Failed: {result.get('error')}")
            return jsonify({
                "success": False,
                "error": result.get("error")
            }), 500
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/email', methods=['POST'])
def receive_email():
    """
    Email webhook endpoint
    Receives email from n8n and parses with Gemini AI
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        subject = data.get("subject", "")
        body = data.get("body", "")
        sender = data.get("from", "")
        
        if not body:
            return jsonify({"error": "Email body required"}), 400
        
        print(f"\n--- Email Received ---")
        print(f"From: {sender}")
        print(f"Subject: {subject}")
        print(f"Body: {len(body)} chars")
        
        # Parse with Gemini AI
        parsed = email_parser.parse_bank_email(body, subject)
        
        if not parsed:
            return jsonify({
                "success": False,
                "error": "Could not parse email"
            }), 400
        
        # Save to database
        result = processor.process_sepay_webhook(parsed)
        
        if result.get("success"):
            print(f"✓ Email processed successfully")
            return jsonify({
                "success": True,
                "message": result.get("message"),
                "category": result.get("category"),
                "parsed_data": parsed
            }), 200
        else:
            print(f"✗ Failed to save: {result.get('error')}")
            return jsonify({
                "success": False,
                "error": result.get("error")
            }), 500
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({"error": str(e)}), 500