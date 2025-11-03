import os
from datetime import datetime
from supabase import create_client, Client
from typing import Dict, Optional, List, Tuple

class TransactionProcessor:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Cache for known receivers to reduce database calls
        self._receiver_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # Cache for 5 minutes
    
    def get_account_name(self, gateway: str) -> str:
        """
        Convert gateway name to simplified account name
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
        
        return gateway_mapping.get(gateway, gateway)
    
    def parse_sepay_transaction(self, sepay_data: Dict) -> Dict:
        """
        Parse transaction data from SePay webhook
        """
        transaction_date = sepay_data.get("transactionDate")
        if transaction_date:
            try:
                dt = datetime.strptime(transaction_date, "%Y-%m-%d %H:%M:%S")
                transaction_date = dt.isoformat()
            except ValueError:
                transaction_date = datetime.now().isoformat()
        else:
            transaction_date = datetime.now().isoformat()
        
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
    
    def _load_known_receivers(self) -> List[Dict]:
        """
        Load known receivers from database with caching
        """
        current_time = datetime.now().timestamp()
        
        # Return cached data if still valid
        if (self._receiver_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._receiver_cache
        
        try:
            response = self.supabase.table("known_receivers").select("*").execute()
            self._receiver_cache = response.data if response.data else []
            self._cache_timestamp = current_time
            return self._receiver_cache
        except Exception as e:
            print(f"⚠️ Error loading known receivers: {e}")
            return []
    
    def categorize_and_format_transaction(self, transaction_data: Dict) -> Tuple[str, Optional[str]]:
        """
        Categorize transaction and optionally replace content based on known_receivers patterns
        
        Returns:
            Tuple[str, Optional[str]]: (category, new_content)
            - category: The matched category or "Uncategorized"
            - new_content: The replacement content if specified, otherwise None
        """
        # Combine all text fields for matching
        text_fields = [
            transaction_data.get("content", ""),
            transaction_data.get("description", ""),
            transaction_data.get("receiver", ""),
            transaction_data.get("code", ""),
        ]
        
        # Create combined lowercase text for matching
        combined_text = " ".join([str(field).lower() for field in text_fields if field])
        
        if not combined_text.strip():
            return "Uncategorized", None
        
        # Load known receivers
        known_receivers = self._load_known_receivers()
        
        if not known_receivers:
            return "Uncategorized", None
        
        # Check each pattern
        for receiver in known_receivers:
            pattern = receiver.get("receiver_pattern", "").lower().strip()
            
            if not pattern:
                continue
            
            # Simple substring match
            if pattern in combined_text:
                category = receiver.get("category", "Uncategorized")
                new_content = receiver.get("new_content")
                
                print(f"✓ Matched pattern: '{pattern}' -> Category: {category}")
                
                if new_content:
                    print(f"  📝 Content will be replaced: '{transaction_data.get('content')}' -> '{new_content}'")
                
                return category, new_content
        
        return "Uncategorized", None
    
    def transaction_exists(self, transaction_data: Dict) -> bool:
        """
        Check if transaction already exists based on unique characteristics
        """
        try:
            response = self.supabase.table("transactions").select("id").match({
                "transaction_date": transaction_data["transaction_date"],
                "transfer_amount": transaction_data["transfer_amount"],
                "account_number": transaction_data["account_number"],
                "content": transaction_data["content"]
            }).execute()
            
            return response.data and len(response.data) > 0
        except Exception as e:
            print(f"⚠️ Error checking for duplicate: {e}")
            return False
    
    def save_transaction(self, transaction_data: Dict) -> Dict:
        """
        Save transaction to database with auto-categorization and content replacement
        Handles motor-bike parking fee aggregation for small transactions
        """
        # Check if transaction already exists (with original content)
        if self.transaction_exists(transaction_data):
            return {
                "success": True,
                "message": "Transaction already exists",
                "duplicate": True
            }

        # Auto-categorize and get new content if available
        category, new_content = self.categorize_and_format_transaction(transaction_data)

        # Replace content if new_content is specified
        if new_content:
            transaction_data["content"] = new_content

        # Handle motor-bike parking aggregation
        parking_data = self._handle_motor_bike_parking(transaction_data, category)
        should_aggregate = parking_data.pop("should_aggregate", False)
        existing_id = parking_data.pop("existing_id", None)
        should_create_new = parking_data.pop("should_create_new", False)

        if should_aggregate:
            if existing_id:
                # Update existing aggregation
                self._update_motor_bike_parking(existing_id, transaction_data["transfer_amount"])
                return {
                    "success": True,
                    "message": "Transaction aggregated to existing parking entry",
                    "duplicate": False,
                    "aggregated": True,
                    "category": category
                }
            elif should_create_new:
                # Create new aggregation entry with aggregated content
                month_key = self._get_month_key(transaction_data["transaction_date"])
                aggregated_content = f"motor-bike park {month_key}"

                db_data = {
                    "account": transaction_data["account"],
                    "transaction_date": transaction_data["transaction_date"],
                    "account_number": transaction_data["account_number"],
                    "code": transaction_data.get("code"),
                    "content": aggregated_content,
                    "transfer_type": transaction_data["transfer_type"],
                    "transfer_amount": transaction_data["transfer_amount"],
                    "accumulated": transaction_data.get("accumulated"),
                    "description": transaction_data.get("description"),
                    "category": category
                }

                try:
                    response = self.supabase.table("transactions").insert(db_data).execute()
                    print(f"✅ New parking aggregation created: {aggregated_content} ({transaction_data['transfer_amount']:,.0f} VND)")

                    return {
                        "success": True,
                        "message": "New parking aggregation created",
                        "duplicate": False,
                        "transaction": response.data[0] if response.data else None,
                        "category": category,
                        "aggregated": True
                    }
                except Exception as e:
                    print(f"❌ Error creating parking aggregation: {e}")
                    return {
                        "success": False,
                        "error": str(e)
                    }

        # Regular transaction saving (not parking)
        db_data = {
            "account": transaction_data["account"],
            "transaction_date": transaction_data["transaction_date"],
            "account_number": transaction_data["account_number"],
            "code": transaction_data.get("code"),
            "content": transaction_data["content"],  # This will be the new_content if replaced
            "transfer_type": transaction_data["transfer_type"],
            "transfer_amount": transaction_data["transfer_amount"],
            "accumulated": transaction_data.get("accumulated"),
            "description": transaction_data.get("description"),
            "category": category
        }

        try:
            response = self.supabase.table("transactions").insert(db_data).execute()

            print(f"✅ Transaction saved:")
            print(f"  Account: {transaction_data['account']}")
            print(f"  Amount: {transaction_data['transfer_amount']:,.0f} VND")
            print(f"  Type: {transaction_data['transfer_type']}")
            print(f"  Category: {category}")
            if new_content:
                print(f"  Content (modified): {transaction_data['content']}")

            return {
                "success": True,
                "message": "Transaction saved successfully",
                "duplicate": False,
                "transaction": response.data[0] if response.data else None,
                "category": category,
                "content_modified": new_content is not None
            }
        except Exception as e:
            print(f"❌ Error saving transaction: {e}")
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
            print(f"❌ Error processing webhook: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def refresh_receiver_cache(self):
        """
        Manually refresh the known receivers cache
        Useful after adding new patterns to the database
        """
        self._receiver_cache = None
        self._cache_timestamp = None
        print("🔄 Receiver cache cleared")

    def _get_month_key(self, transaction_date: str) -> str:
        """
        Extract month key from transaction date (MM/YYYY format)
        """
        try:
            dt = datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
            return dt.strftime('%m/%Y')
        except Exception as e:
            print(f"⚠️ Error extracting month key: {e}")
            return datetime.now().strftime('%m/%Y')

    def _handle_motor_bike_parking(self, transaction_data: Dict, category: str) -> Dict:
        """
        Handle motor-bike parking fee aggregation for transactions <= 5000 VND

        Args:
            transaction_data: The transaction data
            category: The matched category

        Returns:
            Modified transaction data with aggregated content if applicable
        """
        # Check if this is a motor-bike parking category and amount <= 5000
        if category.lower() != "motor-bike parking" or transaction_data["transfer_amount"] > 5000:
            return transaction_data

        month_key = self._get_month_key(transaction_data["transaction_date"])
        aggregated_content = f"motor-bike park {month_key}"

        # Check if an aggregated entry exists for this month
        try:
            response = self.supabase.table("transactions").select(
                "id, content, transfer_amount"
            ).eq(
                "content", aggregated_content
            ).order(
                "transaction_date", desc=True
            ).limit(1).execute()

            if response.data and len(response.data) > 0:
                # Found existing aggregated entry, we'll update it later
                existing_txn = response.data[0]
                print(f"✓ Found existing parking aggregation: {aggregated_content}")
                return {
                    **transaction_data,
                    "should_aggregate": True,
                    "existing_id": existing_txn["id"],
                    "existing_amount": existing_txn["transfer_amount"]
                }
            else:
                # No existing aggregation, will create new one
                print(f"✓ Creating new parking aggregation: {aggregated_content}")
                return {
                    **transaction_data,
                    "should_aggregate": True,
                    "should_create_new": True
                }
        except Exception as e:
            print(f"⚠️ Error checking parking aggregation: {e}")
            return transaction_data

    def _update_motor_bike_parking(self, existing_id: str, amount_to_add: float) -> bool:
        """
        Update existing motor-bike parking aggregation with new amount
        """
        try:
            # Get current amount
            response = self.supabase.table("transactions").select(
                "transfer_amount"
            ).eq(
                "id", existing_id
            ).execute()

            if not response.data:
                return False

            current_amount = response.data[0]["transfer_amount"]
            new_amount = current_amount + amount_to_add

            # Update the transaction
            self.supabase.table("transactions").update({
                "transfer_amount": new_amount
            }).eq(
                "id", existing_id
            ).execute()

            print(f"✅ Updated parking aggregation: {current_amount} + {amount_to_add} = {new_amount} VND")
            return True
        except Exception as e:
            print(f"⚠️ Error updating parking aggregation: {e}")
            return False