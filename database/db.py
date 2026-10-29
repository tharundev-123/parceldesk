import sqlite3
import os
from contextlib import contextmanager
from config import Config

def get_connection():
    """Returns a database connection based on configured database type."""
    if Config.DB_TYPE == "azure_sql" and Config.AZURE_SQL_CONNECTION_STRING:
        try:
            import pyodbc
            conn = pyodbc.connect(Config.AZURE_SQL_CONNECTION_STRING)
            return conn
        except ImportError:
            raise RuntimeError("pyodbc is required for Azure SQL Database connection. Install pyodbc or switch to DB_TYPE=sqlite.")
    else:
        # SQLite connection (default for local development)
        os.makedirs(os.path.dirname(Config.SQLITE_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(Config.SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

@contextmanager
def get_db():
    """Context manager for acquiring a database connection and managing transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute_query(query, params=(), fetch_one=False, fetch_all=False, commit=False):
    """
    Safely executes a parameterized SQL query to eliminate SQL injection vulnerabilities.
    Returns single row, all rows, or lastrowid/rowcount.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch_one:
            row = cursor.fetchone()
            return dict(row) if row else None
        if fetch_all:
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        last_id = cursor.lastrowid
        row_count = cursor.rowcount
        return {"lastrowid": last_id, "rowcount": row_count}
