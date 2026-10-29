-- =====================================================================
-- ParcelDesk: Azure SQL Database Schema (T-SQL / DP-900 Compliant)
-- Relational Database Management System (3NF Normalized)
-- =====================================================================

-- 1. Users Table (Role-Based Access Control)
IF OBJECT_ID('dbo.users', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        password_hash NVARCHAR(255) NOT NULL,
        full_name NVARCHAR(100) NOT NULL,
        email NVARCHAR(100) NOT NULL UNIQUE,
        phone NVARCHAR(20) NULL,
        role NVARCHAR(20) NOT NULL CHECK (role IN ('guard', 'student', 'warden', 'admin')),
        created_at DATETIME2 DEFAULT SYSUTCDATETIME()
    );
END;

-- 2. Hostels Table
IF OBJECT_ID('dbo.hostels', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.hostels (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(100) NOT NULL,
        code NVARCHAR(20) NOT NULL UNIQUE,
        warden_user_id INT NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_hostels_warden FOREIGN KEY (warden_user_id) REFERENCES dbo.users(id) ON DELETE SET NULL
    );
END;

-- 3. Students Table
IF OBJECT_ID('dbo.students', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.students (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL UNIQUE,
        student_roll_no NVARCHAR(30) NOT NULL UNIQUE,
        hostel_id INT NOT NULL,
        room_no NVARCHAR(20) NOT NULL,
        phone NVARCHAR(20) NOT NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_students_user FOREIGN KEY (user_id) REFERENCES dbo.users(id) ON DELETE CASCADE,
        CONSTRAINT FK_students_hostel FOREIGN KEY (hostel_id) REFERENCES dbo.hostels(id)
    );
END;

-- 4. Parcels Table (Core Transactional Ledger)
IF OBJECT_ID('dbo.parcels', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.parcels (
        id INT IDENTITY(1,1) PRIMARY KEY,
        tracking_number NVARCHAR(60) NOT NULL UNIQUE,
        courier_name NVARCHAR(50) NOT NULL,
        student_id INT NOT NULL,
        hostel_id INT NOT NULL,
        logged_by_guard_id INT NOT NULL,
        photo_url NVARCHAR(500) NULL,
        status NVARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'notified', 'collected', 'returned')),
        otp_hash NVARCHAR(64) NULL,
        otp_expiry DATETIME2 NULL,
        otp_attempts INT DEFAULT 0,
        received_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        collected_at DATETIME2 NULL,
        remarks NVARCHAR(MAX) NULL,
        CONSTRAINT FK_parcels_student FOREIGN KEY (student_id) REFERENCES dbo.students(id),
        CONSTRAINT FK_parcels_hostel FOREIGN KEY (hostel_id) REFERENCES dbo.hostels(id),
        CONSTRAINT FK_parcels_guard FOREIGN KEY (logged_by_guard_id) REFERENCES dbo.users(id)
    );
END;

-- 5. Notifications Table (Semi-structured JSON payloads)
IF OBJECT_ID('dbo.notifications', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.notifications (
        id INT IDENTITY(1,1) PRIMARY KEY,
        parcel_id INT NOT NULL,
        student_id INT NOT NULL,
        channel NVARCHAR(30) NOT NULL DEFAULT 'In-App/SMS',
        status NVARCHAR(20) NOT NULL DEFAULT 'sent' CHECK (status IN ('queued', 'sent', 'delivered', 'failed')),
        payload_json NVARCHAR(MAX) NOT NULL,
        sent_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_notifications_parcel FOREIGN KEY (parcel_id) REFERENCES dbo.parcels(id) ON DELETE CASCADE,
        CONSTRAINT FK_notifications_student FOREIGN KEY (student_id) REFERENCES dbo.students(id)
    );
END;

-- 6. Handovers Table (Proof of verified physical collection)
IF OBJECT_ID('dbo.handovers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.handovers (
        id INT IDENTITY(1,1) PRIMARY KEY,
        parcel_id INT NOT NULL UNIQUE,
        student_id INT NOT NULL,
        verified_by_guard_id INT NOT NULL,
        otp_verified_hash NVARCHAR(64) NOT NULL,
        handover_time DATETIME2 DEFAULT SYSUTCDATETIME(),
        notes NVARCHAR(MAX) NULL,
        CONSTRAINT FK_handovers_parcel FOREIGN KEY (parcel_id) REFERENCES dbo.parcels(id),
        CONSTRAINT FK_handovers_student FOREIGN KEY (student_id) REFERENCES dbo.students(id),
        CONSTRAINT FK_handovers_guard FOREIGN KEY (verified_by_guard_id) REFERENCES dbo.users(id)
    );
END;

-- 7. Audit Logs Table (Cloud Security & Compliance)
IF OBJECT_ID('dbo.audit_logs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_logs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NULL,
        action NVARCHAR(50) NOT NULL,
        details NVARCHAR(MAX) NULL,
        ip_address NVARCHAR(45) NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_audit_user FOREIGN KEY (user_id) REFERENCES dbo.users(id) ON DELETE SET NULL
    );
END;

-- =====================================================================
-- INDEXES
-- =====================================================================
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_parcels_student_id')
    CREATE INDEX idx_parcels_student_id ON dbo.parcels(student_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_parcels_status')
    CREATE INDEX idx_parcels_status ON dbo.parcels(status);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_parcels_tracking')
    CREATE INDEX idx_parcels_tracking ON dbo.parcels(tracking_number);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_notifications_parcel')
    CREATE INDEX idx_notifications_parcel ON dbo.notifications(parcel_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_handovers_parcel')
    CREATE INDEX idx_handovers_parcel ON dbo.handovers(parcel_id);

-- =====================================================================
-- VIEWS (Power BI DirectQuery / Import)
-- =====================================================================
CREATE OR ALTER VIEW dbo.vw_pending_parcels AS
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
    CAST(DATEDIFF(MINUTE, p.received_at, SYSUTCDATETIME()) / 60.0 AS DECIMAL(6,1)) AS hours_waiting
FROM dbo.parcels p
INNER JOIN dbo.students s ON p.student_id = s.id
INNER JOIN dbo.users u ON s.user_id = u.id
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
INNER JOIN dbo.users g ON p.logged_by_guard_id = g.id
WHERE p.status IN ('received', 'notified');
GO

CREATE OR ALTER VIEW dbo.vw_daily_parcel_volume AS
SELECT 
    CAST(p.received_at AS DATE) AS log_date,
    h.name AS hostel_name,
    COUNT(p.id) AS total_parcels,
    SUM(CASE WHEN p.status = 'collected' THEN 1 ELSE 0 END) AS collected_parcels,
    SUM(CASE WHEN p.status IN ('received', 'notified') THEN 1 ELSE 0 END) AS pending_parcels
FROM dbo.parcels p
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
GROUP BY CAST(p.received_at AS DATE), h.name;
GO

CREATE OR ALTER VIEW dbo.vw_avg_pickup_time AS
SELECT 
    h.name AS hostel_name,
    COUNT(p.id) AS completed_handovers,
    ROUND(AVG(CAST(DATEDIFF(MINUTE, p.received_at, p.collected_at) AS FLOAT) / 60.0), 2) AS avg_pickup_hours
FROM dbo.parcels p
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
WHERE p.status = 'collected' AND p.collected_at IS NOT NULL
GROUP BY h.name;
GO

-- =====================================================================
-- TRIGGER: Automatic Parcel Status Transition on Handover
-- =====================================================================
CREATE OR ALTER TRIGGER dbo.trg_parcel_collected_after_handover
ON dbo.handovers
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE p
    SET p.status = 'collected',
        p.collected_at = i.handover_time
    FROM dbo.parcels p
    INNER JOIN inserted i ON p.id = i.parcel_id;
END;
GO
