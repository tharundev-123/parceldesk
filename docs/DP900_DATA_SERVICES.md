# ParcelDesk — Azure Data Services & DP-900 Implementation

## 1. DP-900 Core Data Classification

In accordance with **Microsoft Azure DP-900 (Azure Data Fundamentals)** concepts, ParcelDesk classifies, stores, and analyzes data across three distinct data categories:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           PARCELDESK DATA CLASSIFICATION                         │
├─────────────────────┬────────────────────────────┬───────────────────────────────┤
│ 1. STRUCTURED DATA  │ 2. SEMI-STRUCTURED DATA    │ 3. UNSTRUCTURED DATA          │
│ (Azure SQL DB)      │ (JSON Notification Logs)   │ (Azure Blob Storage)          │
├─────────────────────┼────────────────────────────┼───────────────────────────────┤
│ • Users & RBAC      │ • Courier delivery events  │ • Physical parcel photographs │
│ • Hostels & Blocks  │ • In-App / SMS payloads    │ • Damaged box proof           │
│ • Students Registry │ • Recipient metadata trees │ • Shipping label scans        │
│ • Parcels Ledger    │ • Dynamic channel routing  │ • Image files (PNG/JPG/WEBP)  │
│ • Handover Proof    │ • Nested event timestamps  │ • Private blob URLs           │
└─────────────────────┴────────────────────────────┴───────────────────────────────┘
```

---

## 2. Structured Data: Azure SQL Database
- **Service**: Azure SQL Database (`parceldesk-td/parceldesk-db`, connected via `pyodbc`; falls back to local SQLite when `AZURE_SQL_CONNECTION_STRING` is unset).
- **Relational Integrity**: 3NF schema across 7 tables with primary keys, foreign keys, `UNIQUE` constraints, and `CHECK` constraints. Only SHA-256 hashed OTPs (`otp_hash`) are stored in the `parcels` table; the plain OTP is shown once at parcel logging.
- **T-SQL Script**: Defined in [`database/azure_sql_schema.sql`](../database/azure_sql_schema.sql) (with 5 indexes in Azure SQL; local [`database/sqlite_schema.sql`](../database/sqlite_schema.sql) defines 2 additional indexes on `parcels(hostel_id)` and `audit_logs(user_id)`).
- **Views**:
  - `dbo.vw_pending_parcels`: Pending parcels per hostel with waiting hours.
  - `dbo.vw_daily_parcel_volume`: Daily total, collected, and pending parcel counts by hostel.
  - `dbo.vw_avg_pickup_time`: Average pickup turnaround time in hours by hostel.
- **Security**:
  - Transparent Data Encryption (TDE) enabled at rest by default on Azure SQL Database.
  - Database Firewall rules enable **Allow Azure services and resources to access this server** (`0.0.0.0`) so Azure App Service can connect, plus explicit **client IP rules** for developer administration.
  - Connection string is stored in Azure App Service environment settings (and `.env` locally, excluded from Git).

---

## 3. Semi-Structured Data: JSON Notification Documents
- **Storage Target**: `notifications.payload_json` column.
- **Characteristics**:
  - Flexible, document-style key-value structure accommodating dynamic event attributes without schema migrations.
  - Contains nested JSON objects (`recipient`, `channels`) and records `otp_issued` rather than plaintext OTPs.

**Sample Notification Payload:**
```json
{
  "event": "PARCEL_RECEIVED",
  "parcel_id": 14,
  "courier": "Amazon India",
  "tracking_number": "AMZ-IN-889210",
  "recipient": {
    "name": "Rahul Verma",
    "room": "Room 204",
    "hostel": "Boys Hostel 1 (Everest)",
    "email": "rahul.v@student.edu",
    "phone": "+91 98765 00001"
  },
  "channels": ["In-App", "SMS", "Email"],
  "message": "Hello Rahul Verma, your parcel from Amazon India (Tracking: AMZ-IN-889210) has arrived at the Boys Hostel 1 (Everest) gate. Present your one-time code to collect.",
  "dispatched_at": "2026-10-30T02:35:00Z",
  "otp_issued": true
}
```

---

## 4. Unstructured Data: Azure Blob Storage
- **Service**: Azure Blob Storage (`parceldeskstore26`, `Standard_LRS`, `StorageV2`, minimum TLS 1.2, public blob access disabled).
- **Container**: `parcel-photos` (**private container** — anonymous public read access is off).
- **Purpose**: Package condition photos uploaded by gate staff during parcel entry.
- **Implementation & Limitation**: [`services/storage_service.py`](../services/storage_service.py) uploads images to Azure Blob Storage using `BlobServiceClient` when `AZURE_STORAGE_CONNECTION_STRING` is configured (falling back to local `static/uploads/` otherwise) and stores `blob_client.url` in `parcels.photo_url`. Because `parcel-photos` is private, displaying those uploaded Azure Blob URLs directly inside browser `<img>` tags requires adding SAS token generation or an authenticated backend proxy route in future work.

---

## 5. Power BI Analytics & Reporting

### Report Artifacts & Specifications
- **Power BI Desktop Report:** [`parceldesk-analytics.pbix`](../parceldesk-analytics.pbix) built from the exported CSVs of the three Azure SQL analytics views (`analytics/vw_daily_parcel_volume.csv`, `analytics/vw_avg_pickup_time.csv`, `analytics/vw_pending_parcels.csv`) following [`analytics/POWERBI_STEPS.md`](../analytics/POWERBI_STEPS.md).
- **Three Visuals:**
  1. **Parcels Per Day** (from `vw_daily_parcel_volume`: `log_date`, `total_parcels`, `hostel_name`).
  2. **Average Pickup Hours per Hostel** (from `vw_avg_pickup_time`: `hostel_name`, `avg_pickup_hours`).
  3. **Pending Parcels per Hostel** (from `vw_pending_parcels`: `hostel_name`, `parcel_id` count).
- **REST Dataset Export**: Wardens and admins can also export a live CSV dataset directly from `/api/analytics/powerbi-export`.
