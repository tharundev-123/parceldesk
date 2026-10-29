import os
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use in-memory or dedicated test database
TEST_DB_PATH = str(PROJECT_ROOT / "database" / "test_parceldesk.db")
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH
os.environ["DB_TYPE"] = "sqlite"

from app import app
from database.init_db import init_database
from database.db import execute_query

class ParcelDeskTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Remove old test DB if present
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_database(seed=True)
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    def test_01_authentication_guard_success(self):
        """Tests successful login for Gate Guard."""
        res = self.client.post("/api/login", json={
            "username": "guard1",
            "password": "guard123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["user"]["role"], "guard")
        self.assertEqual(data["user"]["username"], "guard1")

    def test_02_authentication_invalid_password(self):
        """Tests security response on invalid password and audit logging."""
        res = self.client.post("/api/login", json={
            "username": "guard1",
            "password": "wrongpassword!"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("error", res.get_json())

        # Check audit log
        audit = execute_query(
            "SELECT action FROM audit_logs WHERE action = 'LOGIN_FAILED' ORDER BY id DESC LIMIT 1;",
            fetch_one=True
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit["action"], "LOGIN_FAILED")

    def test_03_log_incoming_parcel(self):
        """Tests Gate Staff logging incoming parcel with hashed OTP and notification."""
        # Login as guard
        self.client.post("/api/login", json={"username": "guard1", "password": "guard123"})

        res = self.client.post("/api/parcels", json={
            "student_id": 1,
            "hostel_id": 1,
            "courier_name": "Amazon Express",
            "tracking_number": "TEST-AMZ-99901",
            "remarks": "Urgent study material"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("parcel", data)
        self.assertEqual(data["parcel"]["tracking_number"], "TEST-AMZ-99901")
        
        # Verify plain OTP was generated for notification
        plain_otp = data["parcel"]["plain_otp"]
        self.assertEqual(len(plain_otp), 6)

        # Verify parcel row in DB has only the SHA-256 hash (64 hex characters)
        parcel_id = data["parcel"]["parcel_id"]
        db_row = execute_query("SELECT otp_hash, status FROM parcels WHERE id = ?;", (parcel_id,), fetch_one=True)
        self.assertIsNotNone(db_row)
        self.assertEqual(len(db_row["otp_hash"]), 64)
        self.assertNotEqual(db_row["otp_hash"], plain_otp)

        # Verify semi-structured JSON notification record created
        notif = execute_query("SELECT payload_json FROM notifications WHERE parcel_id = ?;", (parcel_id,), fetch_one=True)
        self.assertIsNotNone(notif)
        self.assertIn("Amazon Express", notif["payload_json"])

    def test_04_handover_with_invalid_otp_fails(self):
        """Tests that invalid OTP is rejected and attempt counter increments."""
        # Find an active pending parcel
        parcel = execute_query("SELECT id FROM parcels WHERE status IN ('received', 'notified') LIMIT 1;", fetch_one=True)
        self.assertIsNotNone(parcel)
        p_id = parcel["id"]

        # Login as guard
        self.client.post("/api/login", json={"username": "guard1", "password": "guard123"})

        res = self.client.post(f"/api/parcels/{p_id}/handover", json={
            "otp": "000000"  # Deliberately invalid code
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid OTP", res.get_json()["error"])

        # Check attempts counter
        p_row = execute_query("SELECT otp_attempts FROM parcels WHERE id = ?;", (p_id,), fetch_one=True)
        self.assertGreaterEqual(p_row["otp_attempts"], 1)

    def test_05_student_regenerate_otp_and_successful_handover(self):
        """Tests student regenerating OTP and guard executing atomic handover transaction."""
        # 1. Login as Student 1 (user_id = 4, student_id = 1)
        self.client.post("/api/login", json={"username": "student1", "password": "student123"})

        # Find parcel owned by student 1
        parcel = execute_query("SELECT id FROM parcels WHERE student_id = 1 AND status != 'collected' LIMIT 1;", fetch_one=True)
        self.assertIsNotNone(parcel)
        p_id = parcel["id"]

        # Regenerate OTP
        res_otp = self.client.post(f"/api/parcels/{p_id}/regenerate-otp")
        self.assertEqual(res_otp.status_code, 200)
        new_otp = res_otp.get_json()["otp_data"]["plain_otp"]
        self.assertEqual(len(new_otp), 6)

        # 2. Login as Guard to execute handover
        self.client.post("/api/login", json={"username": "guard1", "password": "guard123"})
        res_handover = self.client.post(f"/api/parcels/{p_id}/handover", json={
            "otp": new_otp,
            "notes": "Verified Student ID Card"
        })
        self.assertEqual(res_handover.status_code, 200)
        self.assertEqual(res_handover.get_json()["handover"]["status"], "collected")

        # 3. Verify Database State
        # Parcel status updated
        p_after = execute_query("SELECT status, collected_at FROM parcels WHERE id = ?;", (p_id,), fetch_one=True)
        self.assertEqual(p_after["status"], "collected")
        self.assertIsNotNone(p_after["collected_at"])

        # Handover ledger row inserted
        handover_row = execute_query("SELECT * FROM handovers WHERE parcel_id = ?;", (p_id,), fetch_one=True)
        self.assertIsNotNone(handover_row)
        self.assertEqual(handover_row["notes"], "Verified Student ID Card")

    def test_06_views_and_analytics_kpis(self):
        """Tests RDBMS Views (vw_pending_parcels, vw_daily_parcel_volume, vw_avg_pickup_time)."""
        self.client.post("/api/login", json={"username": "warden1", "password": "warden123"})

        # Summary API
        res = self.client.get("/api/analytics/summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["total_parcels"], 0)
        self.assertIn("pending_by_hostel", data["summary"])

        # Power BI CSV export
        res_csv = self.client.get("/api/analytics/powerbi-export")
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.content_type)
        self.assertIn(b"TrackingNumber", res_csv.data)
        self.assertIn(b"Structured (Azure SQL)", res_csv.data)

if __name__ == "__main__":
    unittest.main()
