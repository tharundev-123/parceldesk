import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from config import Config


def is_azure_sql() -> bool:
    """Returns True when a non-empty AZURE_SQL_CONNECTION_STRING is configured."""
    conn_str = os.getenv("AZURE_SQL_CONNECTION_STRING")
    if conn_str is None:
        conn_str = Config.AZURE_SQL_CONNECTION_STRING
    return bool(conn_str and conn_str.strip())


def _normalize_value(val):
    """Normalizes database driver types (pyodbc datetime/date/Decimal) for JSON and app parity."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, Decimal):
        return float(val)
    return val


def row_to_dict(cursor, row):
    """Converts a sqlite3.Row or pyodbc.Row into a plain dictionary."""
    if row is None:
        return None
    if isinstance(row, dict):
        return {k: _normalize_value(v) for k, v in row.items()}
    columns = [col[0] for col in cursor.description]
    return {col: _normalize_value(val) for col, val in zip(columns, row)}


def get_connection():
    """Returns an Azure SQL connection if AZURE_SQL_CONNECTION_STRING is set, else SQLite."""
    if is_azure_sql():
        try:
            import pyodbc
            conn_str = os.getenv("AZURE_SQL_CONNECTION_STRING", Config.AZURE_SQL_CONNECTION_STRING).strip()
            return pyodbc.connect(conn_str)
        except ImportError:
            raise RuntimeError(
                "pyodbc is required for Azure SQL Database connection. "
                "Install pyodbc or leave AZURE_SQL_CONNECTION_STRING empty to use SQLite."
            )
    else:
        db_dir = os.path.dirname(Config.SQLITE_DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
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


def insert_and_get_id(cursor, query, params=()):
    """
    Executes an INSERT statement and returns the generated primary key ID.
    Uses SCOPE_IDENTITY() in the same batch on SQL Server (trigger-safe) and lastrowid on SQLite.
    """
    if is_azure_sql():
        clean_sql = query.strip().rstrip(";")
        batch_sql = f"SET NOCOUNT ON; {clean_sql}; SELECT CAST(SCOPE_IDENTITY() AS INT);"
        cursor.execute(batch_sql, params)
        while cursor.description is None:
            if not cursor.nextset():
                return None
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else None
    cursor.execute(query, params)
    return cursor.lastrowid


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
            return row_to_dict(cursor, row)
        if fetch_all:
            rows = cursor.fetchall()
            return [row_to_dict(cursor, r) for r in rows]
        last_id = getattr(cursor, "lastrowid", None)
        row_count = cursor.rowcount
        return {"lastrowid": last_id, "rowcount": row_count}
