import os
import json
import google.generativeai as genai
from datetime import datetime
from typing import Dict, Optional

class EmailParser:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def parse_bank_email(self, email_content: str, email_subject: str = "") -> Optional[Dict]:
        """
        Parse bank transaction email using Gemini AI
        Returns transaction data in SePay-compatible format
        """
        prompt = f"""
You are a bank transaction email parser. Extract transaction information from the email below and return ONLY a valid JSON object.

Email Subject: {email_subject}

Email Content:
{email_content}

Extract the following information and return as JSON:
- gateway: Bank name (Vietcombank, MB, BIDV, Techcombank, VPBank, ACB, etc.)
- transactionDate: Date and time in format "YYYY-MM-DD HH:MM:SS"
- accountNumber: The account number (last 3-4 digits if masked)
- content: Transaction description/content
- transferType: "in" for money received, "out" for money spent
- transferAmount: Amount as a number (no currency symbols or commas)
- accumulated: Account balance after transaction (if available, otherwise null)

Return ONLY the JSON object, no explanation or markdown formatting.

Example output format:
{{
  "gateway": "MBBank",
  "transactionDate": "2025-10-01 14:30:00",
  "accountNumber": "688619102003",
  "content": "Thanh toan tai Grab",
  "transferType": "out",
  "transferAmount": 45000,
  "accumulated": 5000000
}}

If you cannot extract the information or this is not a bank transaction email, return:
{{"error": "Not a valid bank transaction email"}}
"""
        
        try:
            print(f"\n🤖 Sending email to Gemini AI for parsing...")
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
            
            # Add default values for optional fields
            if "accountNumber" not in parsed_data:
                parsed_data["accountNumber"] = "Unknown"
            if "accumulated" not in parsed_data:
                parsed_data["accumulated"] = None
            if "code" not in parsed_data:
                parsed_data["code"] = None
            if "subAccount" not in parsed_data:
                parsed_data["subAccount"] = None
            if "referenceCode" not in parsed_data:
                parsed_data["referenceCode"] = None
            if "description" not in parsed_data:
                parsed_data["description"] = email_content[:500]  # First 500 chars
            
            # Add unique ID (timestamp-based)
            parsed_data["id"] = int(datetime.now().timestamp() * 1000)
            
            print(f"✅ Successfully parsed transaction:")
            print(f"   Bank: {parsed_data['gateway']}")
            print(f"   Amount: {parsed_data['transferAmount']:,.0f} VND")
            print(f"   Type: {parsed_data['transferType']}")
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from Gemini response: {e}")
            print(f"Response was: {response_text}")
            return None
        except Exception as e:
            print(f"❌ Error parsing email with Gemini: {e}")
            return None


# Test the parser
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    parser = EmailParser()
    
    # Test with sample email
    sample_email = """
    Thông báo biến động số dư tài khoản
    
    Kính gửi Quý khách,
    
    MB Bank xin thông báo tài khoản của Quý khách có giao dịch như sau:
    
    - Số tài khoản: 688619102003
    - Thời gian: 01/10/2025 14:30:00
    - Loại giao dịch: Chuyển tiền
    - Số tiền: -500,000 VND
    - Nội dung: Thanh toan Grab
    - Số dư: 5,000,000 VND
    
    Trân trọng,
    MB Bank
    """
    
    result = parser.parse_bank_email(sample_email, "Thông báo giao dịch")
    
    if result:
        print("\n=== Parsed Transaction ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Failed to parse email")