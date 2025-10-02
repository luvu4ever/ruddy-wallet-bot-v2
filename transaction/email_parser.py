import os
import json
import re
import google.generativeai as genai
from datetime import datetime
from typing import Dict, Optional

class EmailParser:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Known banks for validation
        self.known_banks = [
            'Vietcombank', 'VCB', 'BIDV', 'MB', 'MBBank', 'Techcombank', 'TCB',
            'VPBank', 'VPB', 'ACB', 'Sacombank', 'STB', 'Agribank', 'AGB',
            'VietinBank', 'CTG', 'Cake', 'Timo', 'TPBank', 'HDBank', 'SHB',
            'SeABank', 'MSB', 'VIB', 'OCB', 'Eximbank', 'SCB', 'LienVietPostBank',
            'BacABank', 'PVcomBank', 'NCB', 'KienlongBank', 'VietBank', 'VietCapitalBank'
        ]
    
    def parse_bank_email(self, email_content: str, email_subject: str = "") -> Optional[Dict]:
        """
        Parse bank transaction email using Gemini AI
        Returns transaction data in SePay-compatible format
        """
        prompt = f"""
You are a Vietnamese bank transaction email parser. Extract transaction information and return ONLY a valid JSON object.

IMPORTANT DISTINCTIONS:
1. **gateway**: This is the BANK that sent the notification (Vietcombank, MB, BIDV, Techcombank, VPBank, ACB, Cake, Timo, etc.)
   - Look for "MB Bank", "Vietcombank", "Cake by VPBank", "Timo by VPBank" in the sender or header
   - This is NOT the merchant/receiver
   
2. **accountNumber**: YOUR account number at that bank
   - Usually shown as "Số TK:", "Tài khoản:", "Account:"
   - This is YOUR account, not the receiver's
   
3. **receiver**: The person/merchant you paid to OR who paid you
   - For payments OUT: Grab, Shopee, Lazada, store names, person names
   - For money IN: Sender's name or "Unknown" if not specified
   - Extract from the transaction content/description
   - DO NOT put bank names here (Cake, Timo are banks, not receivers)

4. **content**: The transaction description
   - The full description from "Nội dung:", "Content:", "Diễn giải:"
   - May contain receiver information embedded

Email Subject: {email_subject}

Email Content:
{email_content}

Extract and return as JSON:
{{
  "gateway": "Bank name that sent this notification (MB, Vietcombank, Cake, Timo, etc.)",
  "transactionDate": "YYYY-MM-DD HH:MM:SS format",
  "accountNumber": "Your account number at this bank",
  "receiver": "Who you paid to (Grab, Shopee, etc.) or who paid you. Use 'Unknown' if not clear. NEVER use bank names here.",
  "content": "Full transaction description",
  "transferType": "out" for money spent, "in" for money received,
  "transferAmount": number without commas or symbols,
  "accumulated": balance after transaction or null if not available
}}

EXAMPLE 1 (Cake Bank - Payment):
Subject: Thông báo giao dịch Cake
Body: "Cake by VPBank\nTK: 123456\nThời gian: 01/10/2025 14:30\nSố tiền: -50,000 VND\nNội dung: Thanh toan Grab\nSố dư: 1,000,000"

Correct output:
{{
  "gateway": "Cake",
  "accountNumber": "123456",
  "receiver": "Grab",
  "content": "Thanh toan Grab",
  "transferType": "out",
  "transferAmount": 50000,
  ...
}}

WRONG output (DO NOT DO THIS):
{{
  "gateway": "Grab",  ❌ Wrong! Grab is receiver, not bank
  "receiver": "Cake", ❌ Wrong! Cake is the bank, not receiver
  ...
}}

EXAMPLE 2 (MB Bank - Receive money):
Body: "MB Bank\nTK: 688619102003\nNhận tiền từ: Nguyen Van A\nSố tiền: +500,000 VND"

Correct output:
{{
  "gateway": "MB",
  "accountNumber": "688619102003",
  "receiver": "Nguyen Van A",
  "transferType": "in",
  "transferAmount": 500000,
  ...
}}

Return ONLY the JSON, no markdown formatting or explanation.
If not a bank transaction email, return: {{"error": "Not a valid bank transaction email"}}
"""
        
        try:
            print(f"\n🤖 Parsing email with Gemini AI...")
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            parsed_data = json.loads(response_text)
            
            # Check if there's an error
            if "error" in parsed_data:
                print(f"❌ Gemini couldn't parse: {parsed_data['error']}")
                return None
            
            # Validate required fields
            required_fields = ["gateway", "transactionDate", "content", "transferType", "transferAmount"]
            for field in required_fields:
                if field not in parsed_data:
                    print(f"❌ Missing required field: {field}")
                    return None
            
            # Post-processing validation: Check if gateway is a known bank
            gateway = parsed_data.get("gateway", "")
            if not any(bank.lower() in gateway.lower() for bank in self.known_banks):
                print(f"⚠️ Warning: '{gateway}' might not be a valid bank name")
            
            # Check if receiver is accidentally a bank name
            receiver = parsed_data.get("receiver", "")
            if receiver and any(bank.lower() == receiver.lower() for bank in self.known_banks):
                print(f"⚠️ Warning: Receiver '{receiver}' looks like a bank name - setting to Unknown")
                parsed_data["receiver"] = "Unknown"
            
            # Add default values for optional fields
            if "accountNumber" not in parsed_data:
                parsed_data["accountNumber"] = "Unknown"
            if "accumulated" not in parsed_data:
                parsed_data["accumulated"] = None
            if "receiver" not in parsed_data:
                parsed_data["receiver"] = "Unknown"
            if "code" not in parsed_data:
                parsed_data["code"] = None
            if "subAccount" not in parsed_data:
                parsed_data["subAccount"] = None
            if "referenceCode" not in parsed_data:
                parsed_data["referenceCode"] = None
            if "description" not in parsed_data:
                parsed_data["description"] = email_content[:500]
            
            # Add unique ID (timestamp-based)
            parsed_data["id"] = int(datetime.now().timestamp() * 1000)
            
            print(f"✅ Successfully parsed transaction:")
            print(f"   Bank (gateway): {parsed_data['gateway']}")
            print(f"   Account: {parsed_data['accountNumber']}")
            print(f"   Receiver: {parsed_data['receiver']}")
            print(f"   Amount: {parsed_data['transferAmount']:,.0f} VND")
            print(f"   Type: {parsed_data['transferType']}")
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from Gemini response: {e}")
            print(f"Response was: {response_text[:500]}")
            return None
        except Exception as e:
            print(f"❌ Error parsing email with Gemini: {e}")
            return None