import io
import csv
from database.db import execute_query

class AnalyticsService:
    @staticmethod
    def get_summary_metrics():
        """Calculates headline KPI metrics for warden dashboard."""
        counts = execute_query(
            """
            SELECT 
                COUNT(id) AS total_parcels,
                SUM(CASE WHEN status IN ('received', 'notified') THEN 1 ELSE 0 END) AS pending_parcels,
                SUM(CASE WHEN status = 'collected' THEN 1 ELSE 0 END) AS collected_parcels,
                SUM(CASE WHEN DATE(received_at) = DATE('now') THEN 1 ELSE 0 END) AS today_parcels
            FROM parcels;
            """,
            fetch_one=True
        ) or {}

        avg_time = execute_query(
            """
            SELECT ROUND(AVG((JULIANDAY(collected_at) - JULIANDAY(received_at)) * 24), 2) AS avg_pickup_hours
            FROM parcels
            WHERE status = 'collected' AND collected_at IS NOT NULL;
            """,
            fetch_one=True
        )

        pending_by_hostel = execute_query(
            """
            SELECT h.name AS hostel_name, h.code AS hostel_code, COUNT(p.id) AS pending_count
            FROM hostels h
            LEFT JOIN parcels p ON h.id = p.hostel_id AND p.status IN ('received', 'notified')
            GROUP BY h.id, h.name, h.code;
            """,
            fetch_all=True
        )

        return {
            "total_parcels": counts.get("total_parcels") or 0,
            "pending_parcels": counts.get("pending_parcels") or 0,
            "collected_parcels": counts.get("collected_parcels") or 0,
            "today_parcels": counts.get("today_parcels") or 0,
            "avg_pickup_hours": (avg_time.get("avg_pickup_hours") if avg_time else None) or 0.0,
            "pending_by_hostel": pending_by_hostel
        }

    @staticmethod
    def get_daily_volume():
        """Queries the view vw_daily_parcel_volume."""
        return execute_query("SELECT * FROM vw_daily_parcel_volume ORDER BY log_date DESC;", fetch_all=True)

    @staticmethod
    def get_avg_pickup_by_hostel():
        """Queries the view vw_avg_pickup_time."""
        return execute_query("SELECT * FROM vw_avg_pickup_time;", fetch_all=True)

    @staticmethod
    def export_powerbi_csv():
        """
        Exports a flat analytical dataset designed for Power BI consumption,
        integrating structured parcel metrics with semi-structured payload fields.
        """
        rows = execute_query(
            """
            SELECT 
                p.id AS ParcelID,
                p.tracking_number AS TrackingNumber,
                p.courier_name AS Courier,
                h.name AS HostelName,
                h.code AS HostelCode,
                s.student_roll_no AS StudentRollNo,
                s.room_no AS RoomNumber,
                p.status AS Status,
                p.received_at AS ReceivedAt,
                p.collected_at AS CollectedAt,
                ROUND((JULIANDAY(COALESCE(p.collected_at, 'now')) - JULIANDAY(p.received_at)) * 24, 2) AS DurationHours,
                CASE WHEN p.photo_url IS NOT NULL THEN 'Yes' ELSE 'No' END AS HasBlobPhoto,
                'Structured (Azure SQL)' AS DataClassification
            FROM parcels p
            JOIN hostels h ON p.hostel_id = h.id
            JOIN students s ON p.student_id = s.id
            ORDER BY p.received_at DESC;
            """,
            fetch_all=True
        )

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        else:
            output.write("ParcelID,TrackingNumber,Courier,HostelName,HostelCode,StudentRollNo,RoomNumber,Status,ReceivedAt,CollectedAt,DurationHours,HasBlobPhoto,DataClassification\n")

        return output.getvalue()
