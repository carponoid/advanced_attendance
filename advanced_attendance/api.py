import frappe
from frappe.utils import now_datetime
from .utils import get_effective_work_site, compute_geofence_flag, hash_fingerprint

@frappe.whitelist()
def get_employee_for_user():
    """
    Return employee linked to current user, or None.
    """
    user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name"], as_dict=True)
    return emp


@frappe.whitelist(methods=["POST"])
def mobile_checkin(direction, lat, lng, accuracy=None, fingerprint_raw=None):
    """
    Mobile clock-in/out endpoint.
    - Requires logged-in user.
    - Requires GPS coordinates.
    """
    if direction not in ("IN", "OUT"):
        frappe.throw("Invalid direction")

    user = frappe.session.user
    if user in ("Guest", None):
        frappe.throw("You must be logged in to clock in/out")

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        frappe.throw("No Employee linked to this user")

    try:
        lat = float(lat)
        lng = float(lng)
    except Exception:
        frappe.throw("Invalid latitude/longitude")

    work_site = get_effective_work_site(employee)
    within_geofence = compute_geofence_flag(work_site, lat, lng)

    # Parse fingerprint_raw from JSON string if needed
    import json
    try:
        raw_obj = json.loads(fingerprint_raw) if isinstance(fingerprint_raw, str) else (fingerprint_raw or {})
    except Exception:
        raw_obj = {}

    fingerprint = hash_fingerprint(raw_obj, frappe.local.request)

    doc = frappe.get_doc({
        "doctype": "Mobile Checkin",
        "employee": employee,
        "time": now_datetime(),
        "direction": direction,
        "latitude": lat,
        "longitude": lng,
        "gps_accuracy": float(accuracy) if accuracy else None,
        "work_site": work_site,
        "within_geofence": 1 if within_geofence else 0,
        "device_fingerprint": fingerprint,
        "ip_address": getattr(frappe.local, "request_ip", None),
        "user_agent": frappe.local.request.headers.get("User-Agent") if getattr(frappe.local, "request", None) else "",
        "owner_user": user,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "within_geofence": within_geofence}
