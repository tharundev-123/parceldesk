-- =====================================================================
-- ParcelDesk: T-SQL Reporting & Transaction Queries (Azure SQL)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. JOIN Query 1: Full parcel ledger across parcels, students, users, hostels
-- ---------------------------------------------------------------------
SELECT
    p.id AS parcel_id,
    p.tracking_number,
    p.courier_name,
    p.status,
    p.received_at,
    u_student.full_name AS student_name,
    s.student_roll_no,
    h.code AS hostel_code,
    h.name AS hostel_name,
    s.room_no,
    u_guard.full_name AS logged_by_guard
FROM dbo.parcels p
INNER JOIN dbo.students s ON p.student_id = s.id
INNER JOIN dbo.users u_student ON s.user_id = u_student.id
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
INNER JOIN dbo.users u_guard ON p.logged_by_guard_id = u_guard.id
ORDER BY p.received_at DESC;

-- ---------------------------------------------------------------------
-- 2. JOIN Query 2: Pending parcels awaiting student collection
-- ---------------------------------------------------------------------
SELECT
    p.tracking_number,
    p.courier_name,
    p.status,
    u.full_name AS student_name,
    s.student_roll_no,
    s.phone AS student_phone,
    h.name AS hostel_name,
    s.room_no,
    DATEDIFF(MINUTE, p.received_at, SYSUTCDATETIME()) AS minutes_waiting
FROM dbo.parcels p
INNER JOIN dbo.students s ON p.student_id = s.id
INNER JOIN dbo.users u ON s.user_id = u.id
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
WHERE p.status IN ('received', 'notified')
ORDER BY p.received_at ASC;

-- ---------------------------------------------------------------------
-- 3. JOIN Query 3: Completed handover proof & turnaround hours
-- ---------------------------------------------------------------------
SELECT
    p.tracking_number,
    p.courier_name,
    u_student.full_name AS student_name,
    s.student_roll_no,
    h.code AS hostel_code,
    u_guard.full_name AS verified_by_guard,
    p.received_at,
    ho.handover_time,
    CAST(DATEDIFF(MINUTE, p.received_at, ho.handover_time) / 60.0 AS DECIMAL(6, 2)) AS pickup_hours,
    ho.notes
FROM dbo.parcels p
INNER JOIN dbo.students s ON p.student_id = s.id
INNER JOIN dbo.users u_student ON s.user_id = u_student.id
INNER JOIN dbo.hostels h ON p.hostel_id = h.id
INNER JOIN dbo.handovers ho ON p.id = ho.parcel_id
INNER JOIN dbo.users u_guard ON ho.verified_by_guard_id = u_guard.id
ORDER BY ho.handover_time DESC;

-- ---------------------------------------------------------------------
-- 4. GROUP BY with HAVING: Hostels with at least 1 pending parcel
-- ---------------------------------------------------------------------
SELECT
    h.code AS hostel_code,
    h.name AS hostel_name,
    COUNT(p.id) AS pending_parcel_count
FROM dbo.hostels h
INNER JOIN dbo.parcels p ON h.id = p.hostel_id
WHERE p.status IN ('received', 'notified')
GROUP BY h.code, h.name
HAVING COUNT(p.id) >= 1
ORDER BY pending_parcel_count DESC;

-- ---------------------------------------------------------------------
-- 5. Subquery: Students who currently have uncollected parcels at the gate
-- ---------------------------------------------------------------------
SELECT
    s.student_roll_no,
    u.full_name AS student_name,
    u.email,
    h.code AS hostel_code,
    s.room_no
FROM dbo.students s
INNER JOIN dbo.users u ON s.user_id = u.id
INNER JOIN dbo.hostels h ON s.hostel_id = h.id
WHERE s.id IN (
    SELECT p.student_id
    FROM dbo.parcels p
    WHERE p.status IN ('received', 'notified')
)
ORDER BY s.student_roll_no ASC;

-- ---------------------------------------------------------------------
-- 6. SELECT from all 3 reporting views
-- ---------------------------------------------------------------------
SELECT * FROM dbo.vw_pending_parcels ORDER BY received_at DESC;

SELECT * FROM dbo.vw_daily_parcel_volume ORDER BY log_date DESC;

SELECT * FROM dbo.vw_avg_pickup_time ORDER BY avg_pickup_hours ASC;

-- ---------------------------------------------------------------------
-- 7. Transaction Example: Atomic OTP verification and parcel handover
-- ---------------------------------------------------------------------
DECLARE @ParcelId INT = 1;
DECLARE @GuardUserId INT = 1;
DECLARE @SubmittedOtpHash NVARCHAR(64) = 'replace_with_sha256_otp_hash';
DECLARE @HandoverNotes NVARCHAR(200) = 'Verified college ID and 6-digit OTP';

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @StudentId INT;
    DECLARE @CurrentStatus NVARCHAR(20);
    DECLARE @StoredOtpHash NVARCHAR(64);
    DECLARE @OtpExpiry DATETIME2;
    DECLARE @OtpAttempts INT;

    SELECT
        @StudentId = student_id,
        @CurrentStatus = status,
        @StoredOtpHash = otp_hash,
        @OtpExpiry = otp_expiry,
        @OtpAttempts = otp_attempts
    FROM dbo.parcels WITH (UPDLOCK, ROWLOCK)
    WHERE id = @ParcelId;

    IF @StudentId IS NULL
        THROW 50001, 'Parcel not found.', 1;

    IF @CurrentStatus = 'collected'
        THROW 50002, 'Parcel has already been collected.', 1;

    IF @OtpAttempts >= 3
        THROW 50003, 'Maximum OTP verification attempts exceeded.', 1;

    IF @OtpExpiry IS NULL OR SYSUTCDATETIME() > @OtpExpiry
        THROW 50004, 'OTP has expired.', 1;

    IF @StoredOtpHash IS NULL OR @StoredOtpHash <> @SubmittedOtpHash
        THROW 50005, 'Invalid OTP code.', 1;

    -- Insert handover proof (fires trg_parcel_collected_after_handover)
    INSERT INTO dbo.handovers (
        parcel_id, student_id, verified_by_guard_id, otp_verified_hash, handover_time, notes
    )
    VALUES (
        @ParcelId, @StudentId, @GuardUserId, @SubmittedOtpHash, SYSUTCDATETIME(), @HandoverNotes
    );

    -- Clear single-use OTP hash and confirm collected status
    UPDATE dbo.parcels
    SET status = 'collected',
        collected_at = SYSUTCDATETIME(),
        otp_hash = NULL
    WHERE id = @ParcelId;

    -- Write compliance audit record
    INSERT INTO dbo.audit_logs (user_id, action, details, created_at)
    VALUES (
        @GuardUserId,
        'PARCEL_HANDOVER_COMPLETED',
        CONCAT('Parcel ', @ParcelId, ' verified and handed over via transaction.'),
        SYSUTCDATETIME()
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
