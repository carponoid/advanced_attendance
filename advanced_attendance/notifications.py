# Copyright (c) 2025, Wins O. Win Nig Ltd and contributors
# For license information, please see license.txt

"""
Email Notifications for Advanced Attendance
Sends alerts for geofence violations, anomalies, and late entries
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, today, add_days


def send_geofence_violation_alert(attendance_doc):
    """
    Send email alert for geofence violation
    
    Args:
        attendance_doc: Attendance document with geofence violation
    """
    if not attendance_doc.has_outside_geofence_checkin:
        return
    
    # Get employee details
    employee = frappe.get_doc('Employee', attendance_doc.employee)
    
    # Get HR Manager emails
    recipients = get_hr_manager_emails(employee.company)
    
    if not recipients:
        return
    
    # Prepare email content
    subject = f"Geofence Violation Alert: {employee.employee_name}"
    
    message = f"""
    <h3>Geofence Violation Detected</h3>
    
    <p><strong>Employee:</strong> {employee.employee_name} ({attendance_doc.employee})</p>
    <p><strong>Date:</strong> {attendance_doc.attendance_date}</p>
    <p><strong>Department:</strong> {attendance_doc.department or 'N/A'}</p>
    <p><strong>Expected Work Site:</strong> {employee.default_work_site or 'Not Set'}</p>
    
    <p>This employee checked in from a location outside the designated geofence boundary.</p>
    
    <p><a href="{frappe.utils.get_url()}/app/attendance/{attendance_doc.name}">View Attendance Record</a></p>
    
    <p style="color: #666; font-size: 12px;">
    This is an automated alert from the Advanced Attendance System.
    </p>
    """
    
    # Send email
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        reference_doctype='Attendance',
        reference_name=attendance_doc.name
    )
    
    frappe.log_error(f"Geofence violation alert sent for {attendance_doc.name}", "Geofence Alert")


def send_device_anomaly_alert(attendance_doc):
    """
    Send email alert for device fingerprint anomaly
    
    Args:
        attendance_doc: Attendance document with device anomaly
    """
    if not attendance_doc.device_fingerprint_anomaly:
        return
    
    # Get employee details
    employee = frappe.get_doc('Employee', attendance_doc.employee)
    
    # Get HR Manager emails
    recipients = get_hr_manager_emails(employee.company)
    
    if not recipients:
        return
    
    # Prepare email content
    subject = f"Device Anomaly Alert: {employee.employee_name}"
    
    message = f"""
    <h3>Device Fingerprint Anomaly Detected</h3>
    
    <p><strong>Employee:</strong> {employee.employee_name} ({attendance_doc.employee})</p>
    <p><strong>Date:</strong> {attendance_doc.attendance_date}</p>
    <p><strong>Department:</strong> {attendance_doc.department or 'N/A'}</p>
    
    <p style="color: #d9534f;">
    <strong>⚠️ Suspicious Activity:</strong> Multiple devices detected for this employee's check-ins.
    This may indicate device sharing or fraudulent attendance.
    </p>
    
    <p><a href="{frappe.utils.get_url()}/app/attendance/{attendance_doc.name}">View Attendance Record</a></p>
    
    <p style="color: #666; font-size: 12px;">
    This is an automated alert from the Advanced Attendance System.
    </p>
    """
    
    # Send email
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        reference_doctype='Attendance',
        reference_name=attendance_doc.name
    )
    
    frappe.log_error(f"Device anomaly alert sent for {attendance_doc.name}", "Device Anomaly Alert")


def send_late_entry_alert(attendance_doc):
    """
    Send email alert for late entry
    
    Args:
        attendance_doc: Attendance document with late entry
    """
    if not attendance_doc.late_entry:
        return
    
    # Get employee details
    employee = frappe.get_doc('Employee', attendance_doc.employee)
    
    # Get employee's reporting manager email
    recipients = []
    
    if employee.reports_to:
        manager = frappe.get_doc('Employee', employee.reports_to)
        if manager.user_id:
            recipients.append(manager.user_id)
    
    # Also send to HR Manager
    recipients.extend(get_hr_manager_emails(employee.company))
    
    if not recipients:
        return
    
    # Prepare email content
    subject = f"Late Entry: {employee.employee_name} - {attendance_doc.attendance_date}"
    
    message = f"""
    <h3>Late Entry Notification</h3>
    
    <p><strong>Employee:</strong> {employee.employee_name} ({attendance_doc.employee})</p>
    <p><strong>Date:</strong> {attendance_doc.attendance_date}</p>
    <p><strong>Department:</strong> {attendance_doc.department or 'N/A'}</p>
    <p><strong>Shift:</strong> {attendance_doc.shift or 'Not Set'}</p>
    <p><strong>Check-in Time:</strong> {attendance_doc.in_time}</p>
    
    <p>This employee arrived late to work.</p>
    
    <p><a href="{frappe.utils.get_url()}/app/attendance/{attendance_doc.name}">View Attendance Record</a></p>
    
    <p style="color: #666; font-size: 12px;">
    This is an automated notification from the Advanced Attendance System.
    </p>
    """
    
    # Send email
    frappe.sendmail(
        recipients=list(set(recipients)),  # Remove duplicates
        subject=subject,
        message=message,
        reference_doctype='Attendance',
        reference_name=attendance_doc.name
    )


def send_daily_anomaly_summary():
    """
    Send daily summary of all anomalies detected
    Runs at end of day
    """
    date = today()
    
    # Get all anomalies for the day
    geofence_violations = frappe.db.count('Attendance', {
        'attendance_date': date,
        'has_outside_geofence_checkin': 1
    })
    
    device_anomalies = frappe.db.count('Attendance', {
        'attendance_date': date,
        'device_fingerprint_anomaly': 1
    })
    
    late_entries = frappe.db.count('Attendance', {
        'attendance_date': date,
        'late_entry': 1
    })
    
    early_exits = frappe.db.count('Attendance', {
        'attendance_date': date,
        'early_exit': 1
    })
    
    # Only send if there are anomalies
    if not any([geofence_violations, device_anomalies, late_entries, early_exits]):
        return
    
    # Get all HR Managers
    recipients = get_all_hr_manager_emails()
    
    if not recipients:
        return
    
    # Prepare email content
    subject = f"Daily Attendance Anomaly Summary - {date}"
    
    message = f"""
    <h3>Daily Attendance Anomaly Summary</h3>
    <p><strong>Date:</strong> {date}</p>
    
    <table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
        <tr style="background-color: #f5f5f5;">
            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Anomaly Type</th>
            <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Count</th>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">Geofence Violations</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: center; color: {('#d9534f' if geofence_violations > 0 else '#5cb85c')}">{geofence_violations}</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">Device Anomalies</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: center; color: {('#d9534f' if device_anomalies > 0 else '#5cb85c')}">{device_anomalies}</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">Late Entries</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: center; color: {('#f0ad4e' if late_entries > 0 else '#5cb85c')}">{late_entries}</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">Early Exits</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: center; color: {('#f0ad4e' if early_exits > 0 else '#5cb85c')}">{early_exits}</td>
        </tr>
    </table>
    
    <p><a href="{frappe.utils.get_url()}/app/query-report/Geofence%20Violation%20Report">View Detailed Reports</a></p>
    
    <p style="color: #666; font-size: 12px;">
    This is an automated daily summary from the Advanced Attendance System.
    </p>
    """
    
    # Send email
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message
    )
    
    frappe.log_error(f"Daily anomaly summary sent for {date}", "Daily Summary")


def get_hr_manager_emails(company=None):
    """
    Get email addresses of HR Managers
    
    Args:
        company: Filter by company
        
    Returns:
        list: List of email addresses
    """
    filters = {'role': 'HR Manager'}
    
    if company:
        filters['company'] = company
    
    users = frappe.get_all(
        'Has Role',
        filters={'role': 'HR Manager'},
        fields=['parent']
    )
    
    emails = []
    for user in users:
        email = frappe.db.get_value('User', user.parent, 'email')
        if email:
            emails.append(email)
    
    return list(set(emails))


def get_all_hr_manager_emails():
    """Get all HR Manager emails across all companies"""
    return get_hr_manager_emails()


@frappe.whitelist()
def test_notification(notification_type='geofence'):
    """
    Test notification system
    
    Args:
        notification_type: Type of notification to test
    """
    # Get a sample attendance record
    attendance = frappe.get_last_doc('Attendance')
    
    if notification_type == 'geofence':
        attendance.has_outside_geofence_checkin = 1
        send_geofence_violation_alert(attendance)
    elif notification_type == 'device':
        attendance.device_fingerprint_anomaly = 1
        send_device_anomaly_alert(attendance)
    elif notification_type == 'late':
        attendance.late_entry = 1
        send_late_entry_alert(attendance)
    elif notification_type == 'summary':
        send_daily_anomaly_summary()
    
    return {'success': True, 'message': f'Test {notification_type} notification sent'}
