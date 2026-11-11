import json
from datetime import datetime, timezone
from database.db import execute_query, get_db, insert_and_get_id
from services.auth_service import AuthService

class NotificationService:
    @staticmethod
    def create_and_send_notification(parcel_id, student_id, courier_name, tracking_number, 
                                     student_name, student_email, student_phone, room_no, hostel_name, raw_otp=None):
        """
        Creates a semi-structured JSON notification payload (DP-900 Semi-structured data)
        and persists it to the notifications table. Updates parcel status to 'notified'.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Semi-structured JSON Document payload
        payload = {
            "event": "PARCEL_RECEIVED",
            "parcel_id": parcel_id,
            "courier": courier_name,
            "tracking_number": tracking_number,
            "recipient": {
                "name": student_name,
                "room": room_no,
                "hostel": hostel_name,
                "email": student_email,
                "phone": student_phone
            },
            "channels": ["In-App", "SMS", "Email"],
            "message": f"Hello {student_name}, your parcel from {courier_name} (Tracking: {tracking_number}) has arrived at the {hostel_name} gate. Present your one-time code to collect.",
            "dispatched_at": now_iso,
            "otp_issued": True if raw_otp else False
        }

        payload_json = json.dumps(payload, indent=2)

        with get_db() as conn:
            cursor = conn.cursor()
            
            # Insert notification record with JSON payload
            notif_id = insert_and_get_id(
                cursor,
                """
                INSERT INTO notifications (parcel_id, student_id, channel, status, payload_json, sent_at)
                VALUES (?, ?, ?, 'sent', ?, CURRENT_TIMESTAMP);
                """,
                (parcel_id, student_id, "In-App/SMS", payload_json)
            )

            # Update parcel status to 'notified' if it was 'received'
            cursor.execute(
                "UPDATE parcels SET status = 'notified' WHERE id = ? AND status = 'received';",
                (parcel_id,)
            )

        # Audit log for compliance
        AuthService.log_audit(
            user_id=None,
            action="NOTIFICATION_SENT",
            details={"notification_id": notif_id, "parcel_id": parcel_id, "student_id": student_id}
        )

        return {
            "notification_id": notif_id,
            "parcel_id": parcel_id,
            "status": "sent",
            "payload": payload
        }

    @staticmethod
    def get_notifications_for_student(student_id):
        """Fetches and parses notifications for a specific student."""
        rows = execute_query(
            """
            SELECT n.id, n.parcel_id, n.student_id, n.channel, n.status, n.payload_json, n.sent_at,
                   p.tracking_number, p.courier_name, p.status AS parcel_status
            FROM notifications n
            JOIN parcels p ON n.parcel_id = p.id
            WHERE n.student_id = ?
            ORDER BY n.sent_at DESC;
            """,
            (student_id,),
            fetch_all=True
        )

        for row in rows:
            try:
                row["payload"] = json.loads(row["payload_json"])
            except Exception:
                row["payload"] = {}

        return rows
