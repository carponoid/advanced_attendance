# Copyright (c) 2025, Wins O. Win Nig Ltd and contributors
# For license information, please see license.txt

"""
ZKTeco Biometric Device Connector (Enhanced with pyzk)
Syncs attendance data from ZKTeco devices to ERPNext
Supports multiple ZKTeco models including MB160 Plus
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime
from zk import ZK, const


class ZKTecoConnector:
    """
    ZKTeco Device Connector using pyzk library
    Connects to ZKTeco biometric devices and syncs attendance data
    Supports multiple device models and protocols
    """
    
    def __init__(self, device_ip, device_port=4370, timeout=10, password=None):
        """
        Initialize connector
        
        Args:
            device_ip: IP address of the ZKTeco device
            device_port: Port number (default 4370)
            timeout: Connection timeout in seconds
            password: Device communication password (optional)
        """
        self.device_ip = device_ip
        self.device_port = device_port
        self.timeout = timeout
        self.password = password or 0
        self.zk = None
        self.conn = None
    
    def connect(self):
        """Connect to the ZKTeco device"""
        try:
            # Create ZK instance
            self.zk = ZK(
                self.device_ip, 
                port=self.device_port, 
                timeout=self.timeout,
                password=self.password
            )
            
            # Connect to device
            self.conn = self.zk.connect()
            
            if self.conn:
                frappe.logger().info(f"Connected to ZKTeco device at {self.device_ip}:{self.device_port}")
                return True
            
            return False
            
        except Exception as e:
            frappe.log_error(f"ZKTeco Connection Error: {str(e)}", "ZKTeco Connector")
            frappe.logger().error(f"Failed to connect to {self.device_ip}: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the device"""
        try:
            if self.conn:
                self.conn.disconnect()
                frappe.logger().info(f"Disconnected from {self.device_ip}")
        except Exception as e:
            frappe.logger().warning(f"Error during disconnect: {str(e)}")
    
    def get_device_info(self):
        """
        Get device information
        
        Returns:
            dict: Device information including model, firmware, etc.
        """
        try:
            if not self.conn:
                return None
            
            info = {
                'serial_number': self.conn.get_serialnumber(),
                'firmware_version': self.conn.get_firmware_version(),
                'platform': self.conn.get_platform(),
                'device_name': self.conn.get_device_name(),
                'face_version': self.conn.get_face_version(),
                'fp_version': self.conn.get_fp_version(),
                'user_count': len(self.conn.get_users()),
                'attendance_count': len(self.conn.get_attendance())
            }
            
            return info
            
        except Exception as e:
            frappe.log_error(f"Error getting device info: {str(e)}", "ZKTeco Connector")
            return None
    
    def get_attendance_logs(self):
        """
        Fetch attendance logs from the device
        
        Returns:
            list: List of attendance records
        """
        try:
            if not self.conn:
                return []
            
            # Get attendance records from device
            attendances = self.conn.get_attendance()
            
            logs = []
            for att in attendances:
                logs.append({
                    'user_id': att.user_id,
                    'timestamp': att.timestamp,
                    'status': att.status,  # 0=Check-In, 1=Check-Out, 2=Break-Out, 3=Break-In, 4=OT-In, 5=OT-Out
                    'punch': att.punch,  # Punch type
                    'uid': att.uid  # Unique ID
                })
            
            frappe.logger().info(f"Retrieved {len(logs)} attendance records from {self.device_ip}")
            return logs
            
        except Exception as e:
            frappe.log_error(f"Error fetching logs: {str(e)}", "ZKTeco Connector")
            frappe.logger().error(f"Failed to fetch logs from {self.device_ip}: {str(e)}")
            return []
    
    def clear_attendance_logs(self):
        """Clear attendance logs from device after successful sync"""
        try:
            if self.conn:
                self.conn.clear_attendance()
                frappe.logger().info(f"Cleared attendance logs from {self.device_ip}")
                return True
        except Exception as e:
            frappe.log_error(f"Error clearing logs: {str(e)}", "ZKTeco Connector")
            return False
    
    def delete_user_from_device(self, user_id):
        """Delete a user from the device"""
        try:
            if self.conn:
                self.conn.delete_user(uid=user_id)
                frappe.logger().info(f"Deleted user {user_id} from device {self.device_ip}")
                return True
        except Exception as e:
            frappe.log_error(f"Error deleting user: {str(e)}", "ZKTeco Connector")
            return False
    
    @staticmethod
    def sync_device(device_ip, device_port=4370, clear_after_sync=False, auto_delete_inactive=False):
        """
        Sync attendance data from a ZKTeco device
        
        Args:
            device_ip: IP address of the device
            device_port: Port number
            clear_after_sync: Whether to clear device logs after successful sync
            auto_delete_inactive: Whether to automatically delete inactive employees from device
            
        Returns:
            dict: Sync results
        """
        connector = ZKTecoConnector(device_ip, device_port)
        
        if not connector.connect():
            return {
                'success': False,
                'message': f'Failed to connect to device at {device_ip}:{device_port}'
            }
        
        try:
            # Get device info for logging
            device_info = connector.get_device_info()
            if device_info:
                frappe.logger().info(
                    f"Device Info - Model: {device_info.get('platform')}, "
                    f"Firmware: {device_info.get('firmware_version')}, "
                    f"Users: {device_info.get('user_count')}, "
                    f"Records: {device_info.get('attendance_count')}"
                )
            
            # Get attendance logs
            logs = connector.get_attendance_logs()
            
            if not logs:
                return {
                    'success': True,
                    'message': 'No new attendance logs found',
                    'synced': 0,
                    'device_info': device_info
                }
            
            synced_count = 0
            errors = []
            BATCH_SIZE = 100  # Commit every 100 records
            
            for i, log in enumerate(logs):
                try:
                    # Map user_id to employee
                    employee = frappe.db.get_value(
                        'Employee',
                        {'attendance_device_id': str(log['user_id'])},
                        'name'
                    )
                    
                    if not employee:
                        errors.append(f"Employee not found for device ID: {log['user_id']}")
                        continue
                    
                    # Check employee status (NEW: Security Enhancement)
                    employee_doc = frappe.get_doc('Employee', employee)
                    
                    if employee_doc.status != 'Active':
                        # Employee is inactive (Left, Suspended, etc.)
                        error_msg = f"Rejected punch from inactive employee: {employee_doc.employee_name} (ID: {log['user_id']}, Status: {employee_doc.status})"
                        errors.append(error_msg)
                        frappe.logger().warning(error_msg)
                        
                        # Optionally delete user from device
                        if auto_delete_inactive:
                            try:
                                connector.delete_user_from_device(log['user_id'])
                                frappe.logger().info(f"Auto-deleted inactive user {log['user_id']} from device {device_ip}")
                            except Exception as e:
                                frappe.logger().error(f"Failed to auto-delete user {log['user_id']}: {str(e)}")
                        
                        continue
                    
                    # Determine log type based on status
                    # Status: 0=Check-In, 1=Check-Out, 2=Break-Out, 3=Break-In, 4=OT-In, 5=OT-Out
                    if log['status'] in [0, 3, 4]:  # Check-In, Break-In, OT-In
                        log_type = 'IN'
                    elif log['status'] in [1, 2, 5]:  # Check-Out, Break-Out, OT-Out
                        log_type = 'OUT'
                    else:
                        log_type = 'IN'  # Default to IN
                    
                    # Check if already exists
                    exists = frappe.db.exists(
                        'Employee Checkin',
                        {
                            'employee': employee,
                            'time': log['timestamp'],
                            'log_type': log_type
                        }
                    )
                    
                    if not exists:
                        # Create Employee Checkin
                        checkin = frappe.get_doc({
                            'doctype': 'Employee Checkin',
                            'employee': employee,
                            'time': log['timestamp'],
                            'log_type': log_type,
                            'device_id': device_ip
                        })
                        checkin.insert(ignore_permissions=True)
                        synced_count += 1
                    
                    # Batch commit every BATCH_SIZE records
                    if (i + 1) % BATCH_SIZE == 0:
                        frappe.db.commit()
                        frappe.logger().info(f"Batch committed: {i + 1} records processed")
                
                except Exception as e:
                    errors.append(f"Error processing log {i}: {str(e)}")
                    frappe.log_error(str(e), f"Sync Log Error - Device {device_ip}")
            
            # Final commit for remaining records
            frappe.db.commit()
            
            # Clear device logs if requested and sync was successful
            if clear_after_sync and synced_count > 0:
                connector.clear_attendance_logs()
            
            return {
                'success': True,
                'message': f'Synced {synced_count} attendance logs',
                'synced': synced_count,
                'total_logs': len(logs),
                'errors': errors if errors else None,
                'device_info': device_info
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Sync Error - Device {device_ip}")
            return {
                'success': False,
                'message': f'Error during sync: {str(e)}'
            }
        
        finally:
            connector.disconnect()


@frappe.whitelist()
def sync_biometric_device(device_ip, device_port=4370, clear_after_sync=False, auto_delete_inactive=False):
    """
    API method to sync a biometric device
    
    Args:
        device_ip: IP address of the device
        device_port: Port number (default 4370)
        clear_after_sync: Whether to clear device logs after sync
        auto_delete_inactive: Whether to automatically delete inactive employees from device
        
    Returns:
        dict: Sync results
    """
    return ZKTecoConnector.sync_device(device_ip, int(device_port), clear_after_sync, auto_delete_inactive)


@frappe.whitelist()
def sync_all_devices(clear_after_sync=False, auto_delete_inactive=False):
    """
    Sync all configured biometric devices
    
    Args:
        clear_after_sync: Whether to clear device logs after successful sync
        auto_delete_inactive: Whether to automatically delete inactive employees from device
    
    Returns:
        dict: Combined sync results
    """
    try:
        # Get all enabled devices
        devices = frappe.get_all(
            'Biometric Device Settings',
            filters={'enabled': 1},
            fields=['name', 'device_ip', 'device_port', 'auto_delete_inactive_users']
        )
        
        if not devices:
            return {
                'success': True,
                'message': 'No enabled devices found. Please configure and enable devices in Biometric Device Settings.',
                'devices_synced': 0
            }
        
        results = []
        total_synced = 0
        errors = []
        
        for device in devices:
            try:
                # Use device-specific setting if available, otherwise use parameter
                device_auto_delete = device.get('auto_delete_inactive_users', 0) or auto_delete_inactive
                
                result = ZKTecoConnector.sync_device(
                    device.device_ip, 
                    device.device_port,
                    clear_after_sync,
                    device_auto_delete
                )
                results.append({
                    'device': device.name,
                    'ip': device.device_ip,
                    'result': result
                })
                
                if result.get('success'):
                    total_synced += result.get('synced', 0)
                else:
                    errors.append(f"{device.name}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                error_msg = f"{device.name}: {str(e)}"
                errors.append(error_msg)
                frappe.log_error(frappe.get_traceback(), f"Sync failed for {device.name}")
        
        return {
            'success': True,
            'message': f'Synced {total_synced} records from {len(devices)} device(s)',
            'devices_synced': len(devices),
            'total_records': total_synced,
            'results': results,
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sync All Devices Failed")
        return {
            'success': False,
            'message': f'Error syncing devices: {str(e)}',
            'devices_synced': 0
        }


@frappe.whitelist()
def test_device_connection(device_ip, device_port=4370):
    """
    Test connection to ZKTeco device and get device info
    
    Args:
        device_ip: Device IP address
        device_port: Device port (default 4370)
        
    Returns:
        dict: Connection test result with device info
    """
    try:
        device_port = int(device_port)
        
        connector = ZKTecoConnector(device_ip, device_port, timeout=5)
        
        if not connector.connect():
            return {
                'success': False,
                'error': f'Unable to connect to device at {device_ip}:{device_port}. Please check network and device status.'
            }
        
        try:
            # Get device information
            device_info = connector.get_device_info()
            
            if device_info:
                message = (
                    f"Successfully connected to device at {device_ip}:{device_port}\n\n"
                    f"Device Information:\n"
                    f"- Model: {device_info.get('platform', 'Unknown')}\n"
                    f"- Firmware: {device_info.get('firmware_version', 'Unknown')}\n"
                    f"- Serial: {device_info.get('serial_number', 'Unknown')}\n"
                    f"- Users: {device_info.get('user_count', 0)}\n"
                    f"- Attendance Records: {device_info.get('attendance_count', 0)}"
                )
            else:
                message = f"Successfully connected to device at {device_ip}:{device_port}"
            
            return {
                'success': True,
                'message': message,
                'device_info': device_info
            }
            
        finally:
            connector.disconnect()
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f'Connection Test Error - {device_ip}:{device_port}')
        return {
            'success': False,
            'error': f'Connection error: {str(e)}'
        }


@frappe.whitelist()
def get_device_info(device_ip, device_port=4370):
    """
    Get detailed device information
    
    Args:
        device_ip: Device IP address
        device_port: Device port
        
    Returns:
        dict: Device information
    """
    try:
        device_port = int(device_port)
        
        connector = ZKTecoConnector(device_ip, device_port)
        
        if not connector.connect():
            return {
                'success': False,
                'error': 'Failed to connect to device'
            }
        
        try:
            device_info = connector.get_device_info()
            
            return {
                'success': True,
                'device_info': device_info
            }
            
        finally:
            connector.disconnect()
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f'Get Device Info Error - {device_ip}')
        return {
            'success': False,
            'error': str(e)
        }
