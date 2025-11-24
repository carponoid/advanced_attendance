# Copyright (c) 2025, Wins O. Win Nig Ltd and contributors
# For license information, please see license.txt

"""
ZKTeco Biometric Device Connector
Syncs attendance data from ZKTeco devices to ERPNext
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime
import socket
import struct


class ZKTecoConnector:
    """
    ZKTeco Device Connector
    Connects to ZKTeco biometric devices and syncs attendance data
    """
    
    def __init__(self, device_ip, device_port=4370, timeout=10):
        """
        Initialize connector
        
        Args:
            device_ip: IP address of the ZKTeco device
            device_port: Port number (default 4370)
            timeout: Connection timeout in seconds
        """
        self.device_ip = device_ip
        self.device_port = device_port
        self.timeout = timeout
        self.socket = None
        self.session_id = 0
        self.reply_id = 0
    
    def connect(self):
        """Connect to the ZKTeco device"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(self.timeout)
            
            # Send connect command
            command = self._create_header(1000, 0)
            self.socket.sendto(command, (self.device_ip, self.device_port))
            
            # Receive response
            data, addr = self.socket.recvfrom(1024)
            
            if len(data) >= 8:
                self.session_id = struct.unpack('H', data[4:6])[0]
                self.reply_id = struct.unpack('H', data[6:8])[0]
                return True
            
            return False
            
        except Exception as e:
            frappe.log_error(f"ZKTeco Connection Error: {str(e)}", "ZKTeco Connector")
            return False
    
    def disconnect(self):
        """Disconnect from the device"""
        try:
            if self.socket:
                command = self._create_header(1002, 0)
                self.socket.sendto(command, (self.device_ip, self.device_port))
                self.socket.close()
                self.socket = None
        except:
            pass
    
    def get_attendance_logs(self):
        """
        Fetch attendance logs from the device
        
        Returns:
            list: List of attendance records
        """
        try:
            # Send command to read attendance logs
            command = self._create_header(13, 0)
            self.socket.sendto(command, (self.device_ip, self.device_port))
            
            # Receive response
            data, addr = self.socket.recvfrom(65535)
            
            if len(data) < 8:
                return []
            
            # Parse attendance logs
            logs = []
            offset = 8  # Skip header
            
            while offset < len(data):
                if offset + 40 > len(data):
                    break
                
                # Parse log entry (simplified)
                user_id = struct.unpack('I', data[offset:offset+4])[0]
                timestamp = struct.unpack('I', data[offset+4:offset+8])[0]
                verify_type = data[offset+8]
                in_out_type = data[offset+9]
                
                logs.append({
                    'user_id': user_id,
                    'timestamp': timestamp,
                    'verify_type': verify_type,
                    'in_out_type': in_out_type
                })
                
                offset += 40
            
            return logs
            
        except Exception as e:
            frappe.log_error(f"Error fetching logs: {str(e)}", "ZKTeco Connector")
            return []
    
    def _create_header(self, command, data_len):
        """Create command header"""
        buf = struct.pack('HHHH', command, 0, self.session_id, self.reply_id)
        buf += struct.pack('H', data_len)
        return buf
    
    @staticmethod
    def sync_device(device_ip, device_port=4370):
        """
        Sync attendance data from a ZKTeco device
        
        Args:
            device_ip: IP address of the device
            device_port: Port number
            
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
            logs = connector.get_attendance_logs()
            
            if not logs:
                return {
                    'success': True,
                    'message': 'No new attendance logs found',
                    'synced': 0
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
                    
                    # Convert timestamp to datetime
                    from datetime import datetime
                    punch_time = datetime.fromtimestamp(log['timestamp'])
                    
                    # Determine log type (IN/OUT)
                    log_type = 'IN' if log['in_out_type'] == 0 else 'OUT'
                    
                    # Check if already exists
                    exists = frappe.db.exists(
                        'Employee Checkin',
                        {
                            'employee': employee,
                            'time': punch_time,
                            'log_type': log_type
                        }
                    )
                    
                    if not exists:
                        # Create Employee Checkin
                        checkin = frappe.get_doc({
                            'doctype': 'Employee Checkin',
                            'employee': employee,
                            'time': punch_time,
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
            
            return {
                'success': True,
                'message': f'Synced {synced_count} attendance logs',
                'synced': synced_count,
                'errors': errors if errors else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error during sync: {str(e)}'
            }
        
        finally:
            connector.disconnect()


@frappe.whitelist()
def sync_biometric_device(device_ip, device_port=4370):
    """
    API method to sync a biometric device
    
    Args:
        device_ip: IP address of the device
        device_port: Port number (default 4370)
        
    Returns:
        dict: Sync results
    """
    return ZKTecoConnector.sync_device(device_ip, int(device_port))


@frappe.whitelist()
def sync_all_devices():
    """
    Sync all configured biometric devices
    
    Returns:
        dict: Combined sync results
    """
    try:
        # Get all enabled devices
        devices = frappe.get_all(
            'Biometric Device Settings',
            filters={'enabled': 1},
            fields=['name', 'device_ip', 'device_port']
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
                result = ZKTecoConnector.sync_device(device.device_ip, device.device_port)
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
    Test connection to ZKTeco device
    
    Args:
        device_ip: Device IP address
        device_port: Device port (default 4370)
        
    Returns:
        dict: Connection test result
    """
    import socket
    
    try:
        device_port = int(device_port)
        
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        
        # Try to connect
        result = sock.connect_ex((device_ip, device_port))
        sock.close()
        
        if result == 0:
            frappe.log_error(f'Connection test successful: {device_ip}:{device_port}', 'ZKTeco Connection Test')
            return {
                'success': True,
                'message': f'Successfully connected to device at {device_ip}:{device_port}'
            }
        else:
            frappe.log_error(f'Connection test failed: {device_ip}:{device_port} - Error code: {result}', 'ZKTeco Connection Test')
            return {
                'success': False,
                'error': f'Unable to connect to device. Error code: {result}. Please check network and device status.'
            }
            
    except socket.timeout:
        frappe.log_error(f'Connection timeout: {device_ip}:{device_port}', 'ZKTeco Connection Test')
        return {
            'success': False,
            'error': 'Connection timeout. Device may be offline or unreachable.'
        }
    except Exception as e:
        frappe.log_error(f'Connection error: {device_ip}:{device_port} - {str(e)}', 'ZKTeco Connection Test')
        return {
            'success': False,
            'error': f'Connection error: {str(e)}'
        }
