# ParcelDesk — Azure Data Services & DP-900 Implementation

## 1. DP-900 Core Data Classification

In accordance with **Microsoft Azure DP-900 (Azure Data Fundamentals)** concepts, ParcelDesk classifies, stores, and analyzes data across three distinct architectural tiers:

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
│ • Parcels Ledger    │ • Dynamic channel routing  │ • High-resolution JPEG/PNG    │
│ • Handover Proof    │ • Nested event timestamps  │ • Direct Blob URLs            │
└─────────────────────┴────────────────────────────┴───────────────────────────────┘
```

---

## 2. Structured Data: Azure SQL Database
- **Service**: Azure SQL Database (Serverless or Provisioned DTU/vCore tier).
- **Relational Integrity**: Strict 3NF schema, primary keys, foreign keys with referential constraints (`ON DELETE CASCADE` / `ON DELETE RESTRICT`).
- **T-SQL Script**: Fully defined in [`database/azure_sql_schema.sql`](file:///c:/Users/THARUN%20DEV/OneDrive/Documents/parceldesk-project/database/azure_sql_schema.sql).
- **Views**:
  - `dbo.vw_pending_parcels`: Feeds live gate operations and Power BI DirectQuery.
  - `dbo.vw_daily_parcel_volume`: Daily aggregation for trend analysis.
  - `dbo.vw_avg_pickup_time`: Turnaround latency calculation.
- **Security**:
  - Transparent Data Encryption (TDE) enabled at rest.
  - Database Firewall rules restricting ingress exclusively to Azure App Service outbound virtual IP.
  - Connection string configured via environment variables or Azure Key Vault.

---

## 3. Semi-Structured Data: JSON Notification Documents
- **Storage Target**: `notifications.payload_json` column.
- **Characteristics**:
  - Flexible, document-style key-value structure accommodating varied courier APIs (e.g. Amazon Logistics vs Blue Dart).
  - Contains nested JSON objects (`recipient`, `channels`, `metadata`).
  - Allows adding new communication channels (e.g., WhatsApp, WebPush) without running DDL schema migrations.

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
- **Service**: Azure Blob Storage (General-purpose v2).
- **Container**: `parcel-photos` (Hot Access Tier for quick gate uploads and student viewing).
- **Purpose**: High-resolution package condition photos and shipping label captures uploaded by gate guards.
- **Resilience**: The backend [`services/storage_service.py`](file:///c:/Users/THARUN%20DEV/OneDrive/Documents/parceldesk-project/services/storage_service.py) automatically uploads to Azure Blob Storage using `BlobServiceClient` when credentials are present, and seamlessly falls back to local protected disk storage during offline local development.

---

## 5. Power BI Analytics & Reporting

### Report Specifications:
1. **Daily Parcel Volume (Line / Area Chart)**:
   - X-Axis: `log_date`
   - Y-Axis: `total_parcels`, `collected_parcels`, `pending_parcels`
   - Legend: `hostel_name`
2. **Average Pickup Turnaround Latency (Card / Bar Chart)**:
   - Metric: `avg_pickup_hours` (duration between receipt at gate and verified handover).
   - Target: Under 12.0 hours.
3. **Pending Parcels by Hostel (Stacked Column Chart)**:
   - Displays real-time physical backlog occupying shelf space at gate storage per hostel block.

### Power BI Data Ingestion:
- **DirectQuery / SQL Query**: Connects directly to Azure SQL Views (`vw_pending_parcels`, `vw_daily_parcel_volume`).
- **REST Dataset Export**: Wardens can click **"Export Power BI Dataset (CSV)"** from the dashboard or consume `/api/analytics/powerbi-export` to refresh desktop models.
