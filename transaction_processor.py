import os
from datetime import datetime
from supabase import create_client, Client
from typing import Dict, Optional

class TransactionProcessor:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def get_account_name(self, gateway: str) -> str:
        """
        Convert gateway name to simplified account name
        You can customize this mapping based on your banks
        """
        gateway_mapping = {
            "Vietcombank": "VCB",
            "BIDV": "BIDV",
            "MB": "MB",
            "MBBank": "MB",
            "Techcombank": "TCB",
            "VPBank": "VPB",
            "ACB": "ACB",
            "Sacombank": "STB",
            "Agribank": "AGB",
            "VietinBank": "CTG"
        }
        
        # Return mapped value or original gateway name
        return gateway_mapping.get(gateway, gateway)
    
    def parse_sepay_transaction(self, sepay_data: Dict) -> Dict:
        """
        Parse transaction data from SePay webhook
        """
        # Convert transaction date to ISO format
        transaction_date = sepay_data.get("transactionDate")
        if transaction_date:
            # SePay format: "2023-03-25 14:02:37"
            try:
                dt = datetime.strptime(transaction_date, "%Y-%m-%d %H:%M:%S")
                transaction_date = dt.isoformat()
            except ValueError:
                transaction_date = datetime.now().isoformat()
        else:
            transaction_date = datetime.now().isoformat()
        
        # Get gateway and convert to account name
        gateway = sepay_data.get("gateway", "Unknown")
        account = self.get_account_name(gateway)
        
        transaction = {
            "account": account,
            "transaction_date": transaction_date,
            "account_number": sepay_data.get("accountNumber", ""),
            "code": sepay_data.get("code"),
            "content": sepay_data.get("content", ""),
            "transfer_type": sepay_data.get("transferType", "in"),
            "transfer_amount": float(sepay_data.get("transferAmount", 0)),
            "accumulated": float(sepay_data.get("accumulated", 0)) if sepay_data.get("accumulated") else None,
            "description": sepay_data.get("description", "")
        }
        return transaction
    
    def categorize_by_content(self, content: str) -> str:
        """
        Check if transaction content matches any known receiver pattern
        Returns category or 'Uncategorized'
        """
        if not content:
            return "Uncategorized"
        
        content_lower = content.lower()
        
        try:
            # Get all known receiver patterns
            response = self.supabase.table("known_receivers").select("*").execute()
            
            if response.data:
                for receiver in response.data:
                    pattern = receiver["receiver_pattern"].lower()
                    # Simple substring match
                    if pattern in content_lower:
                        return receiver["category"]
            
            return "Uncategorized"
        except Exception as e:
            print(f"Error checking known receiver: {e}")
            return "Uncategorized"
    
    def transaction_exists(self, transaction_data: Dict) -> bool:
        """
        Check if transaction already exists based on unique characteristics
        """
        try:
            # Check for duplicate based on: date, amount, account_number, content
            response = self.supabase.table("transactions").select("id").match({
                "transaction_date": transaction_data["transaction_date"],
                "transfer_amount": transaction_data["transfer_amount"],
                "account_number": transaction_data["account_number"],
                "content": transaction_data["content"]
            }).execute()
            
            return response.data and len(response.data) > 0
        except Exception as e:
            print(f"Error checking for duplicate: {e}")
            return False
    
    def save_transaction(self, transaction_data: Dict) -> Dict:
        """
        Save transaction to database with auto-categorization
        """
        # Check if transaction already exists
        if self.transaction_exists(transaction_data):
            return {
                "success": True,
                "message": "Transaction already exists",
                "duplicate": True
            }
        
        # Auto-categorize based on content
        category = self.categorize_by_content(transaction_data.get("content", ""))
        
        # Prepare data for insertion
        db_data = {
            "account": transaction_data["account"],
            "transaction_date": transaction_data["transaction_date"],
            "account_number": transaction_data["account_number"],
            "code": transaction_data.get("code"),
            "content": transaction_data["content"],
            "transfer_type": transaction_data["transfer_type"],
            "transfer_amount": transaction_data["transfer_amount"],
            "accumulated": transaction_data.get("accumulated"),
            "description": transaction_data.get("description"),
            "category": category
        }
        
        try:
            # Insert new transaction
            response = self.supabase.table("transactions").insert(db_data).execute()
            
            print(f"✓ Transaction saved:")
            print(f"  Account: {transaction_data['account']}")
            print(f"  Amount: {transaction_data['transfer_amount']:,.0f} VND")
            print(f"  Type: {transaction_data['transfer_type']}")
            print(f"  Category: {category}")
            
            return {
                "success": True,
                "message": "Transaction saved successfully",
                "duplicate": False,
                "transaction": response.data[0] if response.data else None,
                "category": category
            }
        except Exception as e:
            print(f"✗ Error saving transaction: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_sepay_webhook(self, webhook_data: Dict) -> Dict:
        """
        Main processing function for SePay webhook data
        """
        try:
            parsed = self.parse_sepay_transaction(webhook_data)
            result = self.save_transaction(parsed)
            return result
        except Exception as e:
            print(f"✗ Error processing webhook: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Test the processor
if __name__ == "__main__":
    # Load environment variables from .env file for local testing
    from dotenv import load_dotenv
    load_dotenv()
    
    processor = TransactionProcessor()
    
    # Test with sample SePay data from different banks
    sample_transactions = [
        {
            "id": 92704,
            "gateway": "Vietcombank",
            "transactionDate": "2025-09-30 14:02:37",
            "accountNumber": "0123499999",
            "code": None,
            "content": "chuyen tien mua iphone",
            "transferType": "out",
            "transferAmount": 2277000,
            "accumulated": 19077000,
            "subAccount": None,
            "referenceCode": "MBVCB.3278907687",
            "description": ""
        },
        {
            "id": 92705,
            "gateway": "MB",
            "transactionDate": "2025-09-30 15:30:00",
            "accountNumber": "9876543210",
            "code": None,
            "content": "Di cho mua com",
            "transferType": "out",
            "transferAmount": 150000,
            "accumulated": 5000000,
            "subAccount": None,
            "referenceCode": "MB123456",
            "description": ""
        },
        {
            "id": 92706,
            "gateway": "BIDV",
            "transactionDate": "2025-09-30 16:00:00",
            "accountNumber": "1122334455",
            "code": None,
            "content": "Nhan luong thang 9",
            "transferType": "in",
            "transferAmount": 15000000,
            "accumulated": 20000000,
            "subAccount": None,
            "referenceCode": "BIDV789",
            "description": ""
        }
    ]
    
    print("\n=== Testing Transaction Processor ===\n")
    for transaction in sample_transactions:
        result = processor.process_sepay_webhook(transaction)
        print(f"Result: {result.get('message')}")
        print(f"Category: {result.get('category', 'N/A')}")
        print("-" * 50)