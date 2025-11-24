# Copyright (c) 2025, Wins O. Win Nig Ltd and contributors
# For license information, please see license.txt

"""
Overtime and Break Time Calculator
Calculates overtime hours and tracks break times
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, time_diff_in_hours, flt
from datetime import datetime, timedelta


def calculate_overtime(attendance_doc):
    """
    Calculate overtime hours for an attendance record
    
    Args:
        attendance_doc: Attendance document
        
    Returns:
        float: Overtime hours
    """
    if not attendance_doc.in_time or not attendance_doc.out_time:
        return 0.0
    
    # Get shift details
    if not attendance_doc.shift:
        return 0.0
    
    shift = frappe.get_doc('Shift Type', attendance_doc.shift)
    
    if not shift.start_time or not shift.end_time:
        return 0.0
    
    # Convert timedelta to time
    shift_start = (datetime.min + shift.start_time).time()
    shift_end = (datetime.min + shift.end_time).time()
    
    # Get actual work time
    in_time = get_datetime(attendance_doc.in_time)
    out_time = get_datetime(attendance_doc.out_time)
    
    # Calculate expected shift hours
    shift_hours = time_diff_in_hours(
        datetime.combine(datetime.today(), shift_end),
        datetime.combine(datetime.today(), shift_start)
    )
    
    # Calculate actual working hours
    actual_hours = time_diff_in_hours(out_time, in_time)
    
    # Overtime is hours worked beyond shift hours
    overtime_hours = max(0, actual_hours - shift_hours)
    
    # Apply overtime rules if configured
    overtime_hours = apply_overtime_rules(overtime_hours, shift)
    
    return flt(overtime_hours, 2)


def apply_overtime_rules(overtime_hours, shift):
    """
    Apply overtime calculation rules
    
    Args:
        overtime_hours: Raw overtime hours
        shift: Shift Type document
        
    Returns:
        float: Adjusted overtime hours
    """
    # Check if shift has overtime threshold
    if hasattr(shift, 'overtime_threshold') and shift.overtime_threshold:
        # Only count overtime after threshold
        overtime_hours = max(0, overtime_hours - shift.overtime_threshold)
    
    # Apply overtime multiplier if configured
    if hasattr(shift, 'overtime_multiplier') and shift.overtime_multiplier:
        overtime_hours = overtime_hours * shift.overtime_multiplier
    
    return overtime_hours


def calculate_break_time(employee, date):
    """
    Calculate total break time for an employee on a specific date
    
    Args:
        employee: Employee ID
        date: Date to calculate break time
        
    Returns:
        float: Total break time in hours
    """
    # Get all check-ins for the day
    checkins = frappe.get_all(
        'Employee Checkin',
        filters={
            'employee': employee,
            'time': ['between', [f'{date} 00:00:00', f'{date} 23:59:59']]
        },
        fields=['time', 'log_type'],
        order_by='time asc'
    )
    
    if len(checkins) < 2:
        return 0.0
    
    break_time = 0.0
    in_break = False
    break_start = None
    
    for checkin in checkins:
        if checkin.log_type == 'OUT' and not in_break:
            # Start of break
            in_break = True
            break_start = get_datetime(checkin.time)
        elif checkin.log_type == 'IN' and in_break:
            # End of break
            if break_start:
                break_end = get_datetime(checkin.time)
                break_time += time_diff_in_hours(break_end, break_start)
            in_break = False
            break_start = None
    
    return flt(break_time, 2)


def update_attendance_with_overtime(attendance_name):
    """
    Update attendance record with calculated overtime
    
    Args:
        attendance_name: Attendance document name
    """
    attendance = frappe.get_doc('Attendance', attendance_name)
    
    # Calculate overtime
    overtime_hours = calculate_overtime(attendance)
    
    # Calculate break time
    break_hours = calculate_break_time(
        attendance.employee,
        attendance.attendance_date
    )
    
    # Update attendance
    attendance.db_set('custom_overtime_hours', overtime_hours, update_modified=False)
    attendance.db_set('custom_break_hours', break_hours, update_modified=False)
    
    # Calculate net working hours (working hours - break hours)
    if attendance.working_hours:
        net_hours = flt(attendance.working_hours) - break_hours
        attendance.db_set('custom_net_working_hours', net_hours, update_modified=False)
    
    frappe.db.commit()


def get_overtime_summary(employee, from_date, to_date):
    """
    Get overtime summary for an employee
    
    Args:
        employee: Employee ID
        from_date: Start date
        to_date: End date
        
    Returns:
        dict: Overtime summary
    """
    attendances = frappe.get_all(
        'Attendance',
        filters={
            'employee': employee,
            'attendance_date': ['between', [from_date, to_date]],
            'status': 'Present'
        },
        fields=['name', 'attendance_date', 'working_hours', 'shift']
    )
    
    total_overtime = 0.0
    total_break_time = 0.0
    overtime_days = []
    
    for att in attendances:
        attendance = frappe.get_doc('Attendance', att.name)
        overtime = calculate_overtime(attendance)
        break_time = calculate_break_time(employee, att.attendance_date)
        
        if overtime > 0:
            total_overtime += overtime
            overtime_days.append({
                'date': att.attendance_date,
                'overtime_hours': overtime,
                'break_hours': break_time,
                'shift': att.shift
            })
        
        total_break_time += break_time
    
    return {
        'employee': employee,
        'from_date': from_date,
        'to_date': to_date,
        'total_overtime_hours': flt(total_overtime, 2),
        'total_break_hours': flt(total_break_time, 2),
        'overtime_days_count': len(overtime_days),
        'overtime_days': overtime_days
    }


@frappe.whitelist()
def get_employee_overtime_summary(employee, from_date, to_date):
    """
    API method to get employee overtime summary
    
    Args:
        employee: Employee ID
        from_date: Start date
        to_date: End date
        
    Returns:
        dict: Overtime summary
    """
    return get_overtime_summary(employee, from_date, to_date)


def process_daily_overtime():
    """
    Process overtime for all attendance records from yesterday
    Runs as a scheduled job
    """
    from frappe.utils import add_days, today
    
    yesterday = add_days(today(), -1)
    
    # Get all attendance records from yesterday
    attendances = frappe.get_all(
        'Attendance',
        filters={
            'attendance_date': yesterday,
            'status': 'Present'
        },
        fields=['name']
    )
    
    processed = 0
    errors = []
    
    for att in attendances:
        try:
            update_attendance_with_overtime(att.name)
            processed += 1
        except Exception as e:
            errors.append(f"{att.name}: {str(e)}")
    
    # Log results
    frappe.log_error(
        f"Processed overtime for {processed} attendance records. Errors: {len(errors)}",
        "Daily Overtime Processing"
    )
    
    if errors:
        frappe.log_error('\n'.join(errors), "Overtime Processing Errors")
    
    return {
        'processed': processed,
        'errors': len(errors)
    }
