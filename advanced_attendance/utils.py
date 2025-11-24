import frappe
import math
import json
from datetime import datetime, timedelta
from frappe.utils import getdate, now_datetime

# -----------------------------
# Work Site & Geofence Helpers
# -----------------------------

def get_effective_work_site(employee: str) -> str | None:
    """
    Resolve effective Work Site for an employee:
    1) Active Tour Plan for today
    2) Employee.default_work_site
    """
    today = getdate()

    tour_plan = frappe.db.get_value(
        "Tour Plan",
        {
            "employee": employee,
            "status": "Active",
            "from_date": ["<=", today],
            "to_date": [">=", today],
        },
        "work_site"
    )
    if tour_plan:
        return tour_plan

    default_work_site = frappe.db.get_value("Employee", employee, "default_work_site")
    return default_work_site


def compute_geofence_flag(work_site_name: str | None, lat: float, lng: float) -> bool:
    """
    Return True if (lat, lng) is within the Work Site radius, False otherwise.
    If no Work Site is configured, return False (or decide your own business rule).
    """
    if not work_site_name:
        return False

    ws = frappe.db.get_value(
        "Work Site",
        work_site_name,
        ["latitude", "longitude", "radius"],
        as_dict=True
    )
    if not ws or not ws.latitude or not ws.longitude or not ws.radius:
        return False

    distance_m = haversine_distance_meters(float(ws.latitude), float(ws.longitude), lat, lng)
    return distance_m <= float(ws.radius)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance (in meters) between two GPS coordinates.
    """
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# -----------------------------
# Device Fingerprint
# -----------------------------

def hash_fingerprint(fingerprint_raw, request) -> str:
    """
    Produce a stable string hash for device fingerprint.

    - fingerprint_raw: JSON-able object from client (may be None)
    - request: frappe.local.request

    This is for anomaly detection only (reporting), not for blocking.
    """
    try:
        ua = request.headers.get("User-Agent", "") if request else ""
    except Exception:
        ua = ""

    ip = getattr(frappe.local, "request_ip", "") or ""
    data = {
        "ua": ua,
        "ip": ip,
        "raw": fingerprint_raw or {},
    }
    serialized = json.dumps(data, sort_keys=True)
    # Simple hash using sha1 for stability (not security-critical)
    import hashlib
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


# -----------------------------
# Attendance Processing Engine
# -----------------------------

def process_attendance_window(from_date, to_date):
    """
    Process attendance for all employees between from_date and to_date.

    from_date, to_date: date objects or strings (YYYY-MM-DD).
    """
    from_date = getdate(from_date)
    to_date = getdate(to_date)

    # Create a Processor Log record
    log = frappe.get_doc({
        "doctype": "Attendance Processor Log",
        "run_time": now_datetime(),
        "from_time": from_date,
        "to_time": to_date,
        "status": "Partial",
        "total": 0,
    })
    log.insert(ignore_permissions=True)

    total_processed = 0
    errors = []

    try:
        # Get all employees that have punches in the window
        employees = get_employees_with_punches(from_date, to_date)

        for emp in employees:
            try:
                for day in daterange(from_date, to_date):
                    processed = process_employee_day(emp, day, log.name)
                    total_processed += processed
            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Attendance processing error for employee {emp}"
                )
                errors.append(f"{emp}: {str(e)}")

        log.status = "Success" if not errors else "Partial"
    except Exception as e:
        log.status = "Failed"
        errors.append(str(e))
        frappe.log_error(frappe.get_traceback(), "Attendance processing window failed")
    finally:
        log.total = total_processed
        log.errors = "\n".join(errors)
        log.save(ignore_permissions=True)
        frappe.db.commit()


def get_employees_with_punches(from_date, to_date):
    """
    Return list of employee IDs that have punches between dates in either
    Employee Checkin or Mobile Checkin.
    """
    emp1 = frappe.db.sql_list(
        """
        SELECT DISTINCT employee
        FROM `tabEmployee Checkin`
        WHERE time BETWEEN %s AND %s
        """,
        (from_date, add_one_day(to_date))
    )
    emp2 = frappe.db.sql_list(
        """
        SELECT DISTINCT employee
        FROM `tabMobile Checkin`
        WHERE time BETWEEN %s AND %s
        """,
        (from_date, add_one_day(to_date))
    )
    return list(set(emp1 + emp2))


def add_one_day(d):
    return getdate(d) + timedelta(days=1)


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)


def process_employee_day(employee, date, processor_log_name) -> int:
    """
    Process attendance for a single employee on a single date.
    Returns number of Attendance docs created/updated (0 or 1).
    """
    # Get punches for that date
    start_dt = datetime.combine(getdate(date), datetime.min.time())
    end_dt = datetime.combine(getdate(date), datetime.max.time())

    punches = []

    # Employee Checkin (biometric / manual)
    for row in frappe.db.get_all(
        "Employee Checkin",
        filters={
            "employee": employee,
            "time": ["between", [start_dt, end_dt]],
            "aa_processed": ["!=", 1]  # custom field (Check) you must add via Customize Form
        },
        fields=["name", "time", "log_type as direction"]
    ):
        punches.append({
            "source": "Employee Checkin",
            "name": row.name,
            "time": row.time,
            "direction": row.direction,
            "within_geofence": None,
            "device_fingerprint": None,
        })

    # Mobile Checkin
    for row in frappe.db.get_all(
        "Mobile Checkin",
        filters={
            "employee": employee,
            "time": ["between", [start_dt, end_dt]],
            "processed": ["!=", 1]
        },
        fields=["name", "time", "direction", "within_geofence", "device_fingerprint"]
    ):
        punches.append({
            "source": "Mobile Checkin",
            "name": row.name,
            "time": row.time,
            "direction": row.direction,
            "within_geofence": row.within_geofence,
            "device_fingerprint": row.device_fingerprint,
        })

    if not punches:
        return 0

    # Sort by time
    punches.sort(key=lambda x: x["time"])

    # De-duplicate: drop subsequent punches within X seconds with same direction
    deduped = deduplicate_punches(punches, threshold_seconds=60)

    # Get shift type (simple assumption: use default_shift_type on Employee)
    shift_type = frappe.db.get_value("Employee", employee, "default_shift_type")
    if not shift_type:
        # Optionally skip employee if no shift_type assigned
        return 0

    shift_doc = frappe.get_doc("Shift Type", shift_type)
    in_time, out_time = classify_in_out(deduped, shift_doc)

    if not in_time and not out_time:
        # Nothing meaningful to create attendance
        mark_punches_processed(deduped, processor_log_name)
        return 0

    # Create or update Attendance
    att_name = frappe.db.get_value("Attendance", {
        "employee": employee,
        "attendance_date": date
    }, "name")

    if att_name:
        att = frappe.get_doc("Attendance", att_name)
    else:
        att = frappe.get_doc({
            "doctype": "Attendance",
            "employee": employee,
            "attendance_date": date,
        })

    # Basic status logic (can be extended)
    att.status = "Present"

    # Late / early (very simplified example)
    # Convert timedelta to time for comparison
    if in_time and hasattr(shift_doc, "start_time") and shift_doc.start_time:
        shift_start = (datetime.min + shift_doc.start_time).time()
        if in_time.time() > shift_start:
            att.late_entry = 1
    if out_time and hasattr(shift_doc, "end_time") and shift_doc.end_time:
        shift_end = (datetime.min + shift_doc.end_time).time()
        if out_time.time() < shift_end:
            att.early_exit = 1

    # Custom fields on Attendance to store flags (create via Customize Form)
    # Example custom fields:
    # - has_outside_geofence_checkin (Check)
    # - device_fingerprint_anomaly (Check)

    has_outside_geofence = any(
        p["source"] == "Mobile Checkin" and p["within_geofence"] == 0 for p in deduped
    )
    if hasattr(att, "has_outside_geofence_checkin"):
        att.has_outside_geofence_checkin = 1 if has_outside_geofence else 0

    # Save Attendance
    att.flags.ignore_permissions = True
    att.save()

    # Mark punches processed
    mark_punches_processed(deduped, processor_log_name)

    return 1


def deduplicate_punches(punches, threshold_seconds=60):
    """
    Remove subsequent punches if they have same direction and are within threshold_seconds.
    """
    if not punches:
        return []

    deduped = [punches[0]]
    for p in punches[1:]:
        last = deduped[-1]
        if (
            p["direction"] == last["direction"]
            and abs((p["time"] - last["time"]).total_seconds()) <= threshold_seconds
        ):
            # skip duplicate
            continue
        deduped.append(p)
    return deduped


def classify_in_out(punches, shift_doc):
    """
    Simplified classification: first IN as in_time, last OUT as out_time.
    You can refine this with shift windows if needed.
    """
    in_time = None
    out_time = None

    for p in punches:
        if p["direction"] in ("IN", "IN PUNCH"):
            if not in_time or p["time"] < in_time:
                in_time = p["time"]
        elif p["direction"] in ("OUT", "OUT PUNCH"):
            if not out_time or p["time"] > out_time:
                out_time = p["time"]

    return in_time, out_time


def mark_punches_processed(punches, processor_log_name):
    """
    Set processed flags on Mobile Checkin and aa_processed on Employee Checkin.
    """
    for p in punches:
        if p["source"] == "Mobile Checkin":
            frappe.db.set_value("Mobile Checkin", p["name"], {
                "processed": 1,
                "processing_batch": processor_log_name
            })
        elif p["source"] == "Employee Checkin":
            frappe.db.set_value("Employee Checkin", p["name"], {
                "aa_processed": 1
            })
    frappe.db.commit()


# -----------------------------
# Anomaly Summary (Daily)
# -----------------------------

def summarize_anomalies_for_date(target_date):
    """
    Stub for daily anomaly summary.
    Extend as needed (e.g., email HR with outside-geofence stats, etc.).
    """
    # Example: count outside-geofence checkins on that date
    start_dt = datetime.combine(getdate(target_date), datetime.min.time())
    end_dt = datetime.combine(getdate(target_date), datetime.max.time())

    count_outside = frappe.db.count(
        "Mobile Checkin",
        filters={
            "time": ["between", [start_dt, end_dt]],
            "within_geofence": 0
        }
    )

    frappe.logger().info(
        f"advanced_attendance.summarize_anomalies_for_date: {target_date} outside_geofence={count_outside}"
    )

    # You can send email from here if desired.
