import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from database.db import execute_query, get_db, insert_and_get_id, row_to_dict
from config import Config
from services.auth_service import AuthService
from services.notification_service import NotificationService

class ParcelService:
    @staticmethod
    def _hash_otp(plain_otp: str) -> str:
        """Computes SHA-256 digest of plaintext OTP."""
        return hashlib.sha256(plain_otp.strip().encode('utf-8')).hexdigest()

    @staticmethod
    def generate_otp_code() -> str:
        """Generates a secure 6-digit numeric OTP."""
        return f"{secrets.randbelow(900000) + 100000}"

    @classmethod
    def log_parcel(cls, tracking_number: str, courier_name: str, student_id: int, 
                   hostel_id: int, logged_by_guard_id: int, photo_url: str = None, 
                   remarks: str = None, ip_address: str = None):
        """
        Logs an incoming parcel at the hostel gate.
        Generates a hashed single-use OTP with short TTL (System Design Trade-off).
        Dispatches semi-structured notification (DP-900).
        """
        # 1. Generate secure OTP and cryptographic hash
        plain_otp = cls.generate_otp_code()
        otp_hash = cls._hash_otp(plain_otp)
        expiry_time = (datetime.now(timezone.utc) + timedelta(minutes=Config.OTP_EXPIRY_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')

        # 2. Insert parcel record
        with get_db() as conn:
            cursor = conn.cursor()
            parcel_id = insert_and_get_id(
                cursor,
                """
                INSERT INTO parcels (
                    tracking_number, courier_name, student_id, hostel_id, 
                    logged_by_guard_id, photo_url, status, otp_hash, 
                    otp_expiry, otp_attempts, received_at, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, 'received', ?, ?, 0, CURRENT_TIMESTAMP, ?);
                """,
                (tracking_number, courier_name, student_id, hostel_id,
                 logged_by_guard_id, photo_url, otp_hash, expiry_time, remarks)
            )

        # 3. Retrieve student and hostel details for notification
        student_details = execute_query(
            """
            SELECT s.id, u.full_name, u.email, s.phone, s.room_no, h.name AS hostel_name
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN hostels h ON s.hostel_id = h.id
            WHERE s.id = ?;
            """,
            (student_id,),
            fetch_one=True
        )

        # 4. Dispatch notification with semi-structured JSON payload
        if student_details:
            NotificationService.create_and_send_notification(
                parcel_id=parcel_id,
                student_id=student_id,
                courier_name=courier_name,
                tracking_number=tracking_number,
                student_name=student_details["full_name"],
                student_email=student_details["email"],
                student_phone=student_details["phone"],
                room_no=student_details["room_no"],
                hostel_name=student_details["hostel_name"],
                raw_otp=plain_otp
            )

        # 5. Audit Log
        AuthService.log_audit(
            user_id=logged_by_guard_id,
            action="PARCEL_LOGGED",
            details={
                "parcel_id": parcel_id,
                "tracking_number": tracking_number,
                "courier": courier_name,
                "student_id": student_id,
                "otp_expiry": expiry_time
            },
            ip_address=ip_address
        )

        return {
            "parcel_id": parcel_id,
            "tracking_number": tracking_number,
            "status": "notified",
            "plain_otp": plain_otp,  # Transmitted directly to student via notification; never saved plain in DB
            "otp_expiry": expiry_time
        }

    @classmethod
    def regenerate_otp_for_student(cls, parcel_id: int, student_id: int):
        """
        Regenerates an expired OTP for an active uncollected parcel.
        Ensures only the authorized student or warden can trigger this.
        """
        parcel = execute_query(
            "SELECT id, status, student_id FROM parcels WHERE id = ?;",
            (parcel_id,),
            fetch_one=True
        )

        if not parcel:
            raise ValueError("Parcel not found.")
        if parcel["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not own this parcel.")
        if parcel["status"] == "collected":
            raise ValueError("Parcel has already been collected.")

        plain_otp = cls.generate_otp_code()
        otp_hash = cls._hash_otp(plain_otp)
        expiry_time = (datetime.now(timezone.utc) + timedelta(minutes=Config.OTP_EXPIRY_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')

        execute_query(
            """
            UPDATE parcels 
            SET otp_hash = ?, otp_expiry = ?, otp_attempts = 0 
            WHERE id = ?;
            """,
            (otp_hash, expiry_time, parcel_id),
            commit=True
        )

        AuthService.log_audit(
            user_id=None,
            action="OTP_REGENERATED",
            details={"parcel_id": parcel_id, "student_id": student_id, "new_expiry": expiry_time}
        )

        return {
            "parcel_id": parcel_id,
            "plain_otp": plain_otp,
            "otp_expiry": expiry_time
        }

    @classmethod
    def handover_parcel(cls, parcel_id: int, submitted_otp: str, guard_user_id: int, 
                        notes: str = None, ip_address: str = None):
        """
        Executes an atomic ACID database transaction:
        1. Validates parcel existence, state, and attempts.
        2. Validates OTP TTL (expiry).
        3. Verifies SHA-256 hash of submitted OTP.
        4. Updates parcel status to 'collected' and records collected_at timestamp.
        5. Inserts record into handovers ledger.
        6. Writes audit log.
        All steps succeed together or roll back cleanly.
        """
        submitted_hash = cls._hash_otp(submitted_otp)

        with get_db() as conn:
            cursor = conn.cursor()

            # 1. Fetch parcel row
            cursor.execute(
                """
                SELECT id, student_id, hostel_id, status, otp_hash, otp_expiry, otp_attempts
                FROM parcels WHERE id = ?;
                """,
                (parcel_id,)
            )
            parcel = cursor.fetchone()
            if not parcel:
                raise ValueError("Parcel not found.")

            parcel = row_to_dict(cursor, parcel)

            # 2. State validation
            if parcel["status"] == "collected":
                raise ValueError("Parcel has already been collected.")

            # 3. Rate limiting / Brute-force check
            if parcel["otp_attempts"] >= Config.MAX_OTP_ATTEMPTS:
                raise ValueError("Maximum OTP verification attempts exceeded. Please ask student to regenerate OTP.")

            # 4. Expiry validation
            if parcel["otp_expiry"]:
                expiry_dt = datetime.strptime(str(parcel["otp_expiry"])[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expiry_dt:
                    raise ValueError("OTP has expired. Please regenerate a new OTP from student portal.")

            # 5. Cryptographic hash comparison
            if parcel["otp_hash"] != submitted_hash:
                # Increment failed attempts
                cursor.execute(
                    "UPDATE parcels SET otp_attempts = otp_attempts + 1 WHERE id = ?;",
                    (parcel_id,)
                )
                conn.commit()  # Persist failure count even if handover fails
                
                AuthService.log_audit(
                    user_id=guard_user_id,
                    action="HANDOVER_FAILED_INVALID_OTP",
                    details={"parcel_id": parcel_id, "attempts": parcel["otp_attempts"] + 1},
                    ip_address=ip_address
                )
                raise ValueError("Invalid OTP code. Please verify the code displayed on student device.")

            # 6. ATOMIC TRANSACTION: Handover Ledger + Parcel Status Update
            # Step A: Insert Handover Proof
            handover_id = insert_and_get_id(
                cursor,
                """
                INSERT INTO handovers (parcel_id, student_id, verified_by_guard_id, otp_verified_hash, handover_time, notes)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (parcel_id, parcel["student_id"], guard_user_id, submitted_hash, notes)
            )

            # Step B: Mark parcel as collected (also supported by DB trigger)
            cursor.execute(
                """
                UPDATE parcels 
                SET status = 'collected', collected_at = CURRENT_TIMESTAMP, otp_hash = NULL 
                WHERE id = ?;
                """,
                (parcel_id,)
            )

            # Step C: Log successful handover audit
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, details, ip_address, created_at)
                VALUES (?, 'PARCEL_HANDOVER_COMPLETED', ?, ?, CURRENT_TIMESTAMP);
                """,
                (guard_user_id, f"Parcel {parcel_id} verified and handed over. Handover ID: {handover_id}", ip_address)
            )

        return {
            "success": True,
            "handover_id": handover_id,
            "parcel_id": parcel_id,
            "status": "collected"
        }

    @staticmethod
    def get_pending_parcels():
        """Queries the RDBMS view vw_pending_parcels."""
        return execute_query("SELECT * FROM vw_pending_parcels ORDER BY received_at DESC;", fetch_all=True)

    @staticmethod
    def get_all_parcels(status_filter=None, hostel_id=None):
        """Retrieves all parcels with relational joins for warden/guard overview."""
        query = """
            SELECT 
                p.id, p.tracking_number, p.courier_name, p.photo_url, p.status, 
                p.received_at, p.collected_at, p.remarks, p.otp_expiry,
                s.id AS student_id, s.student_roll_no, s.room_no,
                u.full_name AS student_name, u.email AS student_email,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code,
                g.full_name AS guard_name,
                ho.handover_time, ho.notes AS handover_notes,
                vg.full_name AS verified_by_guard_name
            FROM parcels p
            JOIN students s ON p.student_id = s.id
            JOIN users u ON s.user_id = u.id
            JOIN hostels h ON p.hostel_id = h.id
            JOIN users g ON p.logged_by_guard_id = g.id
            LEFT JOIN handovers ho ON p.id = ho.parcel_id
            LEFT JOIN users vg ON ho.verified_by_guard_id = vg.id
            WHERE 1=1
        """
        params = []
        if status_filter:
            query += " AND p.status = ?"
            params.append(status_filter)
        if hostel_id:
            query += " AND p.hostel_id = ?"
            params.append(hostel_id)

        query += " ORDER BY p.received_at DESC;"
        return execute_query(query, params, fetch_all=True)

    @staticmethod
    def get_student_parcels(student_id: int):
        """Retrieves parcels specifically addressed to a student."""
        query = """
            SELECT 
                p.id, p.tracking_number, p.courier_name, p.photo_url, p.status, 
                p.received_at, p.collected_at, p.remarks, p.otp_expiry,
                h.name AS hostel_name, h.code AS hostel_code,
                ho.handover_time
            FROM parcels p
            JOIN hostels h ON p.hostel_id = h.id
            LEFT JOIN handovers ho ON p.id = ho.parcel_id
            WHERE p.student_id = ?
            ORDER BY p.received_at DESC;
        """
        return execute_query(query, (student_id,), fetch_all=True)
