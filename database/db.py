import os
import time
import pyodbc
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

pyodbc.pooling = True


def get_db_connection(max_retries=2, retry_delay=1):
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
        "Connection Timeout=30;"
    )

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            return pyodbc.connect(connection_string)

        except pyodbc.Error as e:
            last_error = e
            print(f"Azure SQL connection attempt {attempt} failed:", e)

            if attempt < max_retries:
                time.sleep(retry_delay)

    raise last_error