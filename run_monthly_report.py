#!/usr/bin/env python3
"""
Standalone script to run monthly report
This script is meant to be run by Railway cron service
"""

import asyncio
from handlers.monthly_report_handler import send_monthly_report


async def main():
    """Main entry point for cron job"""
    print("=" * 50)
    print("📊 Monthly Report Cron Job")
    print("=" * 50)

    report = await send_monthly_report()

    if report:
        print("=" * 50)
        print("✅ Monthly report job completed successfully")
        print("=" * 50)
    else:
        print("=" * 50)
        print("❌ Monthly report job failed")
        print("=" * 50)
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
