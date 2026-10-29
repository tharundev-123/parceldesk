import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import hashlib
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from database.db import get_connection, get_db
from config import Config

def init_database(seed=True):
    """Executes schema DDL and seeds initial demo data."""
    print(f"[*] Initializing ParcelDesk database at: {Config.SQLITE_DB_PATH}")
    
    schema_path = os.path.join(os.path.dirname(__file__), "sqlite_schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
        print("[+] Schema created successfully (Tables, Views, Indexes, Triggers).")
    finally:
        conn.close()

    if seed:
        seed_sample_data()

def seed_sample_data():
    """Seeds baseline data for Guard, Student, Warden, Hostels, and sample parcels."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if already seeded
        cursor.execute("SELECT COUNT(*) AS count FROM users;")
        if cursor.fetchone()[0] > 0:
            print("[*] Database already populated. Skipping seed.")
            return

        print("[*] Seeding demo users, hostels, students, and sample parcels...")

        # 1. Create Users
        default_pwd_guard = generate_password_hash("guard123")
        default_pwd_warden = generate_password_hash("warden123")
        default_pwd_student = generate_password_hash("student123")
        default_pwd_admin = generate_password_hash("admin123")

        users_data = [
            ("guard1", default_pwd_guard, "Rajesh Kumar (Gate Staff)", "guard1@hostel.edu", "+91 98765 43210", "guard"),
            ("warden1", default_pwd_warden, "Dr. Ananya Sharma (Chief Warden)", "warden@hostel.edu", "+91 98765 43211", "warden"),
            ("admin", default_pwd_admin, "System Administrator", "admin@hostel.edu", "+91 98765 43212", "admin"),
            ("student1", default_pwd_student, "Rahul Verma", "rahul.v@student.edu", "+91 98765 00001", "student"),
            ("student2", default_pwd_student, "Priya Patel", "priya.p@student.edu", "+91 98765 00002", "student"),
            ("student3", default_pwd_student, "Amit Singh", "amit.s@student.edu", "+91 98765 00003", "student")
        ]

        cursor.executemany(
            """
            INSERT INTO users (username, password_hash, full_name, email, phone, role)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            users_data
        )

        # Retrieve user IDs
        cursor.execute("SELECT id, username FROM users;")
        user_ids = {row[1]: row[0] for row in cursor.fetchall()}

        # 2. Create Hostels
        hostels_data = [
            ("Boys Hostel 1 (Everest)", "BH-1", user_ids["warden1"]),
            ("Girls Hostel 1 (Nilgiri)", "GH-1", user_ids["warden1"]),
            ("Boys Hostel 2 (Himalaya)", "BH-2", user_ids["warden1"])
        ]
        cursor.executemany(
            "INSERT INTO hostels (name, code, warden_user_id) VALUES (?, ?, ?);",
            hostels_data
        )

        cursor.execute("SELECT id, code FROM hostels;")
        hostel_ids = {row[1]: row[0] for row in cursor.fetchall()}

        # 3. Create Students
        students_data = [
            (user_ids["student1"], "2024CS101", hostel_ids["BH-1"], "Room 204", "+91 98765 00001"),
            (user_ids["student2"], "2024EC205", hostel_ids["GH-1"], "Room 112", "+91 98765 00002"),
            (user_ids["student3"], "2024ME310", hostel_ids["BH-2"], "Room 301", "+91 98765 00003")
        ]
        cursor.executemany(
            """
            INSERT INTO students (user_id, student_roll_no, hostel_id, room_no, phone)
            VALUES (?, ?, ?, ?, ?);
            """,
            students_data
        )

        cursor.execute("SELECT id, user_id FROM students;")
        student_ids = {row[1]: row[0] for row in cursor.fetchall()}

        # 4. Create Sample Parcels
        # Demo OTP for student1 is 482910 (hashed)
        plain_otp_1 = "482910"
        hash_otp_1 = hashlib.sha256(plain_otp_1.encode('utf-8')).hexdigest()
        expiry_1 = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')

        # Demo OTP for student2 is 739104 (hashed)
        plain_otp_2 = "739104"
        hash_otp_2 = hashlib.sha256(plain_otp_2.encode('utf-8')).hexdigest()
        expiry_2 = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')

        # Parcel 1: Received / Notified (Pending collection for student1)
        cursor.execute(
            """
            INSERT INTO parcels (
                tracking_number, courier_name, student_id, hostel_id, 
                logged_by_guard_id, photo_url, status, otp_hash, 
                otp_expiry, otp_attempts, received_at, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, 'notified', ?, ?, 0, CURRENT_TIMESTAMP, ?);
            """,
            ("AMZ-IN-889210", "Amazon India", student_ids[user_ids["student1"]], hostel_ids["BH-1"],
             user_ids["guard1"], None, hash_otp_1, expiry_1, "Electronics package (Laptop charger)")
        )
        p1_id = cursor.lastrowid

        # Notification for Parcel 1
        notif_payload_1 = f'{{"event": "PARCEL_RECEIVED", "courier": "Amazon India", "tracking": "AMZ-IN-889210", "room": "Room 204", "demo_otp": "{plain_otp_1}"}}'
        cursor.execute(
            "INSERT INTO notifications (parcel_id, student_id, channel, status, payload_json) VALUES (?, ?, 'In-App/SMS', 'sent', ?);",
            (p1_id, student_ids[user_ids["student1"]], notif_payload_1)
        )

        # Parcel 2: Received / Notified (Pending collection for student2)
        cursor.execute(
            """
            INSERT INTO parcels (
                tracking_number, courier_name, student_id, hostel_id, 
                logged_by_guard_id, photo_url, status, otp_hash, 
                otp_expiry, otp_attempts, received_at, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, 'notified', ?, ?, 0, CURRENT_TIMESTAMP, ?);
            """,
            ("FK-BLR-441299", "Flipkart", student_ids[user_ids["student2"]], hostel_ids["GH-1"],
             user_ids["guard1"], None, hash_otp_2, expiry_2, "Book parcel from Flipkart")
        )
        p2_id = cursor.lastrowid

        notif_payload_2 = f'{{"event": "PARCEL_RECEIVED", "courier": "Flipkart", "tracking": "FK-BLR-441299", "room": "Room 112", "demo_otp": "{plain_otp_2}"}}'
        cursor.execute(
            "INSERT INTO notifications (parcel_id, student_id, channel, status, payload_json) VALUES (?, ?, 'In-App/SMS', 'sent', ?);",
            (p2_id, student_ids[user_ids["student2"]], notif_payload_2)
        )

        # Parcel 3: Collected / Handed Over (for student3 earlier today)
        earlier_time = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        collected_time = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """
            INSERT INTO parcels (
                tracking_number, courier_name, student_id, hostel_id, 
                logged_by_guard_id, photo_url, status, otp_hash, 
                otp_expiry, otp_attempts, received_at, collected_at, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, 'collected', NULL, NULL, 0, ?, ?, ?);
            """,
            ("BLUEDART-091283", "Blue Dart", student_ids[user_ids["student3"]], hostel_ids["BH-2"],
             user_ids["guard1"], None, earlier_time, collected_time, "Study notes and clothing")
        )
        p3_id = cursor.lastrowid

        # Handover proof for Parcel 3
        dummy_verified_hash = hashlib.sha256("123456".encode('utf-8')).hexdigest()
        cursor.execute(
            """
            INSERT INTO handovers (parcel_id, student_id, verified_by_guard_id, otp_verified_hash, handover_time, notes)
            VALUES (?, ?, ?, ?, ?, 'Verified with student college ID card and OTP');
            """,
            (p3_id, student_ids[user_ids["student3"]], user_ids["guard1"], dummy_verified_hash, collected_time)
        )

        # Audit Log
        cursor.execute(
            """
            INSERT INTO audit_logs (user_id, action, details)
            VALUES (?, 'SYSTEM_INIT', 'Database seeded with default roles and demo parcels');
            """,
            (user_ids["admin"],)
        )

        print("[+] Seed completed successfully!")
        print("    Demo Logins:")
        print("    - Guard:   username: guard1   / password: guard123")
        print("    - Student: username: student1 / password: student123 (Active OTP: 482910)")
        print("    - Student: username: student2 / password: student123 (Active OTP: 739104)")
        print("    - Warden:  username: warden1  / password: warden123")
        print("    - Admin:   username: admin    / password: admin123")

if __name__ == "__main__":
    init_database()
