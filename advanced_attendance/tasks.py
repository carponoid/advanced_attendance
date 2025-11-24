import frappe
from frappe.utils import now_datetime, add_days, getdate
from .utils import (
    process_attendance_window,
    summarize_anomalies_for_date
)

def sync_biometric_devices():
    """
    Placeholder for ZKTeco device sync.

    NOTE:
    - If you are using a separate ZK connector app that already writes to Employee Checkin,
      you can leave this empty or remove it from the scheduler.
    - If you implement a custom connector later, call it from here.
    """
    frappe.logger().info("advanced_attendance.sync_biometric_devices: no-op (connector app should handle sync).")


def process_attendance_punches():
    """
    Scheduled job to process attendance for recent days.
    Typical window: yesterday and today (or last 2-3 days).
    """
    today = getdate()
    from_date = add_days(today, -2)
    to_date = today

    frappe.logger().info(f"advanced_attendance.process_attendance_punches: processing from {from_date} to {to_date}")

    process_attendance_window(from_date, to_date)


def generate_daily_anomaly_snapshot():
    """
    Scheduled job to summarize anomalies for previous day.
    Can be extended to send emails or update dashboard.
    """
    today = getdate()
    target_date = add_days(today, -1)

    frappe.logger().info(f"advanced_attendance.generate_daily_anomaly_snapshot: summarizing for {target_date}")

    summarize_anomalies_for_date(target_date)
