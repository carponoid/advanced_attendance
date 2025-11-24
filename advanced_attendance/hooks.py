from . import __version__ as app_version
app_name = "advanced_attendance"
app_title = "Advanced Attendance"
app_publisher = "Winco Group"
app_description = "Advanced multi-source attendance and roster system with geofencing, mobile clock-in, and biometric integration"
app_email = "admin@winco-group.com"
app_license = "MIT"

# Explicit JS mapping for DocTypes in this app
doctype_js = {
    # Ensures Biometric Device Settings form always loads our JS,
    # even if Frappe's auto-detect for DocType JS is inconsistent.
    "Biometric Device Settings": "public/js/biometric_device_settings.js"
}

# Include fixtures if you later want to export roles/permissions, etc.
fixtures = []

# Scheduler events
scheduler_events = {
    "cron": {
        # Sync biometric devices every 5 minutes (optional)
        "*/5 * * * *": [
            "advanced_attendance.tasks.sync_biometric_devices"
        ]
    },
    "hourly": [
        "advanced_attendance.tasks.process_attendance_punches"
    ],
    "daily": [
        "advanced_attendance.tasks.generate_daily_anomaly_snapshot",
        "advanced_attendance.overtime_calculator.process_daily_overtime",
        "advanced_attendance.notifications.send_daily_anomaly_summary"
    ]
}
# Website routes (clock-in page is under www/clock_in.html so no extra config needed)
