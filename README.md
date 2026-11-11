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
- **Azure SQL Database (`parceldesk-td/parceldesk-db`):** Connected via `pyodbc` using `AZURE_SQL_CONNECTION_STRING` (falls back automatically to SQLite when unset). 7 3NF tables, 3 views, indexes, and 1 handover trigger are active.
- **Azure Blob Storage (`parceldeskstore26`):** Configured with a private `parcel-photos` container (`LRS`), falling back to `static/uploads/` when cloud storage is unconfigured.
- **Core Workflows & Security:** Role-based login (`guard`, `student`, `warden`, `admin`) with salted password hashes, parcel logging, JSON notifications, SHA-256 hashed 15-minute single-use OTP handover inside an ACID transaction, parameterized SQL queries, and `audit_logs`.
- **UI & Automated Tests:** Carbon + Signal Orange UI (`templates/index.html`, `static/css/style.css`, `static/js/app.js`) and 7/7 passing tests (`tests/test_parceldesk.py`).

### Pending / Partial
- **Power BI `.pbix` Report:** SQL reporting views (`vw_pending_parcels`, `vw_daily_parcel_volume`, `vw_avg_pickup_time`), in-app warden KPIs, and `/api/analytics/powerbi-export` CSV export are live; standalone `.pbix` report file is not yet created.
- **Private Blob Image Viewing:** Uploading to the private `parcel-photos` container works; generating SAS tokens or an authenticated proxy endpoint to render private blob URLs in `<img>` tags is not yet added.

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

> Note: Pending seeded parcels can be handed over by logging in as `student1` or `student2` and clicking **Reveal / Refresh OTP** to get a fresh 6-digit code (or using initial seeded demo OTPs `482910` for `student1` / `739104` for `student2` within 15 minutes of seeding).

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
- **Azure SQL:** Run [`database/azure_sql_schema.sql`](database/azure_sql_schema.sql) (or the chunks in Azure Portal Query Editor) first, then run `python database/init_db.py` to seed demo rows if the tables are empty.

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
Runs 7 unit/integration tests covering guard/invalid auth, parcel logging with SHA-256 OTP and JSON notification, failed OTP attempt tracking, student OTP regeneration + atomic handover, analytics views/CSV export, and Azure SQL query/row normalization checks.

---

## 📊 DP-900 Data Classification

| Classification | Service | Details |
| :--- | :--- | :--- |
| **Structured** | Azure SQL Database (or SQLite locally) | 3NF tables (`users`, `hostels`, `students`, `parcels`, `notifications`, `handovers`, `audit_logs`), keys, constraints, views, indexes, trigger. |
| **Semi-Structured** | JSON in `notifications.payload_json` | Dynamic courier arrival payloads with nested `recipient` and `channels` metadata. |
| **Unstructured** | Azure Blob Storage (`parcel-photos`, or `static/uploads/` locally) | Package condition images uploaded at the hostel gate. |

---

## 📁 Project Structure
```text
parceldesk-project/
├── app.py                      # Flask REST API, RBAC decorators, startup initialization
├── config.py                   # Environment-based configuration
├── requirements.txt            # Python dependencies (Flask, gunicorn, pyodbc, azure-storage-blob)
├── .env.example                # Environment variable template
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
    └── CLOUD_SECURITY.md       # Security controls overview
```

---

## 📚 Documentation
- **[Project Report, Threat Model & Security Checklist](docs/PROJECT_REPORT.md)**
- [T-SQL Reporting & Transaction Queries](database/queries.sql)
- [System Design](docs/SYSTEM_DESIGN.md) | [RDBMS Design](docs/RDBMS_DESIGN.md) | [DP-900 Data Services](docs/DP900_DATA_SERVICES.md) | [Cloud Security](docs/CLOUD_SECURITY.md)
