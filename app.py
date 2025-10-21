from flask import Flask
from routes import webhook_bp, transaction_bp, cron_bp
import os

# Initialize Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(webhook_bp)
app.register_blueprint(transaction_bp)
app.register_blueprint(cron_bp)

if __name__ == '__main__':
    # This block only runs when executing: python app.py
    # When using gunicorn, the bot thread is started at module level above
    port = int(os.getenv('PORT', 8080))

    print(f"\n{'='*50}")
    print(f"🚀 Budget Tracker API")
    print(f"{'='*50}")
    print(f"📍 Port: {port}")
    print(f"\n📊 Webhooks:")
    print(f"  • SePay:  /webhook/sepay")
    print(f"  • Email:  /webhook/email")
    print(f"\n📈 Transactions:")
    print(f"  • Stats:         /stats")
    print(f"  • Recent:        /transactions/recent")
    print(f"  • By Account:    /transactions/by-account/<account>")
    print(f"  • By Category:   /transactions/by-category/<category>")
    print(f"\n🧪 Testing:")
    print(f"  • Health:        /health")
    print(f"  • Test SePay:    /test")
    print(f"  • Test Email:    /test/email")
    print(f"\n⏰ Cron Jobs:")
    print(f"  • Monthly Report: /cron/monthly-report")
    print(f"  • Test Cron:      /cron/test")
    print(f"{'='*50}\n")

    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=False)