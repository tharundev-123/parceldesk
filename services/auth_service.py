import json
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import execute_query

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Securely hashes plaintext password with salted PBKDF2/scrypt algorithm."""
        return generate_password_hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verifies password against stored cryptographic hash."""
        return check_password_hash(password_hash, password)

    @classmethod
    def authenticate(cls, username: str, password: str, ip_address: str = None):
        """
        Authenticates user with credentials and retrieves role profile.
        Writes audit log for security tracking.
        """
        user = execute_query(
            "SELECT id, username, password_hash, full_name, email, phone, role FROM users WHERE username = ?;",
            (username,),
            fetch_one=True
        )

        if not user or not cls.verify_password(password, user["password_hash"]):
            cls.log_audit(
                user_id=user["id"] if user else None,
                action="LOGIN_FAILED",
                details=f"Failed login attempt for username: {username}",
                ip_address=ip_address
            )
            return None

        # If student, attach student profile information
        student_info = None
        if user["role"] == "student":
            student_info = execute_query(
                """
                SELECT s.id AS student_id, s.student_roll_no, s.room_no, s.hostel_id, h.name AS hostel_name, h.code AS hostel_code
                FROM students s
                JOIN hostels h ON s.hostel_id = h.id
                WHERE s.user_id = ?;
                """,
                (user["id"],),
                fetch_one=True
            )

        cls.log_audit(
            user_id=user["id"],
            action="LOGIN_SUCCESS",
            details=f"Successful login for role: {user['role']}",
            ip_address=ip_address
        )

        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
            "student_profile": student_info
        }

    @staticmethod
    def log_audit(user_id, action, details, ip_address=None):
        """Records security audit events to audit_logs table."""
        try:
            if isinstance(details, dict):
                details = json.dumps(details)
            execute_query(
                "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (?, ?, ?, ?);",
                (user_id, action, str(details), ip_address)
            )
        except Exception as e:
            print(f"[Audit Log Error] Failed to write audit record: {e}")
