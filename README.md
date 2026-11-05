# ParcelDesk 📦

> **ParcelDesk lets hostel gate staff log incoming parcels, notify students, and hand them over securely using a one-time code.**

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Azure SQL](https://img.shields.io/badge/Azure_SQL-DP--900-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/products/azure-sql/)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(6%2F6)-10b981)]()

---

## 📌 Project Status

Current development status: **In progress** (college project progress update)

### What is done
- **3NF Relational Database**: Tables, primary/foreign keys, check constraints, indexes, views (`vw_pending_parcels`, `vw_daily_parcel_volume`, `vw_avg_pickup_time`), trigger (`trg_parcel_collected_after_handover`), and atomic transaction handling.
- **Authentication & RBAC**: Role-based access control for guard, student, warden, and admin with salted password hashing (PBKDF2/scrypt).
- **Parcel Entry**: Gate staff parcel logging with student selection, courier, tracking number, condition photo, and remarks.
- **Notifications & Tracking**: Semi-structured JSON notification payloads stored in database and in-app lifecycle tracking (Received ➔ Notified ➔ Collected).
- **Secure OTP Handover**: 6-digit single-use OTP, SHA-256 hashed in database, 15-minute TTL, 3-attempt rate limit, verified and released inside an atomic ACID transaction.
- **Security & Integrity**: 100% parameterized SQL queries, file upload extension validation, secrets kept in `.env` (git-ignored), and audit log ledger for all key actions.
- **Frontend UI/UX**: Carbon + Signal Orange technical logistics console with collapsible sidebar, multi-criteria filtering, and photo viewer modal.
- **Automated Tests**: Unit and integration test suite passing 6/6 tests (`tests/test_parceldesk.py`).

### What is partial
- **Azure SQL Database**: T-SQL schema script (`database/azure_sql_schema.sql`) and `pyodbc` connection code in `database/db.py` are written. The app currently runs on local SQLite; Azure SQL instance is not yet provisioned.
- **Azure Blob Storage**: Blob upload code with `BlobServiceClient` is implemented in `services/storage_service.py` with automatic local fallback. Currently runs on local disk fallback (`static/uploads/`) since cloud credentials are not yet configured.
- **Power BI / Analytics**: SQL reporting views, in-app warden dashboard KPIs, hostel distribution bars, and CSV dataset export endpoint (`/api/analytics/powerbi-export`) are working. The standalone Power BI `.pbix` report file is not yet created.

### What is not started
- **Azure App Service Deployment with HTTPS**: Application currently runs on local development server (`http://127.0.0.1:5000`). Cloud hosting on Azure App Service and HTTPS certificates are not yet started.

---

## 🌟 Problem Statement & Target Users
Hostel parcels are traditionally recorded in paper registers at the security gate. Students often remain unaware when packages arrive, parcels get misplaced or claimed by the wrong person, and guards have no verifiable proof of handover. 

**ParcelDesk** digitizes the entire lifecycle:
1. **Hostel Gate Staff / Guards**: Rapidly log incoming packages, capture parcel condition photos, and perform verified handovers.
2. **Students**: Receive instant notification alerts, track package status (Received ➔ Notified ➔ Collected), view package condition photos, and present a single-use OTP.
3. **Hostel Wardens & Admins**: Monitor pending parcel shelf occupancy, evaluate average pickup latency, analyze daily courier volumes, and review the security audit trail.

---

## 🏗️ System Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        3-TIER SYSTEM ARCHITECTURE                      │
├────────────────────┬─────────────────────────────┬─────────────────────┤
│ 1. PRESENTATION    │ 2. APPLICATION (REST API)   │ 3. DATA TIER        │
├────────────────────┼─────────────────────────────┼─────────────────────┤
│ • HTML5, CSS3, JS  │ • Python 3 (Flask)          │ • Azure SQL DB (3NF)│
│ • Guard Console    │ • Session Auth & RBAC       │ • Azure Blob Storage│
│ • Student Portal   │ • SHA-256 Hashed OTP Engine │ • JSON Notifications│
│ • Warden Analytics │ • ACID Transaction Handover │ • Power BI DirectQ  │
└────────────────────┴─────────────────────────────┴─────────────────────┘
```

- **Frontend**: Responsive Single-Page Application (HTML5, Modern CSS Glassmorphism/Cards, Vanilla JavaScript).
- **Backend**: Python 3 with Flask REST API.
- **Relational Database**: Azure SQL Database / SQLite 3NF Schema with 6 core tables, 3 reporting views, triggers, and indexes.
- **Object Storage**: Azure Blob Storage (with automated local fallback for offline development).
- **Security**: Cryptographic password hashing (PBKDF2/scrypt), single-use SHA-256 hashed OTPs with 15-minute TTL, parameterized queries, and audit logging.

---

## 🚀 Quick Start Guide

### 1. Clone & Set Up Environment
```powershell
# Navigate to project root
cd "parceldesk-project"

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize and Seed Database
Initializes the 3NF relational schema, views, triggers, indexes, and pre-populates sample hostels, students, and active parcels:
```powershell
python database/init_db.py
```

### 3. Run the ParcelDesk Server
```powershell
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 👥 Demo Logins & Roles

For immediate demonstration, ParcelDesk includes an **Instant Demo Switcher** bar at the top of the interface:

| Role | Username | Password | Context | Active Demo OTP |
| :--- | :--- | :--- | :--- | :--- |
| **Gate Guard** | `guard1` | `guard123` | Gate Security Staff (Logs & Handovers) | — |
| **Student 1** | `student1` | `student123` | Rahul Verma (Room 204, Boys Hostel 1) | `482910` |
| **Student 2** | `student2` | `student123` | Priya Patel (Room 112, Girls Hostel 1) | `739104` |
| **Hostel Warden** | `warden1` | `warden123` | Dr. Ananya Sharma (Analytics & Capacity)| — |
| **System Admin** | `admin` | `admin123` | IT Administrator (Full RBAC Access) | — |

---

## 🧪 Running Automated Tests
ParcelDesk comes with a comprehensive automated test suite testing RBAC authentication, parcel ingestion, OTP hashing, failed attempts brute-force locking, atomic handover transactions, and analytical views:

```powershell
python -m unittest tests/test_parceldesk.py
```
*Result: 6 tests executed in under 2 seconds (100% pass rate).*

---

## 📊 DP-900 Data Classification & Azure Services

| Classification | Storage Service | Implementation Details |
| :--- | :--- | :--- |
| **Structured Data** | **Azure SQL Database** | 3NF normalized tables (`users`, `hostels`, `students`, `parcels`, `notifications`, `handovers`), constraints, views, and indexes. |
| **Semi-Structured Data** | **JSON Payloads in SQL** | Flexible courier event logs and recipient metadata stored in `notifications.payload_json`. |
| **Unstructured Data** | **Azure Blob Storage** | Physical parcel condition photographs stored in the `parcel-photos` container. |

### Power BI Report Features
- **Daily Parcel Volume**: Aggregated parcel intake by date and hostel block.
- **Average Pickup Turnaround**: Calculated duration from gate arrival to verified handover.
- **Pending Backlog per Hostel**: Live count of uncollected packages occupying gate storage space.
- **One-Click Export**: Wardens can download the analytical dataset directly via the **"Export Power BI Dataset (CSV)"** button (`/api/analytics/powerbi-export`).

---

## 📁 Project Directory Structure
```
parceldesk-project/
├── app.py                      # Flask application entrypoint & REST API routes
├── config.py                   # App configuration & Azure cloud credentials
├── requirements.txt            # Python dependencies
├── .env.example                # Template for cloud environment variables
├── database/
│   ├── db.py                   # Database connection & transaction abstraction
│   ├── sqlite_schema.sql       # SQLite 3NF DDL (Tables, Views, Indexes, Trigger)
│   ├── azure_sql_schema.sql    # Azure SQL (T-SQL) DDL for cloud deployment
│   └── init_db.py              # Database initialization & demo seed script
├── services/
│   ├── auth_service.py         # Authentication, password hashing, and audit logging
│   ├── parcel_service.py       # Parcel ingestion, OTP hashing, and ACID handover
│   ├── storage_service.py      # Azure Blob Storage + local fallback
│   ├── notification_service.py # Semi-structured JSON notification dispatch
│   └── analytics_service.py    # KPI aggregations & Power BI dataset exporter
├── static/
│   ├── css/
│   │   └── style.css           # Modern, responsive UI design
│   ├── js/
│   │   └── app.js             # Client logic, OTP countdown, dynamic views
│   └── uploads/                # Local storage for parcel condition photos
├── templates/
│   └── index.html              # Single-page dashboard (Guard, Student, Warden)
├── tests/
│   └── test_parceldesk.py      # Automated unit & integration test suite
└── docs/
    ├── SYSTEM_DESIGN.md        # 3-Tier Architecture, API specs, Trade-offs
    ├── RDBMS_DESIGN.md         # 3NF Schema, ERD, ACID Transactions, Views
    ├── DP900_DATA_SERVICES.md  # Structured, Semi-structured, Unstructured breakdown
    └── CLOUD_SECURITY.md       # RBAC, Key Vault, TLS, Hashed OTPs & Audit Logs
```

---

## 📚 Technical Documentation
Detailed academic documentation is provided in the `docs/` folder:
- [System Design Document](docs/SYSTEM_DESIGN.md)
- [RDBMS & Database Schema Design](docs/RDBMS_DESIGN.md)
- [Azure Data Services (DP-900) Architecture](docs/DP900_DATA_SERVICES.md)
- [Cloud Security & Compliance Guide](docs/CLOUD_SECURITY.md)
