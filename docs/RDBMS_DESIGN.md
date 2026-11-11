# ParcelDesk — RDBMS Database Design (3NF)

## 1. Relational Database Management System Overview
The ParcelDesk database is modeled in **Third Normal Form (3NF)** to eliminate redundancy, avoid update anomalies, and enforce relational integrity across university hostel parcel workflows.

---

## 2. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    users ||--o{ hostels : "warden_user_id manages"
    users ||--o{ students : "user_id belongs to"
    users ||--o{ parcels : "logged_by_guard_id logs"
    users ||--o{ handovers : "verified_by_guard_id releases"
    users ||--o{ audit_logs : "user_id audits"
    
    hostels ||--o{ students : "hostel_id houses"
    hostels ||--o{ parcels : "hostel_id receives"
    
    students ||--o{ parcels : "student_id owns"
    students ||--o{ notifications : "student_id notified"
    students ||--o{ handovers : "student_id collects"
    
    parcels ||--o{ notifications : "parcel_id alerts"
    parcels ||--|| handovers : "parcel_id completes"

    users {
        int id PK
        string username UK
        string password_hash
        string full_name
        string email UK
        string phone
        string role "guard|student|warden|admin"
        datetime created_at
    }

    hostels {
        int id PK
        string name
        string code UK
        int warden_user_id FK
        datetime created_at
    }

    students {
        int id PK
        int user_id FK,UK
        string student_roll_no UK
        int hostel_id FK
        string room_no
        string phone
        datetime created_at
    }

    parcels {
        int id PK
        string tracking_number UK
        string courier_name
        int student_id FK
        int hostel_id FK
        int logged_by_guard_id FK
        string photo_url
        string status "received|notified|collected|returned"
        string otp_hash
        datetime otp_expiry
        int otp_attempts
        datetime received_at
        datetime collected_at
        string remarks
    }

    notifications {
        int id PK
        int parcel_id FK
        int student_id FK
        string channel
        string status
        string payload_json "Semi-structured JSON"
        datetime sent_at
    }

    handovers {
        int id PK
        int parcel_id FK,UK
        int student_id FK
        int verified_by_guard_id FK
        string otp_verified_hash
        datetime handover_time
        string notes
    }

    audit_logs {
        int id PK
        int user_id FK
        string action
        string details
        string ip_address
        datetime created_at
    }
```

---

## 3. Schema Normalization (3NF Justification)

1. **1NF (Atomic Attributes)**: Every column stores atomic values (no multivalued or composite attributes; JSON notification payloads are stored in `notifications.payload_json` for semi-structured log tracking).
2. **2NF (No Partial Functional Dependencies)**: All non-key attributes are fully functionally dependent on the entire primary key (all tables use single-column integer identity/autoincrement primary keys).
3. **3NF (No Transitive Functional Dependencies)**: Core entities (`users`, `hostels`, `students`, `parcels`, `notifications`, `handovers`, `audit_logs`) separate user accounts, hostel metadata, student room allocations, parcel logs, and physical handover proofs. Only SHA-256 hashed OTPs (`otp_hash`) are stored in the `parcels` table, and the plain OTP is shown once at parcel logging. *(Note: `parcels.hostel_id` intentionally snapshots the destination hostel at arrival time even though `students` also has `hostel_id`, and `handovers.student_id`, `notifications.student_id`, and `users.phone`/`students.phone` carry minor denormalized references for direct reporting joins.)*

---

## 4. ACID Transaction Handover Logic

The handover process represents the critical business transition from *holding* to *collected*. Inside [`services/parcel_service.py`](../services/parcel_service.py) (and demonstrated in T-SQL inside [`database/queries.sql`](../database/queries.sql)), verification, handover insertion, parcel status update, and audit logging execute inside a database transaction (`UNIQUE(parcel_id)` on `handovers` prevents duplicate handovers, and invalid OTPs increment `otp_attempts` before raising an error):

```sql
BEGIN TRANSACTION;

-- Step 1: Query parcel state & verify active status, attempts (< 3), and TTL
SELECT id, student_id, status, otp_hash, otp_expiry, otp_attempts
FROM dbo.parcels WITH (UPDLOCK, ROWLOCK) WHERE id = @ParcelId;

-- Step 2: Validate SHA-256 OTP hash (if invalid, increment otp_attempts and reject)

-- Step 3: Insert Handover Proof into ledger (fires trg_parcel_collected_after_handover)
INSERT INTO dbo.handovers (parcel_id, student_id, verified_by_guard_id, otp_verified_hash, handover_time, notes)
VALUES (@ParcelId, @StudentId, @GuardUserId, @SubmittedHash, SYSUTCDATETIME(), @Notes);

-- Step 4: Transition parcel status to collected and clear single-use otp_hash
UPDATE dbo.parcels 
SET status = 'collected', collected_at = SYSUTCDATETIME(), otp_hash = NULL 
WHERE id = @ParcelId;

-- Step 5: Write Security Audit
INSERT INTO dbo.audit_logs (user_id, action, details, created_at)
VALUES (@GuardUserId, 'PARCEL_HANDOVER_COMPLETED', @AuditDetails, SYSUTCDATETIME());

COMMIT TRANSACTION;
```

---

## 5. Database Views (Reporting & Analytics)

Both [`database/azure_sql_schema.sql`](../database/azure_sql_schema.sql) (T-SQL using `DATEDIFF`, `CAST(... AS DATE)`, `SYSUTCDATETIME()`) and [`database/sqlite_schema.sql`](../database/sqlite_schema.sql) (SQLite using `JULIANDAY` and `DATE`) define the same three analytical views (`vw_pending_parcels`, `vw_daily_parcel_volume`, `vw_avg_pickup_time`):

### View 1: `vw_pending_parcels` (SQLite version shown; T-SQL uses `DATEDIFF`)
Provides gate guards and wardens with a live query of packages awaiting pickup, joined with student contact numbers, hostel rooms, and elapsed wait time:
```sql
CREATE VIEW vw_pending_parcels AS
SELECT 
    p.id AS parcel_id,
    p.tracking_number,
    p.courier_name,
    p.photo_url,
    p.status,
    p.received_at,
    h.id AS hostel_id,
    h.name AS hostel_name,
    h.code AS hostel_code,
    s.id AS student_id,
    u.full_name AS student_name,
    s.student_roll_no,
    s.room_no,
    s.phone AS student_phone,
    g.full_name AS logged_by_guard,
    ROUND((JULIANDAY('now') - JULIANDAY(p.received_at)) * 24, 1) AS hours_waiting
FROM parcels p
JOIN students s ON p.student_id = s.id
JOIN users u ON s.user_id = u.id
JOIN hostels h ON p.hostel_id = h.id
JOIN users g ON p.logged_by_guard_id = g.id
WHERE p.status IN ('received', 'notified');
```

### View 2: `vw_daily_parcel_volume`
Aggregates incoming parcel throughput by date and hostel for logistics capacity planning:
```sql
CREATE VIEW vw_daily_parcel_volume AS
SELECT 
    DATE(p.received_at) AS log_date,
    h.name AS hostel_name,
    COUNT(p.id) AS total_parcels,
    SUM(CASE WHEN p.status = 'collected' THEN 1 ELSE 0 END) AS collected_parcels,
    SUM(CASE WHEN p.status IN ('received', 'notified') THEN 1 ELSE 0 END) AS pending_parcels
FROM parcels p
JOIN hostels h ON p.hostel_id = h.id
GROUP BY DATE(p.received_at), h.name;
```

### View 3: `vw_avg_pickup_time`
Calculates average student pickup turnaround time (hours) by hostel:
```sql
CREATE VIEW vw_avg_pickup_time AS
SELECT 
    h.name AS hostel_name,
    COUNT(p.id) AS completed_handovers,
    ROUND(AVG((JULIANDAY(p.collected_at) - JULIANDAY(p.received_at)) * 24), 2) AS avg_pickup_hours
FROM parcels p
JOIN hostels h ON p.hostel_id = h.id
WHERE p.status = 'collected' AND p.collected_at IS NOT NULL
GROUP BY h.name;
```

---

## 6. Indexing & Azure SQL Firewall Notes

### Shared Indexes (Defined in both `azure_sql_schema.sql` and `sqlite_schema.sql`)
1. **`idx_parcels_student_id`** on `parcels(student_id)` — Accelerates student dashboard lookups.
2. **`idx_parcels_status`** on `parcels(status)` — Accelerates pending parcels queries.
3. **`idx_parcels_tracking`** on `parcels(tracking_number)` — Accelerates tracking-number searches.
4. **`idx_notifications_parcel`** on `notifications(parcel_id)` — Accelerates notification lookups per parcel.
5. **`idx_handovers_parcel`** on `handovers(parcel_id)` — Accelerates handover verification lookups.

### SQLite-Only Indexes (Defined in `sqlite_schema.sql` only)
6. **`idx_parcels_hostel`** on `parcels(hostel_id)` — Present in `sqlite_schema.sql`; not defined in `azure_sql_schema.sql`.
7. **`idx_audit_logs_user`** on `audit_logs(user_id)` — Present in `sqlite_schema.sql`; not defined in `azure_sql_schema.sql`.

### Azure SQL Server Networking
- Azure SQL firewall rules enable **Allow Azure services and resources to access this server** (`0.0.0.0`) so App Service can connect, alongside explicit **client IP rules** for local/developer access.
