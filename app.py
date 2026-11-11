import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functools import wraps
from flask import Flask, request, jsonify, render_template, session, Response
from flask_cors import CORS
from config import Config
from database.db import execute_query, is_azure_sql
from database.init_db import init_database, seed_sample_data
from services.auth_service import AuthService
from services.parcel_service import ParcelService
from services.storage_service import StorageService
from services.notification_service import NotificationService
from services.analytics_service import AnalyticsService

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# RBAC Security Middleware & Decorators
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                return jsonify({"error": "Unauthorized. Please log in."}), 401
            current_role = session["user"].get("role")
            if current_role not in allowed_roles and "admin" not in allowed_roles:
                return jsonify({"error": f"Forbidden. Role '{current_role}' lacks access permission."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------------------------------------------------------
# Frontend Views
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serves the ParcelDesk single-page web portal."""
    return render_template("index.html")

# ---------------------------------------------------------------------------
# Authentication API (Cloud Security)
# ---------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    """
    Authenticates user, verifies password hash, and starts role-based session.
    """
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_data = AuthService.authenticate(username, password, ip_address=ip_address)

    if not user_data:
        return jsonify({"error": "Invalid username or password."}), 401

    session["user"] = user_data
    return jsonify({
        "message": "Login successful.",
        "user": user_data
    }), 200

@app.route("/api/logout", methods=["POST"])
def logout():
    """Clears user session."""
    user = session.pop("user", None)
    if user:
        AuthService.log_audit(user.get("id"), "LOGOUT", "User logged out")
    return jsonify({"message": "Successfully logged out."}), 200

@app.route("/api/me", methods=["GET"])
def get_current_user():
    """Returns currently authenticated user profile."""
    if "user" not in session:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": session["user"]}), 200

# ---------------------------------------------------------------------------
# Parcel Management Endpoints (System Design Core API)
# ---------------------------------------------------------------------------
@app.route("/api/parcels", methods=["GET"])
@login_required
def get_parcels():
    """
    Retrieves parcel records.
    Students see only their own deliveries.
    Guards and wardens see all or filtered parcels.
    """
    current_user = session["user"]
    role = current_user["role"]

    if role == "student":
        student_id = current_user["student_profile"]["student_id"]
        parcels = ParcelService.get_student_parcels(student_id)
    else:
        status_filter = request.args.get("status")
        hostel_id = request.args.get("hostel_id")
        parcels = ParcelService.get_all_parcels(status_filter=status_filter, hostel_id=hostel_id)

    return jsonify({"parcels": parcels}), 200

@app.route("/api/parcels/pending", methods=["GET"])
@login_required
@roles_required("guard", "warden", "admin")
def get_pending_parcels():
    """Queries the RDBMS view vw_pending_parcels."""
    pending = ParcelService.get_pending_parcels()
    return jsonify({"pending_parcels": pending}), 200

@app.route("/api/parcels", methods=["POST"])
@login_required
@roles_required("guard", "admin")
def log_parcel():
    """
    Gate staff logs incoming parcel with student, courier, date, and photo.
    Generates single-use hashed OTP and issues semi-structured notification.
    """
    # Handle both multipart/form-data (photo upload) and json
    if request.is_json:
        data = request.get_json()
        photo_url = data.get("photo_url")
    else:
        data = request.form
        photo_file = request.files.get("photo")
        photo_url = None
        if photo_file:
            try:
                photo_url = StorageService.save_parcel_photo(photo_file)
            except Exception as e:
                return jsonify({"error": f"Photo upload failed: {str(e)}"}), 400

    tracking_number = data.get("tracking_number", "").strip()
    courier_name = data.get("courier_name", "").strip()
    student_id = data.get("student_id")
    hostel_id = data.get("hostel_id")
    remarks = data.get("remarks", "").strip()

    if not tracking_number or not courier_name or not student_id or not hostel_id:
        return jsonify({"error": "Tracking number, courier, student, and hostel are required."}), 400

    try:
        student_id = int(student_id)
        hostel_id = int(hostel_id)
    except ValueError:
        return jsonify({"error": "Invalid student or hostel ID."}), 400

    guard_id = session["user"]["id"]
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        result = ParcelService.log_parcel(
            tracking_number=tracking_number,
            courier_name=courier_name,
            student_id=student_id,
            hostel_id=hostel_id,
            logged_by_guard_id=guard_id,
            photo_url=photo_url,
            remarks=remarks,
            ip_address=ip_address
        )
        return jsonify({
            "message": "Parcel successfully logged at gate and notification dispatched.",
            "parcel": result
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/parcels/<int:parcel_id>/notify", methods=["POST"])
@login_required
@roles_required("guard", "warden", "admin")
def resend_notification(parcel_id):
    """
    Re-triggers notification delivery for an uncollected parcel.
    Stores semi-structured JSON payload in notifications table.
    """
    parcel = execute_query(
        """
        SELECT p.id, p.tracking_number, p.courier_name, p.student_id, p.hostel_id,
               s.room_no, s.phone, u.full_name, u.email, h.name AS hostel_name
        FROM parcels p
        JOIN students s ON p.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN hostels h ON p.hostel_id = h.id
        WHERE p.id = ?;
        """,
        (parcel_id,),
        fetch_one=True
    )

    if not parcel:
        return jsonify({"error": "Parcel not found."}), 404

    notif = NotificationService.create_and_send_notification(
        parcel_id=parcel["id"],
        student_id=parcel["student_id"],
        courier_name=parcel["courier_name"],
        tracking_number=parcel["tracking_number"],
        student_name=parcel["full_name"],
        student_email=parcel["email"],
        student_phone=parcel["phone"],
        room_no=parcel["room_no"],
        hostel_name=parcel["hostel_name"]
    )

    return jsonify({"message": "Notification dispatched successfully.", "notification": notif}), 200

@app.route("/api/parcels/<int:parcel_id>/handover", methods=["POST"])
@login_required
@roles_required("guard", "admin")
def handover_parcel(parcel_id):
    """
    ACID Transactional Handover:
    Verifies student's single-use OTP against cryptographic hash,
    transitions parcel status to 'collected', and creates handover ledger record.
    """
    data = request.get_json(silent=True) or request.form
    otp = data.get("otp", "").strip()
    notes = data.get("notes", "").strip()

    if not otp:
        return jsonify({"error": "6-digit OTP code is required for handover verification."}), 400

    guard_id = session["user"]["id"]
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        result = ParcelService.handover_parcel(
            parcel_id=parcel_id,
            submitted_otp=otp,
            guard_user_id=guard_id,
            notes=notes,
            ip_address=ip_address
        )
        return jsonify({
            "message": "OTP verified successfully. Parcel marked as collected and handover logged.",
            "handover": result
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Handover failed: {str(e)}"}), 500

@app.route("/api/parcels/<int:parcel_id>/regenerate-otp", methods=["POST"])
@login_required
def regenerate_otp(parcel_id):
    """
    Regenerates a fresh 6-digit OTP with a new 15-minute TTL.
    Only permitted for the parcel recipient student.
    """
    current_user = session["user"]
    if current_user["role"] != "student":
        return jsonify({"error": "Only the student receiving the parcel may request an OTP."}), 403

    student_id = current_user["student_profile"]["student_id"]

    try:
        result = ParcelService.regenerate_otp_for_student(parcel_id, student_id)
        return jsonify({
            "message": "New secure OTP generated.",
            "otp_data": result
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------------------------------------------------------------------
# Metadata, Students & Hostels Endpoints (Lookup for Forms)
# ---------------------------------------------------------------------------
@app.route("/api/students", methods=["GET"])
@login_required
def list_students():
    """Lists students for search and dropdown selection."""
    students = execute_query(
        """
        SELECT s.id AS student_id, s.student_roll_no, s.room_no, s.phone,
               u.full_name AS student_name, u.email,
               h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
        FROM students s
        JOIN users u ON s.user_id = u.id
        JOIN hostels h ON s.hostel_id = h.id
        ORDER BY u.full_name ASC;
        """,
        fetch_all=True
    )
    return jsonify({"students": students}), 200

@app.route("/api/hostels", methods=["GET"])
def list_hostels():
    """Lists registered hostel blocks."""
    hostels = execute_query("SELECT id, name, code FROM hostels ORDER BY name ASC;", fetch_all=True)
    return jsonify({"hostels": hostels}), 200

@app.route("/api/notifications", methods=["GET"])
@login_required
def get_notifications():
    """Returns semi-structured notifications for student."""
    current_user = session["user"]
    if current_user["role"] != "student":
        return jsonify({"notifications": []}), 200

    student_id = current_user["student_profile"]["student_id"]
    notifs = NotificationService.get_notifications_for_student(student_id)
    return jsonify({"notifications": notifs}), 200

# ---------------------------------------------------------------------------
# Analytics & Power BI Endpoints (DP-900 Data Services)
# ---------------------------------------------------------------------------
@app.route("/api/analytics/summary", methods=["GET"])
@login_required
@roles_required("warden", "admin", "guard")
def get_analytics_summary():
    """Returns headline KPIs, pickup turnaround times, and pending counts per hostel."""
    summary = AnalyticsService.get_summary_metrics()
    daily_vol = AnalyticsService.get_daily_volume()
    avg_pickup = AnalyticsService.get_avg_pickup_by_hostel()
    return jsonify({
        "summary": summary,
        "daily_volume": daily_vol,
        "avg_pickup_by_hostel": avg_pickup
    }), 200

@app.route("/api/analytics/powerbi-export", methods=["GET"])
@login_required
@roles_required("warden", "admin")
def export_powerbi():
    """Exports structured & semi-structured dataset for Power BI report ingestion."""
    csv_data = AnalyticsService.export_powerbi_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=parceldesk_powerbi_dataset.csv"}
    )

@app.route("/api/audit-logs", methods=["GET"])
@login_required
@roles_required("warden", "admin")
def get_audit_logs():
    """Returns Cloud Security audit logs for compliance review."""
    if is_azure_sql():
        query = """
            SELECT TOP 100 a.id, a.action, a.details, a.ip_address, a.created_at,
                   u.username, u.role, u.full_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC;
        """
    else:
        query = """
            SELECT a.id, a.action, a.details, a.ip_address, a.created_at,
                   u.username, u.role, u.full_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 100;
        """
    logs = execute_query(query, fetch_all=True)
    return jsonify({"audit_logs": logs}), 200

# ---------------------------------------------------------------------------
# Application Startup & DB check
# ---------------------------------------------------------------------------
with app.app_context():
    if is_azure_sql():
        try:
            seed_sample_data()
        except Exception as exc:
            print(f"[Startup Warning] Could not seed Azure SQL database yet: {exc}")
    elif not os.path.exists(Config.SQLITE_DB_PATH):
        init_database(seed=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
