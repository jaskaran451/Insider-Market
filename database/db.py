import os
import time
import pyodbc
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Enables pyodbc connection pooling
pyodbc.pooling = True


def get_db_connection(max_retries=3, retry_delay=2):
    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DATABASE")
    username = os.getenv("AZURE_SQL_USERNAME")
    password = os.getenv("AZURE_SQL_PASSWORD")

    if not all([server, database, username, password]):
        raise RuntimeError("Azure SQL environment variables are missing.")

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER=tcp:{server},1433;"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=60;"
    )

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            conn = pyodbc.connect(connection_string)
            return conn

        except pyodbc.Error as e:
            last_error = e
            print(f"Azure SQL connection attempt {attempt} failed:", e)

            if attempt < max_retries:
                time.sleep(retry_delay)

    raise last_error


def warm_up_database():
    try:
        conn = get_db_connection(max_retries=2, retry_delay=2)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        print("Azure SQL warm-up successful.")

    except Exception as e:
        print("Azure SQL warm-up failed:", e)