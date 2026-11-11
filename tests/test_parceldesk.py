import os
import sys
import unittest
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use in-memory or dedicated test database (always isolate tests from Azure SQL)
TEST_DB_PATH = str(PROJECT_ROOT / "database" / "test_parceldesk.db")
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH
os.environ["DB_TYPE"] = "sqlite"
os.environ["AZURE_SQL_CONNECTION_STRING"] = ""

from app import app
from database.init_db import init_database
from database.db import execute_query, insert_and_get_id, is_azure_sql, row_to_dict
from services.analytics_service import AnalyticsService

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

    def test_07_azure_sql_detection_and_tsql_queries(self):
        """Tests Azure SQL detection, row normalization, SCOPE_IDENTITY batching, and T-SQL queries."""
        self.assertFalse(is_azure_sql())

        with patch.dict(os.environ, {"AZURE_SQL_CONNECTION_STRING": "Driver={ODBC Driver 18 for SQL Server};Server=dummy;"}):
            self.assertTrue(is_azure_sql())

            # Test row_to_dict normalization for pyodbc datetime/date/Decimal types
            mock_cursor = MagicMock()
            mock_cursor.description = [("id",), ("received_at",), ("log_date",), ("hours_waiting",)]
            normalized = row_to_dict(
                mock_cursor,
                (1, datetime(2026, 11, 11, 13, 30, 0), date(2026, 11, 11), Decimal("4.5")),
            )
            self.assertEqual(normalized, {
                "id": 1,
                "received_at": "2026-11-11 13:30:00",
                "log_date": "2026-11-11",
                "hours_waiting": 4.5,
            })

            # Test insert_and_get_id uses SCOPE_IDENTITY() batch on Azure SQL
            mock_cursor.description = [("id",)]
            mock_cursor.fetchone.return_value = (42,)
            new_id = insert_and_get_id(mock_cursor, "INSERT INTO parcels (tracking_number) VALUES (?);", ("T-1",))
            self.assertEqual(new_id, 42)
            executed_sql = mock_cursor.execute.call_args[0][0]
            self.assertIn("SET NOCOUNT ON", executed_sql)
            self.assertIn("SCOPE_IDENTITY()", executed_sql)

        # Test T-SQL query generation in AnalyticsService and /api/audit-logs
        with patch("services.analytics_service.is_azure_sql", return_value=True), \
             patch("services.analytics_service.execute_query", return_value=[]) as mock_exec:
            AnalyticsService.get_summary_metrics()
            AnalyticsService.export_powerbi_csv()
            sql_calls = [call.args[0] for call in mock_exec.call_args_list]
            for sql in sql_calls:
                self.assertNotIn("JULIANDAY", sql)
                self.assertNotIn("DATE('now')", sql)
            self.assertTrue(any("SYSUTCDATETIME()" in s for s in sql_calls))
            self.assertTrue(any("DATEDIFF" in s for s in sql_calls))

        self.client.post("/api/login", json={"username": "warden1", "password": "warden123"})
        with patch("app.is_azure_sql", return_value=True), \
             patch("app.execute_query", return_value=[]) as mock_app_exec:
            res_logs = self.client.get("/api/audit-logs")
            self.assertEqual(res_logs.status_code, 200)
            audit_sql = mock_app_exec.call_args[0][0]
            self.assertIn("TOP 100", audit_sql)
            self.assertNotIn("LIMIT 100", audit_sql)


if __name__ == "__main__":
    unittest.main()
