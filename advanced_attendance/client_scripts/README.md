# Client Scripts

This directory contains client-side JavaScript code that runs in the browser for custom form behaviors.

## Biometric Device Settings

**File:** `biometric_device_settings.js`

**Purpose:** Adds a "Test Connection" button to the Biometric Device Settings form that allows users to test connectivity to ZKTeco biometric devices before saving the configuration.

**Installation:**

This client script is stored in the database as a Client Script document. To install or update:

1. Go to: **Desk → Customization → Client Script**
2. Create/Edit: **Biometric Device Settings Buttons**
3. Set the following fields:
   - **DocType:** Biometric Device Settings
   - **Apply To:** Form
   - **Enabled:** ✓ (checked)
   - **Script:** Copy the contents of `biometric_device_settings.js`

**Features:**

- Adds a "Test Connection" button in the Actions dropdown
- Validates that Device IP and Device Port are set before testing
- Calls the backend API `advanced_attendance.zkteco_connector.test_device_connection`
- Shows success/failure alerts with appropriate colors
- Displays a loading indicator during the connection test

**Backend API:**

The button calls the whitelisted method:
```python
@frappe.whitelist()
def test_device_connection(device_ip, device_port):
    # Located in: advanced_attendance/zkteco_connector.py
```

**Testing:**

1. Open any Biometric Device Settings document
2. Click **Actions → Test Connection**
3. The system will attempt to connect to the device and show the result

**Error Handling:**

- If device is offline: Shows "Connection failed: Unable to connect to device. Error code: 11"
- If fields are empty: Shows "Please set Device IP Address and Device Port before testing"
- If connection succeeds: Shows "Successfully connected to device" with green indicator
