import os
import sys
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from dotenv import load_dotenv

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Load environment variables from .env in repository root
env_path = os.path.join(REPO_ROOT, ".env")
load_dotenv(dotenv_path=env_path)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "eukakanto_user")
DB_PASS = os.getenv("DB_PASS", "eukakanto_pass")
DB_NAME = os.getenv("DB_NAME", "eukakanto")


def get_connection(database=None):
    """
    Creates and returns a new raw PyMySQL database connection.
    Autocommit is False by default to allow transaction management.
    """
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=database or DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def execute_query(sql, params=None):
    """
    Executes a read query and returns all matching rows as dictionaries.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    finally:
        conn.close()


def execute_one(sql, params=None):
    """
    Executes a read query and returns a single row dictionary or None.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchone()
    finally:
        conn.close()


@contextmanager
def transaction():
    """
    Context manager for multi-statement atomic transactions.
    Commits on success; rolls back if any exception is raised.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection():
    """
    Tests connectivity to the database and prints DBMS version.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, DATABASE() AS db;")
            info = cursor.fetchone()
            print(f"[SUCCESS] Connected to {info['version']}. Current DB: {info['db']}")
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
