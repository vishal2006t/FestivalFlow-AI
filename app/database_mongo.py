"""MongoDB integration and non-destructive sync service for FestivalFlow AI.

Supports:
- Safe connection testing using MONGODB_URI.
- Accurate connection status reporting without leaking connection string secrets.
- Non-destructive synchronization/migration from primary SQLite database to MongoDB.
- Collection indexing and data integrity verification.
- Zero-downtime coexistence: SQLite remains operational primary default until target is verified.
"""

import os
import sys
import time
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("festivalflow.database_mongo")

TABLE_COLLECTIONS = [
    "users", "depots", "buses", "drivers", "schedules", "stops", "routes",
    "events", "bus_telematics", "camera_configs", "crowd_readings",
    "alerts_and_recommendations", "driver_notifications", "driver_reports",
    "audit_logs", "recalculation_history"
]


def sanitize_uri(uri: str) -> str:
    """Mask password and user credentials from a MongoDB URI for safe logging."""
    if not uri:
        return ""
    try:
        parsed = urlparse(uri)
        if parsed.password:
            sanitized_netloc = f"{parsed.username}:*****@{parsed.hostname}"
            if parsed.port:
                sanitized_netloc += f":{parsed.port}"
            return uri.replace(parsed.netloc, sanitized_netloc)
        return uri
    except Exception:
        return "mongodb://[sanitized-connection-string]"


def get_mongodb_uri() -> str:
    """Read MONGODB_URI from environment."""
    return os.environ.get("MONGODB_URI", "").strip()


def test_mongodb_connection(uri: Optional[str] = None) -> Dict[str, Any]:
    """Test connectivity to MongoDB without risking application stability."""
    conn_uri = uri.strip() if uri is not None else get_mongodb_uri()
    
    if not conn_uri:
        return {
            "status": "NOT_CONFIGURED",
            "connected": False,
            "message": "MONGODB_URI is not configured in environment.",
            "sanitized_uri": None,
            "ping_ms": None,
            "collections": []
        }

    try:
        import pymongo
        from pymongo.errors import ConnectionFailure, ConfigurationError
    except ImportError:
        return {
            "status": "DEPENDENCY_MISSING",
            "connected": False,
            "message": "pymongo package is not installed.",
            "sanitized_uri": sanitize_uri(conn_uri),
            "ping_ms": None,
            "collections": []
        }

    start = time.perf_counter()
    try:
        client = pymongo.MongoClient(conn_uri, serverSelectionTimeoutMS=4000)
        # Verify ping
        client.admin.command('ping')
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        
        # Determine database name safely
        try:
            default_db = client.get_default_database()
            db_name = default_db.name if default_db is not None else "festivalflow"
        except Exception:
            db_name = "festivalflow"
        db = client[db_name]
        collections = db.list_collection_names()
        client.close()

        return {
            "status": "CONNECTED",
            "connected": True,
            "message": "MongoDB connection successfully established and verified.",
            "sanitized_uri": sanitize_uri(conn_uri),
            "database_name": db_name,
            "ping_ms": elapsed_ms,
            "collections": collections
        }
    except Exception as e:
        safe_err = str(e)
        # Strip potential password leak from error message if URI was embedded
        if "@" in safe_err and ":" in safe_err:
            safe_err = "Authentication or network connectivity error (credentials masked)."
        return {
            "status": "CONNECTION_FAILED",
            "connected": False,
            "message": f"MongoDB connection failed: {safe_err}",
            "sanitized_uri": sanitize_uri(conn_uri),
            "ping_ms": None,
            "collections": []
        }


def sync_sqlite_to_mongodb(
    sqlite_db_path: Optional[str] = None,
    mongo_uri: Optional[str] = None
) -> Dict[str, Any]:
    """Copy records from SQLite to MongoDB non-destructively and verify counts."""
    from app.database import get_db_path
    db_file = sqlite_db_path or get_db_path()
    
    test_result = test_mongodb_connection(mongo_uri)
    if not test_result["connected"]:
        return {
            "success": False,
            "error": test_result["message"],
            "test_result": test_result
        }

    import pymongo
    conn_uri = mongo_uri.strip() if mongo_uri else get_mongodb_uri()
    client = pymongo.MongoClient(conn_uri, serverSelectionTimeoutMS=5000)
    try:
        default_db = client.get_default_database()
        db_name = default_db.name if default_db is not None else "festivalflow"
    except Exception:
        db_name = "festivalflow"
    mongo_db = client[db_name]

    sqlite_conn = sqlite3.connect(db_file)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    report: Dict[str, Any] = {
        "database_name": db_name,
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tables_synced": {},
        "total_records_synced": 0
    }

    try:
        # Create indexes
        mongo_db["users"].create_index("username", unique=True)
        mongo_db["buses"].create_index("bus_number", unique=True)
        mongo_db["stops"].create_index("stop_id", unique=True)
        mongo_db["routes"].create_index("route_id", unique=True)
        mongo_db["schedules"].create_index([("bus_number", 1), ("departure_time", 1)])

        for tbl in TABLE_COLLECTIONS:
            # Check if SQLite table exists
            sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
            if not sqlite_cur.fetchone():
                continue

            sqlite_cur.execute(f"SELECT * FROM [{tbl}]")
            rows = sqlite_cur.fetchall()
            sqlite_count = len(rows)

            collection = mongo_db[tbl]
            inserted = 0

            for r in rows:
                doc = dict(r)
                # Map SQLite integer 'id' to 'sqlite_id'
                if "id" in doc:
                    doc["sqlite_id"] = doc["id"]
                # Upsert into MongoDB
                query = {"sqlite_id": doc["sqlite_id"]} if "sqlite_id" in doc else doc
                collection.replace_one(query, doc, upsert=True)
                inserted += 1

            mongo_count = collection.count_documents({})
            report["tables_synced"][tbl] = {
                "sqlite_count": sqlite_count,
                "mongo_count": mongo_count,
                "status": "VERIFIED" if mongo_count >= sqlite_count else "COUNT_MISMATCH"
            }
            report["total_records_synced"] += inserted

        report["success"] = True
        return report
    except Exception as e:
        report["success"] = False
        report["error"] = str(e)
        return report
    finally:
        sqlite_conn.close()
        client.close()


if __name__ == "__main__":
    # Command line testing utility
    if "--test" in sys.argv:
        res = test_mongodb_connection()
        print(f"MongoDB Test Result: {res['status']}")
        print(f"Connected: {res['connected']}")
        print(f"Message: {res['message']}")
    elif "--sync" in sys.argv:
        res = sync_sqlite_to_mongodb()
        print("MongoDB Sync Result:")
        print(res)
    else:
        print("Usage: python -m app.database_mongo [--test | --sync]")
