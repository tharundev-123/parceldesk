# ParcelDesk 📦

> **ParcelDesk lets hostel gate staff log incoming parcels, notify students, and hand them over securely using a one-time code.**

**Live Deployment (HTTPS):** [https://parceldesk-td-2026.azurewebsites.net](https://parceldesk-td-2026.azurewebsites.net)

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Azure SQL](https://img.shields.io/badge/Azure_SQL-Connected-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/products/azure-sql/)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(7%2F7)-10b981)]()

---

## 📌 Project Status

### Implemented & Deployed
- **Azure App Service Hosting (HTTPS):** Deployed at [https://parceldesk-td-2026.azurewebsites.net](https://parceldesk-td-2026.azurewebsites.net) on Linux Python 3.11 (`F1` Free tier) with HTTPS Only enabled (`gunicorn`).
- **Azure SQL Database (`parceldesk-td/parceldesk-db`):** Connected via `pyodbc` using `AZURE_SQL_CONNECTION_STRING` (falls back automatically to SQLite when unset). All 7 3NF tables, 3 views, indexes, and 1 handover trigger are active.
- **Azure Blob Storage (`parceldeskstore26`):** Configured with a private `parcel-photos` container (`LRS`), falling back to `static/uploads/` when cloud storage is unconfigured.
- **Power BI Analytics Report (`parceldesk-analytics.pbix`):** Done — saved in the repository root alongside exported view CSVs in `analytics/`, live SQL reporting views (`vw_pending_parcels`, `vw_daily_parcel_volume`, `vw_avg_pickup_time`), in-app warden KPIs, and `/api/analytics/powerbi-export` CSV download.
- **Core Workflows & Security:** Role-based login (`guard`, `student`, `warden`, `admin`) with salted password hashes, parcel logging, JSON notifications, SHA-256 hashed 15-minute single-use OTP handover inside an ACID transaction (only SHA-256 hashed OTPs are stored in the `parcels` table, and the plain OTP is shown once at parcel logging), parameterized SQL queries, and `audit_logs`.
- **UI & Automated Tests:** Carbon + Signal Orange UI (`templates/index.html`, `static/css/style.css`, `static/js/app.js`) and 7/7 passing tests (`tests/test_parceldesk.py`).

---

## 🌟 Problem Statement & Target Users
Hostel parcels are traditionally recorded in paper registers at the security gate. Students often remain unaware when packages arrive, parcels get misplaced or claimed by the wrong person, and guards have no verifiable proof of handover.

**ParcelDesk** digitizes the lifecycle for three user groups:
1. **Hostel Gate Staff (`guard`):** Log incoming packages with tracking number, courier, student, and condition photo, resend alerts, and verify student OTPs at handover.
2. **Students (`student`):** Track delivery status (`received` ➔ `notified` ➔ `collected`), view notification JSON details, and reveal or regenerate their 6-digit collection OTP.
3. **Hostel Wardens & Admins (`warden`, `admin`):** Monitor pending parcels per hostel, inspect average pickup turnaround, export the Power BI CSV dataset, and review security audit logs.

---

## 👥 Test Logins (Seed Data)

Use the **Operational Role** selector in the sidebar or authenticate via `/api/login` using the seeded accounts from [`database/init_db.py`](database/init_db.py):

| Role | Username | Password | Profile / Notes |
| :--- | :--- | :--- | :--- |
| **Guard** | `guard1` | `guard123` | Rajesh Kumar (Gate Staff) — logs parcels & verifies OTPs |
| **Student** | `student1` | `student123` | Rahul Verma (`2024CS101`, Boys Hostel 1, Room 204) |
| **Student** | `student2` | `student123` | Priya Patel (`2024EC205`, Girls Hostel 1, Room 112) |
| **Student** | `student3` | `student123` | Amit Singh (`2024ME310`, Boys Hostel 2, Room 301) |
| **Warden** | `warden1` | `warden123` | Dr. Ananya Sharma (Chief Warden) — analytics & audit logs |
| **Admin** | `admin` | `admin123` | System Administrator — full access |

> To test an OTP handover on any active parcel, sign in as the matching student and click **Reveal / Refresh OTP** to generate a fresh 6-digit code, then sign in as `guard1` and submit that code in **Verify Handover (OTP)**.

---

## 🚀 Local Setup Steps

### 1. Clone & Install Dependencies
```powershell
git clone https://github.com/tharundev-123/parceldesk.git
cd parceldesk

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
- Leave `AZURE_SQL_CONNECTION_STRING` and `AZURE_STORAGE_CONNECTION_STRING` empty to run locally with **SQLite** (`database/parceldesk.db`) and local upload storage (`static/uploads/`).
- Set `AZURE_SQL_CONNECTION_STRING` (ODBC Driver 18 format) and `AZURE_STORAGE_CONNECTION_STRING` in `.env` to connect to Azure SQL and Azure Blob Storage.

### 3. Initialize & Seed Database
- **Local SQLite:** Creates tables, views, indexes, trigger, and seeds demo data:
  ```powershell
  python database/init_db.py
  ```
- **Azure SQL:** Run [`database/azure_sql_schema.sql`](database/azure_sql_schema.sql) (or the portal chunks) first, then run `python database/init_db.py` to seed demo rows if the tables are empty.

### 4. Run Locally
```powershell
python app.py
```
Open **`http://127.0.0.1:5000`**.

---

## 🧪 Running Automated Tests
```powershell
python -m unittest tests/test_parceldesk.py -v
```
Runs 7 unit/integration tests against an isolated SQLite test database and mocked Azure branches, covering guard/invalid auth, parcel logging with SHA-256 OTP and JSON notification, failed OTP attempt tracking, student OTP regeneration + atomic handover, analytics views/CSV export, and Azure SQL query/row normalization checks.

---

## 📊 DP-900 Data Classification

| Classification | Service | Details |
| :--- | :--- | :--- |
| **Structured** | Azure SQL Database (or SQLite locally) | 3NF tables (`users`, `hostels`, `students`, `parcels`, `notifications`, `handovers`, `audit_logs`), keys, constraints, views, indexes, trigger. |
| **Semi-Structured** | JSON in `notifications.payload_json` | Dynamic courier arrival payloads with nested `recipient` and `channels` metadata. |
| **Unstructured** | Azure Blob Storage (`parcel-photos` private container, or `static/uploads/` locally) | Package condition images uploaded at the hostel gate. |

---

## ⚠️ Known Limitations and Future Work

1. **Private Blob Photo Display:** Parcel photos are uploaded to a private `parcel-photos` container in Azure Blob Storage, and the code saves the plain blob URL. Without SAS tokens or a backend image-proxy route, the browser cannot load those private blob URLs directly inside `<img>` tags yet.
2. **No CSRF Tokens or Login Rate Limiting:** State-changing POST requests rely on `SameSite=Lax` cookies instead of explicit CSRF tokens, and `/api/login` logs failed attempts without throttling or locking out repeated guesses.
3. **Demo Login Shortcuts and Seed Passwords:** The sidebar demo switcher, auto-login as `guard1`, and seeded default passwords are included for classroom demonstration only and must be removed or rotated before real production use.
4. **`GET /api/students` Permissions:** The `/api/students` endpoint currently requires only `@login_required`, so any signed-in student can query the student list. It should be restricted with `@roles_required("guard", "warden", "admin")`.
5. **File Upload Size and Content Checks:** Uploaded photos are checked by filename extension and sanitized with `secure_filename()`, but there is no `MAX_CONTENT_LENGTH` file size cap or image magic-byte/MIME inspection yet.
6. **CORS and Session Cookie Hardening:** `CORS(app, supports_credentials=True)` uses permissive default origins, and `SESSION_COOKIE_SECURE` / `PERMANENT_SESSION_LIFETIME` are not explicitly set in `config.py` so local HTTP development still works. Both should be tightened for production.
7. **No Azure SQL Serverless Wake-Up Retry:** `pyodbc.connect()` does not retry automatically if a paused Azure SQL Serverless database takes longer than the connection timeout to wake up on the first request.
8. **Plain OTP Visibility at Logging:** `POST /api/parcels` returns the generated plain OTP once in its response at parcel logging (so the guard receives it in the API response). In a production system, the plain OTP would be delivered directly to the student via SMS or email and never shown to the guard.
9. **Unpinned Dependency Versions:** `requirements.txt` uses `>=` minimum version constraints instead of exact `==` pins.

---

## 📁 Project Structure
```text
parceldesk-project/
├── app.py                      # Flask REST API, RBAC decorators, startup initialization
├── config.py                   # Environment-based configuration
├── requirements.txt            # Python dependencies (Flask, gunicorn, pyodbc, azure-storage-blob)
├── parceldesk-analytics.pbix   # Power BI Desktop analytics report
├── .env.example                # Environment variable template
├── analytics/
│   ├── POWERBI_STEPS.md        # Step-by-step guide to build the Power BI report
│   ├── vw_avg_pickup_time.csv  # Exported view data
│   ├── vw_daily_parcel_volume.csv
│   └── vw_pending_parcels.csv
├── database/
│   ├── db.py                   # Azure SQL / SQLite connection, row normalization, SCOPE_IDENTITY helper
│   ├── sqlite_schema.sql       # SQLite 3NF DDL
│   ├── azure_sql_schema.sql    # Azure SQL (T-SQL) DDL
│   ├── queries.sql             # T-SQL JOIN, GROUP BY/HAVING, subquery, view, and transaction queries
│   └── init_db.py              # Schema setup & demo data seeder
├── services/
│   ├── auth_service.py         # Password hashing, login verification, audit log writer
│   ├── parcel_service.py       # Parcel logging, OTP hashing/expiry, ACID handover transaction
│   ├── storage_service.py      # Azure Blob upload with local upload fallback
│   ├── notification_service.py # JSON payload generation & persistence
│   └── analytics_service.py    # KPI queries, SQL view wrappers, Power BI CSV export
├── static/
│   ├── css/style.css           # Carbon + Signal Orange theme
│   ├── js/app.js               # Role views, filtering, OTP countdown, drawers/modals
│   └── uploads/                # Local fallback upload directory
├── templates/index.html        # Single-page portal UI
├── tests/test_parceldesk.py    # 7 automated tests
└── docs/
    ├── PROJECT_REPORT.md       # Full project report, threat model, security checklist & credits
    ├── SYSTEM_DESIGN.md        # 3-tier architecture & trade-offs
    ├── RDBMS_DESIGN.md         # 3NF design & ERD
    ├── DP900_DATA_SERVICES.md  # DP-900 data classification
    ├── CLOUD_SECURITY.md       # Security controls overview
    └── screenshots/            # Azure, live HTTPS site, and Power BI screenshots
```

---

## 📚 Documentation
- **[Project Report, Threat Model & Security Checklist](docs/PROJECT_REPORT.md)**
- [T-SQL Reporting & Transaction Queries](database/queries.sql)
- [System Design](docs/SYSTEM_DESIGN.md) | [RDBMS Design](docs/RDBMS_DESIGN.md) | [DP-900 Data Services](docs/DP900_DATA_SERVICES.md) | [Cloud Security](docs/CLOUD_SECURITY.md)
