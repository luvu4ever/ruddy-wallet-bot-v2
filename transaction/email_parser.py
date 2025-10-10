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
    
    def fix_mojibake(self, text: str) -> str:
        """
        Fix mojibake encoding issues in Vietnamese text using ftfy
        """
        if not text:
            return text
        
        try:
            import ftfy
            fixed = ftfy.fix_text(text)
            return fixed
        except ImportError:
            print(f"⚠️ ftfy not installed. Install with: pip install ftfy")
            return text
        except Exception as e:
            print(f"⚠️ Error fixing encoding: {e}")
            return text
    
    def parse_bank_email(self, email_content: str, email_subject: str = "") -> Optional[Dict]:
        """
        Parse bank transaction email using Gemini AI
        Returns transaction data in SePay-compatible format
        """
        # Fix encoding issues first
        email_content = self.fix_mojibake(email_content)
        email_subject = self.fix_mojibake(email_subject)
        
        print(f"\n📧 Fixed email content preview:")
        print(email_content[:200] + "..." if len(email_content) > 200 else email_content)
        
        prompt = f"""
You are a bank transaction email parser. Extract transaction information from the email below and return ONLY a valid JSON object.

Email Subject: {email_subject}

Email Content:
{email_content}

Extract the following information and return as JSON:
- gateway: Bank name (Vietcombank, MB, BIDV, Techcombank, VPBank, ACB, Cake, etc.)
- transactionDate: Date and time in format "YYYY-MM-DD HH:MM:SS"
- accountNumber: The account number (sender account)
- content: Transaction description/content
- transferType: "in" for money received, "out" for money spent/transferred
- transferAmount: Amount as a number (no currency symbols or commas)
- accumulated: Account balance after transaction (if available, otherwise null)
- receiver: The receiver name or account if this is a transfer out

Return ONLY the JSON object, no explanation or markdown formatting.

Example output format:
{{
  "gateway": "Cake",
  "transactionDate": "2025-10-08 21:14:13",
  "accountNumber": "0986381568",
  "content": "Chuyen tien ngoai CAKE",
  "transferType": "out",
  "transferAmount": 28000,
  "accumulated": null,
  "receiver": "PHAN THE ANH"
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
    
    # Test with your actual mojibake text
    sample_email = """
    Chào MAI VIẾT DŨNG Cake xin thông báo tài khoản của bạn vừa mới phát sinh giao dịch như sau: Thông tin tài khoản Tài khoản chuyển 0986381568 - Tài khoản thanh toán Tài khoản nhận VQRQADDBO8746 Tên người nhận PHAN THE ANH Ngân hàng nhận MBBank Thông tin giao dịch Loại giao dịch Chuyển tiền ngoài CAKE Mã giao dịch 323781189 Ngày giờ giao dịch 08/10/2025, 21:14:13 Số tiền -28.000 đ Phí giao dịch 0 đ Nội dung giao dịch
    """
    
    result = parser.parse_bank_email(sample_email, "Thông báo giao dịch")
    
    if result:
        print("\n=== Parsed Transaction ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Failed to parse email")