# Advanced Attendance App for ERPNext

Advanced multi-source attendance and roster system with geofencing, mobile clock-in, and biometric integration.

## Features

- **Multi-Source Attendance**: Combines biometric device punches and mobile clock-ins
- **Geofencing**: GPS-based validation of clock-in locations
- **Work Sites**: Define physical work locations with geofence radius
- **Tour Plans**: Temporary work site assignments for employees
- **Mobile Clock-In**: Browser-based mobile interface (no app required)
- **Device Fingerprinting**: Fraud detection through device identification
- **Automated Processing**: Hourly attendance processing with shift logic
- **Anomaly Detection**: Daily reports on suspicious patterns
- **Audit Trail**: Complete logging of all attendance processing

## Installation

### On ERPNext Bench

```bash
# Get the app from GitHub
bench get-app https://github.com/wincoadmin/advanced_attendance.git

# Install on your site
bench --site your-site-name install-app advanced_attendance

# Restart bench
bench restart
```

### Important: Site-Specific Installation

This app should be installed **only on the specific site** where you want attendance management to run. Do not install it on multiple sites on the same bench unless you have separate attendance systems.

## Configuration

### 1. Create DocTypes

The following DocTypes need to be created via Desk (Developer Mode ON):

#### Work Site
- Module: Advanced Attendance
- Fields: site_name, company, latitude, longitude, radius, is_active, description

#### Tour Plan
- Module: Advanced Attendance
- Fields: employee, work_site, from_date, to_date, status, company, remarks

#### Mobile Checkin
- Module: Advanced Attendance
- Fields: employee, time, direction, latitude, longitude, gps_accuracy, within_geofence, work_site, device_fingerprint, fingerprint_risk, ip_address, user_agent, owner_user, notes, processed, processing_batch

#### Attendance Processor Log
- Module: Advanced Attendance
- Fields: run_time, from_time, to_time, status, total, errors

### 2. Add Custom Fields

Use **Customize Form** to add these fields:

**Employee**
- `default_work_site` (Link → Work Site)
- `default_shift_type` (Link → Shift Type)

**Employee Checkin**
- `aa_processed` (Check, default 0)

**Attendance** (optional but recommended)
- `has_outside_geofence_checkin` (Check)
- `device_fingerprint_anomaly` (Check)

### 3. Configure Work Sites

1. Go to **Work Site** list
2. Create work sites with GPS coordinates and radius
3. Assign default work sites to employees

### 4. Configure Shifts

1. Ensure **Shift Type** is configured in ERPNext
2. Assign default shifts to employees

## Usage

### Mobile Clock-In

Employees can access the clock-in page at:
```
https://your-site.com/clock-in
```

Requirements:
- Employee must be logged in
- Employee must have a linked User account
- GPS must be enabled on the device
- HTTPS connection required for GPS API

### Biometric Integration

For ZKTeco devices (MB160 Plus, etc.):
- Use a separate connector app that writes to `Employee Checkin`
- The connector should map device user IDs to ERPNext employees
- See ZKTeco connector specification document for details

### Attendance Processing

Attendance is processed automatically:
- **Hourly**: Processes punches from last 2 days
- **Daily**: Generates anomaly summary

Manual processing:
```bash
bench execute advanced_attendance.tasks.process_attendance_punches
```

## Scheduler Jobs

The app runs three scheduled jobs:

1. **Biometric Sync** (every 5 minutes): Placeholder for device connector
2. **Attendance Processing** (hourly): Processes punches and creates attendance
3. **Anomaly Summary** (daily): Summarizes suspicious patterns

## Architecture

### Data Flow

```
Biometric Devices → Employee Checkin ┐
                                     ├→ Attendance Processing Engine → Attendance
Mobile Clock-In → Mobile Checkin    ┘
```

### Key Components

- **utils.py**: Core logic (geofencing, processing engine, anomaly detection)
- **api.py**: Public API methods for mobile clock-in
- **tasks.py**: Scheduled jobs
- **www/clock_in.html**: Mobile clock-in interface

## Security

- Geofence validation prevents remote clock-ins
- Device fingerprinting detects shared devices
- GPS accuracy tracking flags weak location data
- IP address and User Agent logging for forensics
- Role-based permissions ensure data integrity

## Permissions

### Roles

- **Employee**: Can clock in/out via mobile (own records only)
- **HR Manager**: Full access to all attendance data
- **Attendance Admin**: (Optional) Dedicated attendance management role

### Permission Rules

- Mobile Checkin: Employees can create and read own records only
- Work Site / Tour Plan: HR Manager can create, read, write
- Attendance: HR Manager can read and write (for corrections)

## Troubleshooting

### Clock-in not working

1. Check if employee has linked User account
2. Verify GPS is enabled on device
3. Ensure HTTPS connection (GPS API requirement)
4. Check if default_work_site is configured

### Attendance not being created

1. Check if employee has default_shift_type configured
2. Verify punches exist in Employee Checkin or Mobile Checkin
3. Check Attendance Processor Log for errors
4. Ensure aa_processed custom field exists on Employee Checkin

### Geofence validation failing

1. Verify Work Site has correct GPS coordinates
2. Check radius is appropriate (meters)
3. Test GPS accuracy on device (should be < 100m)

## Development

### Running Tests

```bash
bench --site your-site-name run-tests --app advanced_attendance
```

### Debugging

Enable developer mode and check:
- Error Log (Desk → Error Log)
- Attendance Processor Log (for processing errors)
- frappe.log for scheduler job output

## Updates

To update the app after changes:

```bash
cd apps/advanced_attendance
git pull origin main
cd ../../
bench --site your-site-name migrate
bench restart
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/wincoadmin/advanced_attendance/issues
- Documentation: See included specification documents

## License

MIT License

## Credits

Developed by Winco Group for ERPNext/Frappe Framework
