-- =====================================================================
-- ParcelDesk: Relational Database Schema (SQLite 3NF compliant)
-- Target: Development and local testing
-- =====================================================================

PRAGMA foreign_keys = ON;

-- 1. Users Table (Role-Based Access Control)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    role VARCHAR(20) NOT NULL CHECK (role IN ('guard', 'student', 'warden', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Hostels Table
CREATE TABLE IF NOT EXISTS hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,
    warden_user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (warden_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 3. Students Table (Extends user with hostel-specific details)
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    student_roll_no VARCHAR(30) NOT NULL UNIQUE,
    hostel_id INTEGER NOT NULL,
    room_no VARCHAR(20) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (hostel_id) REFERENCES hostels(id) ON DELETE RESTRICT
);

-- 4. Parcels Table (Core transactional log of incoming packages)
CREATE TABLE IF NOT EXISTS parcels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number VARCHAR(60) NOT NULL UNIQUE,
    courier_name VARCHAR(50) NOT NULL,
    student_id INTEGER NOT NULL,
    hostel_id INTEGER NOT NULL,
    logged_by_guard_id INTEGER NOT NULL,
    photo_url VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'notified', 'collected', 'returned')),
    otp_hash VARCHAR(64),
    otp_expiry TIMESTAMP,
    otp_attempts INTEGER DEFAULT 0,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    collected_at TIMESTAMP,
    remarks TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (hostel_id) REFERENCES hostels(id) ON DELETE RESTRICT,
    FOREIGN KEY (logged_by_guard_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- 5. Notifications Table (Semi-structured notification payload storage)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    channel VARCHAR(30) NOT NULL DEFAULT 'In-App/SMS',
    status VARCHAR(20) NOT NULL DEFAULT 'sent' CHECK (status IN ('queued', 'sent', 'delivered', 'failed')),
    payload_json TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parcel_id) REFERENCES parcels(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- 6. Handovers Table (Proof of collection ledger)
CREATE TABLE IF NOT EXISTS handovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL UNIQUE,
    student_id INTEGER NOT NULL,
    verified_by_guard_id INTEGER NOT NULL,
    otp_verified_hash VARCHAR(64) NOT NULL,
    handover_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (parcel_id) REFERENCES parcels(id) ON DELETE RESTRICT,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (verified_by_guard_id) REFERENCES users(id) ON DELETE RESTRICT
);

-- 7. Audit Logs Table (Security and compliance audit trail)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action VARCHAR(50) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- =====================================================================
-- INDEXES (Optimizing query performance for frequent lookups)
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_parcels_student_id ON parcels(student_id);
CREATE INDEX IF NOT EXISTS idx_parcels_status ON parcels(status);
CREATE INDEX IF NOT EXISTS idx_parcels_tracking ON parcels(tracking_number);
CREATE INDEX IF NOT EXISTS idx_parcels_hostel ON parcels(hostel_id);
CREATE INDEX IF NOT EXISTS idx_notifications_parcel ON notifications(parcel_id);
CREATE INDEX IF NOT EXISTS idx_handovers_parcel ON handovers(parcel_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);

-- =====================================================================
-- VIEWS (Reporting & Power BI Integration)
-- =====================================================================

-- View 1: Pending parcels per hostel awaiting pickup
CREATE VIEW IF NOT EXISTS vw_pending_parcels AS
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

-- View 2: Daily parcel volume by hostel
CREATE VIEW IF NOT EXISTS vw_daily_parcel_volume AS
SELECT 
    DATE(p.received_at) AS log_date,
    h.name AS hostel_name,
    COUNT(p.id) AS total_parcels,
    SUM(CASE WHEN p.status = 'collected' THEN 1 ELSE 0 END) AS collected_parcels,
    SUM(CASE WHEN p.status IN ('received', 'notified') THEN 1 ELSE 0 END) AS pending_parcels
FROM parcels p
JOIN hostels h ON p.hostel_id = h.id
GROUP BY DATE(p.received_at), h.name;

-- View 3: Average pickup turnaround time
CREATE VIEW IF NOT EXISTS vw_avg_pickup_time AS
SELECT 
    h.name AS hostel_name,
    COUNT(p.id) AS completed_handovers,
    ROUND(AVG((JULIANDAY(p.collected_at) - JULIANDAY(p.received_at)) * 24), 2) AS avg_pickup_hours
FROM parcels p
JOIN hostels h ON p.hostel_id = h.id
WHERE p.status = 'collected' AND p.collected_at IS NOT NULL
GROUP BY h.name;

-- =====================================================================
-- TRIGGER: Automatically update parcel status upon Handover insertion
-- =====================================================================
CREATE TRIGGER IF NOT EXISTS trg_parcel_collected_after_handover
AFTER INSERT ON handovers
BEGIN
    UPDATE parcels 
    SET status = 'collected',
        collected_at = NEW.handover_time
    WHERE id = NEW.parcel_id;
END;
