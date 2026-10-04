import os
from urllib.parse import quote_plus
import pyodbc
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    host = os.environ["SQLSERVER_HOST"]
    port = os.environ.get("SQLSERVER_PORT", "1433")
    database = os.environ["SQLSERVER_DATABASE"]
    driver = os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")

    trusted = os.environ.get("SQLSERVER_TRUSTED_CONNECTION", "no").lower() == "yes"

    if trusted:
        odbc_str = (
            f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};"
            f"Trusted_Connection=yes;TrustServerCertificate=yes;"
        )
        connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"
    else:
        user = os.environ["SQLSERVER_USER"]
        password = quote_plus(os.environ["SQLSERVER_PASSWORD"])
        driver_encoded = driver.replace(" ", "+")
        connection_url = (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
            f"?driver={driver_encoded}&TrustServerCertificate=yes"
        )

    return create_engine(connection_url)


def get_raw_connection(database: str = "master", autocommit: bool = True):
    host = os.environ["SQLSERVER_HOST"]
    port = os.environ.get("SQLSERVER_PORT", "1433")
    driver = os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    trusted = os.environ.get("SQLSERVER_TRUSTED_CONNECTION", "no").lower() == "yes"

    if trusted:
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};"
            f"Trusted_Connection=yes;TrustServerCertificate=yes;"
        )
    else:
        user = os.environ["SQLSERVER_USER"]
        password = os.environ["SQLSERVER_PASSWORD"]
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};"
            f"UID={user};PWD={password};TrustServerCertificate=yes;"
        )

    return pyodbc.connect(conn_str, autocommit=autocommit)


if __name__ == "__main__":
    engine = get_engine()
    with engine.connect() as conn:
        print("✅ Connected to SQL Server successfully.")