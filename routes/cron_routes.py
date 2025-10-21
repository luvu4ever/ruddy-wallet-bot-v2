from flask import Blueprint, jsonify, request
import os
from handlers.monthly_report_handler import send_monthly_report

cron_bp = Blueprint('cron', __name__)


@cron_bp.route('/cron/monthly-report', methods=['GET', 'POST'])
def monthly_report():
    """
    Endpoint to trigger monthly report generation
    Called by Railway cron job on the 1st of each month
    """
    # Optional: Add authentication via API key
    api_key = request.headers.get('Authorization')
    expected_key = os.getenv('CRON_API_KEY')

    if expected_key and api_key != f"Bearer {expected_key}":
        return jsonify({"error": "Unauthorized"}), 401

    try:
        print("🔔 Monthly report cron job triggered")

        # Generate and send report
        report = send_monthly_report()

        if report:
            return jsonify({
                "success": True,
                "message": "Monthly report sent successfully",
                "month": report.get("month"),
                "total_income": report.get("total_income"),
                "total_expense": report.get("total_expense")
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to generate report"
            }), 500

    except Exception as e:
        print(f"❌ Error in monthly report cron: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cron_bp.route('/cron/test', methods=['GET'])
def test_cron():
    """Test endpoint to verify cron setup"""
    return jsonify({
        "success": True,
        "message": "Cron endpoint is working",
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }), 200
