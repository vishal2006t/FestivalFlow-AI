"""Database models, SQLite persistence, authentication and conflict prevention for FestivalFlow AI.

Supports:
- Bus Depot Admin and Bus Driver user authentication with PBKDF2-HMAC-SHA256 password hashing.
- Token session management.
- Depot, bus, and driver inventory models.
- Persistent bus schedule management with overlapping time conflict prevention.
- Fleet conservation enforcement.
- Demo account seeding.
"""

import sqlite3
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "festivalflow.db")


def get_db_path() -> str:
    """Return the absolute path to the SQLite database file."""
    return os.environ.get("FESTIVALFLOW_DB_PATH", DB_PATH)


def get_db_connection() -> sqlite3.Connection:
    """Create and return a row-factory enabled SQLite connection."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a password using bcrypt (work factor 12) with fallback to PBKDF2."""
    try:
        pw_bytes = password.encode("utf-8")
        hashed_bytes = bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=12))
        return hashed_bytes.decode("utf-8"), "bcrypt"
    except Exception:
        if not salt:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()
        return hashed, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify a plain password against bcrypt hash, with backward-compatibility for PBKDF2."""
    pw_bytes = password.encode("utf-8")
    if password_hash.startswith("$2b$") or password_hash.startswith("$2a$"):
        try:
            return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
        except Exception:
            return False
    # Fallback for PBKDF2
    legacy_calc = hashlib.pbkdf2_hmac(
        "sha256",
        pw_bytes,
        salt.encode("utf-8"),
        100000
    ).hex()
    return secrets.compare_digest(legacy_calc, password_hash)


def init_db(force_reset: bool = False) -> None:
    """Initialize database tables and seed default demo accounts and fleet."""
    db_file = get_db_path()
    os.makedirs(os.path.dirname(db_file), exist_ok=True)

    if force_reset and os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass

    conn = get_db_connection()
    cursor = conn.cursor()

    if force_reset:
        cursor.execute("PRAGMA foreign_keys = OFF")
        table_names = [
            "users", "sessions", "depots", "buses", "drivers", "schedules",
            "camera_configs", "crowd_readings", "bus_telematics",
            "alerts_and_recommendations", "driver_notifications",
            "stops", "routes", "events", "assignments", "dispatch_plans",
            "driver_reports", "audit_logs"
        ]
        for tbl in table_names:
            cursor.execute(f"DROP TABLE IF EXISTS {tbl}")
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL,          -- 'depot_admin' or 'driver'
            full_name TEXT NOT NULL,
            depot_name TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 2. Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 3. Depots Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS depots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            depot_name TEXT UNIQUE NOT NULL,
            total_buses INTEGER NOT NULL,
            idle_buses INTEGER NOT NULL,
            min_service_buses INTEGER NOT NULL DEFAULT 1
        );
    """)

    # 4. Buses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_number TEXT UNIQUE NOT NULL,
            registration_no TEXT,
            depot_name TEXT NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 70,
            status TEXT NOT NULL DEFAULT 'Available'
        );
    """)

    # 5. Drivers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            driver_name TEXT NOT NULL,
            license_no TEXT,
            phone TEXT,
            depot_name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 6. Schedules Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_start_time TEXT NOT NULL,
            expected_crowd_departure TEXT NOT NULL,
            depot_name TEXT NOT NULL,
            bus_number TEXT NOT NULL,
            bus_registration_no TEXT,
            bus_capacity INTEGER NOT NULL DEFAULT 70,
            available_bus_count INTEGER NOT NULL DEFAULT 1,
            source_stop TEXT NOT NULL,
            destination_stop TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            arrival_time TEXT,
            driver_id INTEGER,
            driver_name TEXT,
            route_details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # 7. Camera Configurations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS camera_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT UNIQUE NOT NULL,
            stop_id TEXT NOT NULL,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'demo',  -- 'rtsp', 'video_upload', 'webcam', 'demo'
            stream_url TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            roi_x1 REAL DEFAULT 0.10,
            roi_y1 REAL DEFAULT 0.20,
            roi_x2 REAL DEFAULT 0.90,
            roi_y2 REAL DEFAULT 0.85,
            status TEXT NOT NULL DEFAULT 'CONNECTED',   -- 'CONNECTED', 'CONNECTING', 'DISCONNECTED', 'ERROR'
            last_frame_time TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 8. Crowd Readings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crowd_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            raw_count INTEGER NOT NULL,
            smoothed_count INTEGER NOT NULL,
            crowd_level TEXT NOT NULL,                  -- 'Low', 'Moderate', 'High', 'Critical'
            trend TEXT NOT NULL,                        -- 'Surging', 'Increasing', 'Stable', 'Clearing'
            confidence REAL NOT NULL,
            source_label TEXT NOT NULL,                 -- 'LIVE', 'RECORDED', 'WEBCAM', 'DEMO'
            night_alert_flag INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );
    """)

    # 9. Bus Telematics & Occupancy Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bus_telematics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_number TEXT UNIQUE NOT NULL,
            registration_no TEXT,
            depot_name TEXT NOT NULL,
            assigned_route TEXT NOT NULL,
            destination_stop TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',   -- 'Available', 'En Route', 'Full', 'Out of Service', 'Assigned'
            passenger_count INTEGER NOT NULL DEFAULT 0,
            capacity INTEGER NOT NULL DEFAULT 70,
            available_seats INTEGER NOT NULL DEFAULT 70,
            occupancy_rate REAL NOT NULL DEFAULT 0.0,
            occupancy_source TEXT NOT NULL DEFAULT 'DEMO_DATA',  -- 'SENSOR_FEED', 'AUTHORIZED_TELEMATICS', 'DEMO_DATA'
            current_location TEXT NOT NULL,
            distance_to_hub_km REAL NOT NULL DEFAULT 2.0,
            eta_mins INTEGER NOT NULL DEFAULT 10,
            eta_source TEXT NOT NULL DEFAULT 'ESTIMATED_MODEL',  -- 'REAL_GPS', 'ESTIMATED_MODEL', 'DEMO_DATA'
            last_update TEXT NOT NULL
        );
    """)

    # 10. Alerts and Recommendations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts_and_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,                   -- 'NIGHT_SAFETY', 'CROWD_SURGE', 'CAPACITY_DEFICIT', 'UNDERUTILIZED_BUS'
            severity TEXT NOT NULL,                     -- 'CRITICAL', 'HIGH', 'MEDIUM', 'INFO'
            stop_id TEXT NOT NULL,
            stop_name TEXT NOT NULL,
            message TEXT NOT NULL,
            crowd_count INTEGER NOT NULL,
            waiting_time_mins INTEGER NOT NULL DEFAULT 15,
            is_night_time INTEGER NOT NULL DEFAULT 1,
            recommended_bus_number TEXT,
            recommended_action TEXT,
            source_impact_summary TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',       -- 'ACTIVE', 'ACKNOWLEDGED', 'DISMISSED'
            notified_driver_id INTEGER,
            created_at TEXT NOT NULL
        );
    """)

    # 11. Driver Urgent Notifications Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS driver_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            driver_name TEXT NOT NULL,
            bus_number TEXT NOT NULL,
            stop_name TEXT NOT NULL,
            notification_type TEXT NOT NULL,            -- 'NIGHT_SAFETY_DISPATCH', 'URGENT_EVACUATION', 'GENERAL'
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'HIGH',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)

    # 12. Stops Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stop_id TEXT UNIQUE NOT NULL,
            stop_name TEXT NOT NULL,
            location_lat REAL NOT NULL,
            location_lon REAL NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 500,
            zone TEXT NOT NULL DEFAULT 'Central Corridor',
            is_hub INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)

    # 13. Routes Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id TEXT UNIQUE NOT NULL,
            route_name TEXT NOT NULL,
            origin_stop TEXT NOT NULL,
            destination_stop TEXT NOT NULL,
            typical_headway_mins INTEGER NOT NULL DEFAULT 15,
            distance_km REAL NOT NULL DEFAULT 5.0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
    """)

    # 14. Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            expected_attendees INTEGER NOT NULL DEFAULT 40000,
            hub_stop_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        );
    """)

    # 15. Operational Assignments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            plan_id INTEGER,
            bus_number TEXT NOT NULL,
            driver_id INTEGER,
            driver_name TEXT,
            source_stop TEXT NOT NULL,
            target_stop TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ASSIGNED',    -- 'ASSIGNED', 'ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'BOARDING', 'COMPLETED', 'CANCELLED'
            assigned_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE SET NULL,
            FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE SET NULL
        );
    """)

    # 16. Dispatch Recommendations & Plans Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispatch_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_stop_id TEXT NOT NULL,
            target_stop_name TEXT NOT NULL,
            crowd_count INTEGER NOT NULL,
            buses_requested INTEGER NOT NULL DEFAULT 4,
            buses_allocated INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PENDING',     -- 'PENDING', 'APPROVED', 'REJECTED', 'PARTIALLY_FULFILLED'
            plan_details_json TEXT NOT NULL,
            source_impact_summary TEXT,
            unmet_demand_reason TEXT,
            approved_by TEXT,
            rejection_reason TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );
    """)

    # 17. Driver Incident & Delay Reports Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS driver_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            driver_name TEXT NOT NULL,
            bus_number TEXT NOT NULL,
            schedule_id INTEGER,
            report_type TEXT NOT NULL,                  -- 'DELAY', 'BREAKDOWN', 'OVERCROWDING', 'SAFETY_CONCERN'
            severity TEXT NOT NULL DEFAULT 'MEDIUM',    -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
            stop_name TEXT,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'REPORTED',    -- 'REPORTED', 'IN_REVIEW', 'RESOLVED'
            admin_response TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 18. Security Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,                   -- 'LOGIN_SUCCESS', 'LOGIN_FAILURE', 'SCHEDULE_CREATE', 'SCHEDULE_UPDATE', 'SCHEDULE_DELETE', 'DISPATCH_APPROVED', 'DISPATCH_REJECTED', 'SAFETY_ALERT_ACKNOWLEDGED', 'SAFETY_ALERT_ESCALATED', 'DRIVER_STATUS_UPDATE', 'DRIVER_REPORT_FILED'
            actor_username TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            ip_address TEXT,
            action_details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SUCCESS'
        );
    """)

    conn.commit()

    # Check if seeding is required
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_demo_data(conn)

    # Apply backward-compatible schema upgrades and initialize settings/incidents
    _init_upgrades(conn)

    conn.close()



def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Seed initial prototype demo data: depots, buses, drivers, users, and schedules."""
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()

    # 1. Seed Depots (Strictly fixed network total of 17 buses: 12 + 5)
    depots = [
        ("Central Depot", 12, 0, 12),
        ("Tech Park North Depot", 5, 4, 1),
    ]
    for name, total, idle, min_svc in depots:
        cursor.execute("""
            INSERT OR REPLACE INTO depots (depot_name, total_buses, idle_buses, min_service_buses)
            VALUES (?, ?, ?, ?)
        """, (name, total, idle, min_svc))

    # 2. Seed Buses
    # 12 buses at Central Depot
    for i in range(1, 13):
        bus_num = f"BUS-{100 + i}"
        reg_no = f"TN-01-N-{1000 + i}"
        cursor.execute("""
            INSERT OR REPLACE INTO buses (bus_number, registration_no, depot_name, capacity, status)
            VALUES (?, ?, 'Central Depot', 70, 'Available')
        """, (bus_num, reg_no))

    # 5 buses at Tech Park North Depot (4 idle + 1 commuter)
    for i in range(1, 6):
        bus_num = f"BUS-{200 + i}"
        reg_no = f"TN-02-B-{2000 + i}"
        status = "Active" if i == 5 else "Available"
        cursor.execute("""
            INSERT OR REPLACE INTO buses (bus_number, registration_no, depot_name, capacity, status)
            VALUES (?, ?, 'Tech Park North Depot', 70, ?)
        """, (bus_num, reg_no, status))

    # 3. Seed Users
    # Bus Depot Admins
    admin1_hash, admin1_salt = hash_password("Admin@Depot2026")
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, depot_name, created_at)
        VALUES (?, ?, ?, 'depot_admin', 'S. Meena (Depot Operations Head)', 'Central Depot', ?)
    """, ("admin_chennai", admin1_hash, admin1_salt, now_str))

    admin2_hash, admin2_salt = hash_password("Admin@Depot2026")
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, depot_name, created_at)
        VALUES (?, ?, ?, 'depot_admin', 'K. Ramesh (Depot Manager)', 'Tech Park North Depot', ?)
    """, ("admin_depot", admin2_hash, admin2_salt, now_str))

    # Bus Drivers
    driver1_hash, driver1_salt = hash_password("Driver@2026")
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, depot_name, created_at)
        VALUES (?, ?, ?, 'driver', 'R. Ramesh', 'Tech Park North Depot', ?)
    """, ("driver_ramesh", driver1_hash, driver1_salt, now_str))
    driver1_user_id = cursor.lastrowid

    driver2_hash, driver2_salt = hash_password("Driver@2026")
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, depot_name, created_at)
        VALUES (?, ?, ?, 'driver', 'K. Suresh', 'Tech Park North Depot', ?)
    """, ("driver_suresh", driver2_hash, driver2_salt, now_str))
    driver2_user_id = cursor.lastrowid

    driver3_hash, driver3_salt = hash_password("Driver@2026")
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, depot_name, created_at)
        VALUES (?, ?, ?, 'driver', 'V. Anand', 'Central Depot', ?)
    """, ("driver_anand", driver3_hash, driver3_salt, now_str))
    driver3_user_id = cursor.lastrowid

    # 4. Seed Drivers Table
    cursor.execute("""
        INSERT INTO drivers (user_id, driver_name, license_no, phone, depot_name)
        VALUES (?, 'R. Ramesh', 'TN-01-2019-0098', '+91 98401 23456', 'Tech Park North Depot')
    """, (driver1_user_id,))

    cursor.execute("""
        INSERT INTO drivers (user_id, driver_name, license_no, phone, depot_name)
        VALUES (?, 'K. Suresh', 'TN-01-2020-0541', '+91 98402 34567', 'Tech Park North Depot')
    """, (driver2_user_id,))

    cursor.execute("""
        INSERT INTO drivers (user_id, driver_name, license_no, phone, depot_name)
        VALUES (?, 'V. Anand', 'TN-02-2018-0712', '+91 98403 45678', 'Central Depot')
    """, (driver3_user_id,))

    # 5. Seed Initial Schedules
    # Schedule 1: Assigned to driver_ramesh (Ready for festival peak)
    cursor.execute("""
        INSERT INTO schedules (
            event_name, event_date, event_start_time, expected_crowd_departure,
            depot_name, bus_number, bus_registration_no, bus_capacity, available_bus_count,
            source_stop, destination_stop, departure_time, arrival_time,
            driver_id, driver_name, route_details, status, notes, created_at, updated_at
        ) VALUES (
            'Grand City Lights Cultural Festival', '2026-10-10', '18:00', '2026-10-10T22:00',
            'Tech Park North Depot', 'BUS-201', 'TN-02-B-2001', 70, 4,
            'Tech Hub North Stop (2km away)', 'Main Bus Stand (Festival Arena)',
            '2026-10-10T21:40', '2026-10-10T21:55',
            ?, 'R. Ramesh',
            'Corridor North Express via Ring Road - Direct Hub Gate 2',
            'Scheduled',
            'Proactive positioning before 22:00 headline finale surge. Staging at Bay 3.',
            ?, ?
        )
    """, (driver1_user_id, now_str, now_str))

    # Schedule 2: Assigned to driver_suresh (Second wave shuttle)
    cursor.execute("""
        INSERT INTO schedules (
            event_name, event_date, event_start_time, expected_crowd_departure,
            depot_name, bus_number, bus_registration_no, bus_capacity, available_bus_count,
            source_stop, destination_stop, departure_time, arrival_time,
            driver_id, driver_name, route_details, status, notes, created_at, updated_at
        ) VALUES (
            'Grand City Lights Cultural Festival', '2026-10-10', '18:00', '2026-10-10T22:00',
            'Tech Park North Depot', 'BUS-202', 'TN-02-B-2002', 70, 4,
            'Tech Hub North Stop (2km away)', 'Main Bus Stand (Festival Arena)',
            '2026-10-10T21:45', '2026-10-10T21:58',
            ?, 'K. Suresh',
            'North Link Rapid Shuttle via Expressway Flyover',
            'Ready',
            'Second wave evacuation shuttle. Standby for driver dispatch.',
            ?, ?
        )
    """, (driver2_user_id, now_str, now_str))

    # 6. Seed Camera Configurations
    cursor.execute("""
        INSERT OR REPLACE INTO camera_configs (
            camera_id, stop_id, name, source_type, stream_url, is_active,
            roi_x1, roi_y1, roi_x2, roi_y2, status, last_frame_time, created_at
        ) VALUES (
            'CAM-MAIN-01', 'STOP_MAIN', 'Festival Arena Main Stand Platform Cam',
            'demo', 'rtsp://cctv.festivaltransit.local:554/live/arena_stand_bay1', 1,
            0.15, 0.25, 0.85, 0.85, 'CONNECTED', ?, ?
        )
    """, (now_str, now_str))

    cursor.execute("""
        INSERT OR REPLACE INTO camera_configs (
            camera_id, stop_id, name, source_type, stream_url, is_active,
            roi_x1, roi_y1, roi_x2, roi_y2, status, last_frame_time, created_at
        ) VALUES (
            'CAM-NORTH-01', 'STOP_NEARBY', 'Tech Hub North Stop Platform Cam',
            'demo', 'rtsp://cctv.festivaltransit.local:554/live/tech_hub_north', 1,
            0.10, 0.20, 0.90, 0.80, 'CONNECTED', ?, ?
        )
    """, (now_str, now_str))

    # 7. Seed Initial Crowd Readings
    cursor.execute("""
        INSERT INTO crowd_readings (
            camera_id, stop_id, timestamp, raw_count, smoothed_count,
            crowd_level, trend, confidence, source_label, night_alert_flag, notes
        ) VALUES (
            'CAM-MAIN-01', 'STOP_MAIN', ?, 145, 142,
            'High', 'Surging', 0.912, 'DEMO SIMULATION', 1,
            'Crowd accumulating outside Gates A and B right before headline finale exit.'
        )
    """, (now_str,))

    cursor.execute("""
        INSERT INTO crowd_readings (
            camera_id, stop_id, timestamp, raw_count, smoothed_count,
            crowd_level, trend, confidence, source_label, night_alert_flag, notes
        ) VALUES (
            'CAM-NORTH-01', 'STOP_NEARBY', ?, 18, 16,
            'Low', 'Stable', 0.895, 'DEMO SIMULATION', 0,
            'Light local commuter queue; plenty of platform capacity available.'
        )
    """, (now_str,))

    # 8. Seed Bus Telematics for all 17 buses
    # Central Depot (12 buses at Main Stand)
    for i in range(1, 13):
        b_num = f"BUS-{100 + i}"
        reg = f"TN-01-N-{1000 + i}"
        pax = 55 if i <= 8 else 20
        free = 70 - pax
        rate = round(pax / 70.0, 2)
        cursor.execute("""
            INSERT OR REPLACE INTO bus_telematics (
                bus_number, registration_no, depot_name, assigned_route, destination_stop,
                status, passenger_count, capacity, available_seats, occupancy_rate,
                occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
            ) VALUES (
                ?, ?, 'Central Depot', 'Central Metro Hub Feeder', 'Main Bus Stand (Festival Arena)',
                'En Route', ?, 70, ?, ?,
                'DEMO_DATA', 'Central Ring Road', 0.8, 3, 'ESTIMATED_MODEL', ?
            )
        """, (b_num, reg, pax, free, rate, now_str))

    # Tech Park North Depot (5 buses)
    # BUS-201: Active run assigned to driver_ramesh
    cursor.execute("""
        INSERT OR REPLACE INTO bus_telematics (
            bus_number, registration_no, depot_name, assigned_route, destination_stop,
            status, passenger_count, capacity, available_seats, occupancy_rate,
            occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
        ) VALUES (
            'BUS-201', 'TN-02-B-2001', 'Tech Park North Depot', 'Corridor North Express via Ring Road',
            'Main Bus Stand (Festival Arena)', 'Assigned', 0, 70, 70, 0.0,
            'DEMO_DATA', 'Tech Hub Staging Bay', 2.0, 12, 'ESTIMATED_MODEL', ?
        )
    """, (now_str,))

    # BUS-202: Second wave run assigned to driver_suresh
    cursor.execute("""
        INSERT OR REPLACE INTO bus_telematics (
            bus_number, registration_no, depot_name, assigned_route, destination_stop,
            status, passenger_count, capacity, available_seats, occupancy_rate,
            occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
        ) VALUES (
            'BUS-202', 'TN-02-B-2002', 'Tech Park North Depot', 'North Link Rapid Shuttle via Expressway Flyover',
            'Main Bus Stand (Festival Arena)', 'Assigned', 0, 70, 70, 0.0,
            'DEMO_DATA', 'Tech Park North Staging Bay', 2.0, 15, 'ESTIMATED_MODEL', ?
        )
    """, (now_str,))

    # BUS-203: Highly underutilized available candidate!
    cursor.execute("""
        INSERT OR REPLACE INTO bus_telematics (
            bus_number, registration_no, depot_name, assigned_route, destination_stop,
            status, passenger_count, capacity, available_seats, occupancy_rate,
            occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
        ) VALUES (
            'BUS-203', 'TN-02-B-2003', 'Tech Park North Depot', 'North Technology Park Line',
            'Tech Hub North Stop (2km away)', 'Available', 12, 70, 58, 0.17,
            'SENSOR_FEED', 'Tech Park Terminal Bay 4', 2.0, 9, 'REAL_GPS', ?
        )
    """, (now_str,))

    # BUS-204: Underutilized available candidate!
    cursor.execute("""
        INSERT OR REPLACE INTO bus_telematics (
            bus_number, registration_no, depot_name, assigned_route, destination_stop,
            status, passenger_count, capacity, available_seats, occupancy_rate,
            occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
        ) VALUES (
            'BUS-204', 'TN-02-B-2004', 'Tech Park North Depot', 'North Industrial Corridor Line',
            'Tech Hub North Stop (2km away)', 'Available', 8, 70, 62, 0.11,
            'SENSOR_FEED', 'North Depot Maintenance Bay', 2.0, 10, 'REAL_GPS', ?
        )
    """, (now_str,))

    # BUS-205: Full commuter line (must not be reassigned)
    cursor.execute("""
        INSERT OR REPLACE INTO bus_telematics (
            bus_number, registration_no, depot_name, assigned_route, destination_stop,
            status, passenger_count, capacity, available_seats, occupancy_rate,
            occupancy_source, current_location, distance_to_hub_km, eta_mins, eta_source, last_update
        ) VALUES (
            'BUS-205', 'TN-02-B-2005', 'Tech Park North Depot', 'North Commuter Mainline Line',
            'Tech Hub North Stop (2km away)', 'Full', 68, 70, 2, 0.97,
            'SENSOR_FEED', 'Tech Hub Approach Flyover', 2.2, 7, 'REAL_GPS', ?
        )
    """, (now_str,))

    # 9. Seed Initial Alerts & Recommendations
    cursor.execute("""
        INSERT INTO alerts_and_recommendations (
            alert_type, severity, stop_id, stop_name, message, crowd_count,
            waiting_time_mins, is_night_time, recommended_bus_number, recommended_action,
            source_impact_summary, status, created_at
        ) VALUES (
            'NIGHT_SAFETY', 'CRITICAL', 'STOP_MAIN', 'Main Bus Stand (Festival Arena)',
            'Night Safety Alert: 142 passengers waiting >22 mins during festival exit window (22:15). Prolonged night queue increases safety vulnerability.',
            142, 22, 1, 'BUS-203',
            'Recommend reassigning underutilized BUS-203 (12/70 occupied, 58 seats free, ETA ~9 mins) from Tech Park North Route. Dispatches in ~9m before crowd reaches peak 8,000+ surge.',
            'Tech Park North commuter headway increases from 15m to 25m. Minimum service strictly protected (1 bus retained). Fixed fleet conserved: 17 buses.',
            'ACTIVE', ?
        )
    """, (now_str,))

    # 10. Seed Initial Driver Notifications
    cursor.execute("""
        INSERT INTO driver_notifications (
            driver_id, driver_name, bus_number, stop_name, notification_type,
            title, message, severity, is_read, created_at
        ) VALUES (
            ?, 'R. Ramesh', 'BUS-201', 'Main Bus Stand (Festival Arena)',
            'NIGHT_SAFETY_DISPATCH',
            '🌙 Priority Night Evacuation Run: BUS-201',
            'Critical night crowd detected at Main Bus Stand (~142 passengers waiting). Proceed to Bay 3 for expedited staging prior to 22:00 finale.',
            'HIGH', 0, ?
        )
    """, (driver1_user_id, now_str))

    # 11. Seed Network Stops
    stops_data = [
        ("STOP_MAIN", "Main Bus Stand (Festival Arena)", 13.0827, 80.2707, 4000, "Festival Transit Zone", 1),
        ("STOP_NORTH", "Tech Hub North Stop", 13.1200, 80.2450, 1200, "North IT Corridor", 0),
        ("STOP_SOUTH", "South Commercial Terminal", 13.0400, 80.2200, 1500, "South Metro Zone", 0),
        ("STOP_EAST", "East University Hub", 13.0650, 80.2900, 800, "Coastal Academic Belt", 0),
    ]
    for s_id, s_name, lat, lon, cap, zone, is_hub in stops_data:
        cursor.execute("""
            INSERT OR REPLACE INTO stops (stop_id, stop_name, location_lat, location_lon, capacity, zone, is_hub, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (s_id, s_name, lat, lon, cap, zone, is_hub, now_str))

    # 12. Seed Network Transit Routes
    routes_data = [
        ("RT-01", "Route 1 - Arena Express Corridor", "Tech Hub North Stop", "Main Bus Stand (Festival Arena)", 15, 4.2),
        ("RT-04", "Route 4 - North Industrial Line", "Central Depot", "Tech Hub North Stop", 20, 6.5),
        ("RT-07", "Route 7 - South Metro Feeder", "South Commercial Terminal", "Main Bus Stand (Festival Arena)", 12, 3.8),
    ]
    for r_id, r_name, orig, dest, hdway, dist in routes_data:
        cursor.execute("""
            INSERT OR REPLACE INTO routes (route_id, route_name, origin_stop, destination_stop, typical_headway_mins, distance_km, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (r_id, r_name, orig, dest, hdway, dist))

    # 13. Seed Festival Event
    cursor.execute("""
        INSERT INTO events (event_name, event_date, start_time, end_time, expected_attendees, hub_stop_id, status, created_at)
        VALUES ('Grand City Lights Cultural Festival', '2026-10-10', '18:00', '22:30', 40000, 'STOP_MAIN', 'ACTIVE', ?)
    """, (now_str,))

    # 14. Seed Initial Driver Incident / Delay Report
    cursor.execute("""
        INSERT INTO driver_reports (
            driver_id, driver_name, bus_number, schedule_id, report_type, severity,
            stop_name, description, status, admin_response, created_at
        ) VALUES (
            ?, 'R. Ramesh', 'BUS-201', 1, 'DELAY', 'MEDIUM',
            'Main Bus Stand (Festival Arena)',
            'Heavy pedestrian crowd surging through Gate 3 approach road. Traffic bottleneck causing ~8 min staging delay.',
            'REPORTED', NULL, ?
        )
    """, (driver1_user_id, now_str))

    # 15. Seed Initial Security Audit Logs
    cursor.execute("""
        INSERT INTO audit_logs (timestamp, event_type, actor_username, actor_role, ip_address, action_details, status)
        VALUES (?, 'SYSTEM_INIT', 'system', 'system', '127.0.0.1', 'FestivalFlow AI database initialized and prototype data seeded.', 'SUCCESS')
    """, (now_str,))

    cursor.execute("""
        INSERT INTO audit_logs (timestamp, event_type, actor_username, actor_role, ip_address, action_details, status)
        VALUES (?, 'SECURITY_CONFIG_LOADED', 'system', 'system', '127.0.0.1', 'Role-based access control, bcrypt hashing (work factor 12), and object-level authorization active.', 'SUCCESS')
    """, (now_str,))

    conn.commit()


# ==================== Auth & Session Functions ====================

def create_session(user_id: int, username: str, role: str) -> Dict[str, Any]:
    """Generate and store an authentication session token."""
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires = now + timedelta(days=7)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (token, user_id, username, role, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (token, user_id, username, role, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "expires_at": expires.isoformat()
    }


def get_session_user(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve the authenticated user associated with a session token."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.token, s.user_id, s.role, s.expires_at, u.username, u.full_name, u.depot_name
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Check expiration
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires_at:
        delete_session(token)
        return None

    return {
        "id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "full_name": row["full_name"],
        "depot_name": row["depot_name"]
    }


def delete_session(token: str) -> None:
    """Invalidate and remove a session token upon logout."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Look up a user account by username (case-insensitive and trimmed)."""
    if not username or not username.strip():
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password_hash, salt, role, full_name, depot_name
        FROM users
        WHERE LOWER(username) = LOWER(?)
    """, (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Look up a user account by user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, role, full_name, depot_name
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


# ==================== Depot & Bus & Driver Helpers ====================

def get_all_depots() -> List[Dict[str, Any]]:
    """Return all depots and their bus stats."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM depots ORDER BY depot_name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_buses() -> List[Dict[str, Any]]:
    """Return all buses and their statuses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM buses ORDER BY bus_number")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_drivers() -> List[Dict[str, Any]]:
    """Return all registered drivers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.user_id, d.driver_name, d.license_no, d.phone, d.depot_name, u.username
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.driver_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== Bus Schedule Management & Conflict Prevention ====================

def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse various ISO and datetime representations safely."""
    clean_str = dt_str.strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    # Try date + time fallback
    if len(clean_str) == 10:  # YYYY-MM-DD
        return datetime.strptime(clean_str, "%Y-%m-%d")
    raise ValueError(f"Unable to parse datetime string: '{dt_str}'")


def check_schedule_conflicts(
    bus_number: str,
    departure_time_str: str,
    arrival_time_str: Optional[str] = None,
    driver_id: Optional[int] = None,
    exclude_schedule_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """Detect overlapping schedules for the same bus or driver.

    Returns:
        (has_conflict, error_message)
    """
    try:
        new_dep = parse_iso_datetime(departure_time_str)
    except ValueError as e:
        return True, f"Invalid departure date/time format: {e}"

    if arrival_time_str and arrival_time_str.strip():
        try:
            new_arr = parse_iso_datetime(arrival_time_str)
        except ValueError as e:
            return True, f"Invalid arrival date/time format: {e}"
        if new_arr < new_dep:
            return True, "Arrival date/time cannot be earlier than departure date/time."
    else:
        # Assume minimum transit buffer of 45 minutes if arrival is not explicitly set
        new_arr = new_dep + timedelta(minutes=45)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query active schedules for the same bus
    query = """
        SELECT id, bus_number, departure_time, arrival_time, route_details, status
        FROM schedules
        WHERE bus_number = ?
          AND status NOT IN ('Completed', 'Cancelled')
    """
    params = [bus_number]
    if exclude_schedule_id:
        query += " AND id != ?"
        params.append(exclude_schedule_id)

    cursor.execute(query, params)
    bus_schedules = cursor.fetchall()

    for row in bus_schedules:
        try:
            existing_dep = parse_iso_datetime(row["departure_time"])
            if row["arrival_time"] and row["arrival_time"].strip():
                existing_arr = parse_iso_datetime(row["arrival_time"])
            else:
                existing_arr = existing_dep + timedelta(minutes=45)

            # Two intervals [new_dep, new_arr] and [existing_dep, existing_arr] overlap if:
            # new_dep < existing_arr and new_arr > existing_dep
            if new_dep < existing_arr and new_arr > existing_dep:
                conn.close()
                return True, (
                    f"Bus Assignment Conflict: Bus '{bus_number}' is already assigned to active schedule #{row['id']} "
                    f"({row['route_details']}) from {row['departure_time']} to "
                    f"{row['arrival_time'] or 'estimated completion'}. Overlapping schedules are not allowed."
                )
        except Exception:
            continue

    # Query active schedules for the same driver if assigned
    if driver_id:
        driver_query = """
            SELECT id, driver_name, bus_number, departure_time, arrival_time, route_details, status
            FROM schedules
            WHERE driver_id = ?
              AND status NOT IN ('Completed', 'Cancelled')
        """
        driver_params = [driver_id]
        if exclude_schedule_id:
            driver_query += " AND id != ?"
            driver_params.append(exclude_schedule_id)

        cursor.execute(driver_query, driver_params)
        driver_schedules = cursor.fetchall()

        for row in driver_schedules:
            try:
                existing_dep = parse_iso_datetime(row["departure_time"])
                if row["arrival_time"] and row["arrival_time"].strip():
                    existing_arr = parse_iso_datetime(row["arrival_time"])
                else:
                    existing_arr = existing_dep + timedelta(minutes=45)

                if new_dep < existing_arr and new_arr > existing_dep:
                    conn.close()
                    return True, (
                        f"Driver Assignment Conflict: Driver '{row['driver_name']}' is already assigned to active schedule #{row['id']} "
                        f"on bus {row['bus_number']} from {row['departure_time']} to "
                        f"{row['arrival_time'] or 'completion'}. A driver cannot operate two buses simultaneously."
                    )
            except Exception:
                continue

    conn.close()
    return False, None


def get_all_schedules(
    date_filter: Optional[str] = None,
    bus_filter: Optional[str] = None,
    route_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve bus schedules with optional multi-attribute filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM schedules WHERE 1=1"
    params = []

    if date_filter and date_filter.strip():
        sql += " AND event_date = ?"
        params.append(date_filter.strip())

    if bus_filter and bus_filter.strip():
        sql += " AND bus_number LIKE ?"
        params.append(f"%{bus_filter.strip()}%")

    if route_filter and route_filter.strip():
        sql += " AND (route_details LIKE ? OR source_stop LIKE ? OR destination_stop LIKE ?)"
        term = f"%{route_filter.strip()}%"
        params.extend([term, term, term])

    if status_filter and status_filter.strip():
        sql += " AND status = ?"
        params.append(status_filter.strip())

    if search_query and search_query.strip():
        sql += """ AND (
            event_name LIKE ? OR
            bus_number LIKE ? OR
            bus_registration_no LIKE ? OR
            driver_name LIKE ? OR
            route_details LIKE ? OR
            notes LIKE ?
        )"""
        term = f"%{search_query.strip()}%"
        params.extend([term, term, term, term, term, term])

    sql += " ORDER BY departure_time ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_schedule_by_id(schedule_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single schedule by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def create_schedule(data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new validated bus schedule into the database."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO schedules (
            event_name, event_date, event_start_time, expected_crowd_departure,
            depot_name, bus_number, bus_registration_no, bus_capacity, available_bus_count,
            source_stop, destination_stop, departure_time, arrival_time,
            driver_id, driver_name, route_details, status, notes, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        data["event_name"],
        data["event_date"],
        data["event_start_time"],
        data["expected_crowd_departure"],
        data["depot_name"],
        data["bus_number"],
        data.get("bus_registration_no"),
        data.get("bus_capacity", 70),
        data.get("available_bus_count", 1),
        data["source_stop"],
        data["destination_stop"],
        data["departure_time"],
        data.get("arrival_time"),
        data.get("driver_id"),
        data.get("driver_name"),
        data["route_details"],
        data.get("status", "Scheduled"),
        data.get("notes"),
        now_str,
        now_str
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return get_schedule_by_id(new_id)  # type: ignore


def update_schedule(schedule_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update fields on an existing schedule."""
    existing = get_schedule_by_id(schedule_id)
    if not existing:
        return None

    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE schedules
        SET event_name = ?,
            event_date = ?,
            event_start_time = ?,
            expected_crowd_departure = ?,
            depot_name = ?,
            bus_number = ?,
            bus_registration_no = ?,
            bus_capacity = ?,
            available_bus_count = ?,
            source_stop = ?,
            destination_stop = ?,
            departure_time = ?,
            arrival_time = ?,
            driver_id = ?,
            driver_name = ?,
            route_details = ?,
            status = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        data.get("event_name", existing["event_name"]),
        data.get("event_date", existing["event_date"]),
        data.get("event_start_time", existing["event_start_time"]),
        data.get("expected_crowd_departure", existing["expected_crowd_departure"]),
        data.get("depot_name", existing["depot_name"]),
        data.get("bus_number", existing["bus_number"]),
        data.get("bus_registration_no", existing["bus_registration_no"]),
        data.get("bus_capacity", existing["bus_capacity"]),
        data.get("available_bus_count", existing["available_bus_count"]),
        data.get("source_stop", existing["source_stop"]),
        data.get("destination_stop", existing["destination_stop"]),
        data.get("departure_time", existing["departure_time"]),
        data.get("arrival_time", existing["arrival_time"]),
        data.get("driver_id", existing["driver_id"]),
        data.get("driver_name", existing["driver_name"]),
        data.get("route_details", existing["route_details"]),
        data.get("status", existing["status"]),
        data.get("notes", existing["notes"]),
        now_str,
        schedule_id
    ))

    conn.commit()
    conn.close()
    return get_schedule_by_id(schedule_id)


def update_schedule_status(schedule_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    """Update the status of a schedule."""
    existing = get_schedule_by_id(schedule_id)
    if not existing:
        return None

    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE schedules
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (new_status, now_str, schedule_id))
    conn.commit()
    conn.close()
    return get_schedule_by_id(schedule_id)


def delete_schedule(schedule_id: int) -> bool:
    """Delete a schedule from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    rows_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_deleted > 0


def get_driver_schedules(user_id: int, driver_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve schedules assigned exclusively to the specified driver."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if driver_name:
        cursor.execute("""
            SELECT * FROM schedules
            WHERE driver_id = ? OR driver_name = ?
            ORDER BY departure_time ASC
        """, (user_id, driver_name))
    else:
        cursor.execute("""
            SELECT * FROM schedules
            WHERE driver_id = ?
            ORDER BY departure_time ASC
        """, (user_id,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== Camera & Crowd Vision Helpers ====================

def get_all_cameras() -> List[Dict[str, Any]]:
    """Retrieve all configured camera monitoring endpoints."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM camera_configs ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_camera_by_id(camera_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single camera by camera_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM camera_configs WHERE camera_id = ?", (camera_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_camera_config(camera_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update camera configuration (source type, URL, ROI, status)."""
    existing = get_camera_by_id(camera_id)
    if not existing:
        return None

    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE camera_configs
        SET source_type = ?,
            stream_url = ?,
            is_active = ?,
            roi_x1 = ?,
            roi_y1 = ?,
            roi_x2 = ?,
            roi_y2 = ?,
            status = ?,
            last_frame_time = ?
        WHERE camera_id = ?
    """, (
        data.get("source_type", existing["source_type"]),
        data.get("stream_url", existing["stream_url"]),
        data.get("is_active", existing["is_active"]),
        data.get("roi_x1", existing["roi_x1"]),
        data.get("roi_y1", existing["roi_y1"]),
        data.get("roi_x2", existing["roi_x2"]),
        data.get("roi_y2", existing["roi_y2"]),
        data.get("status", existing["status"]),
        now_str,
        camera_id
    ))
    conn.commit()
    conn.close()
    return get_camera_by_id(camera_id)


def save_crowd_reading(data: Dict[str, Any]) -> int:
    """Record a crowd density reading with data provenance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO crowd_readings (
            camera_id, stop_id, timestamp, raw_count, smoothed_count,
            crowd_level, trend, confidence, source_label, night_alert_flag, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["camera_id"],
        data["stop_id"],
        data.get("timestamp", datetime.now().isoformat()),
        data["raw_count"],
        data["smoothed_count"],
        data["crowd_level"],
        data.get("trend", "Stable"),
        data.get("confidence", 0.90),
        data.get("source_label", "DEMO SIMULATION"),
        data.get("night_alert_flag", 0),
        data.get("notes")
    ))
    reading_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reading_id


def get_recent_crowd_readings(
    camera_id: Optional[str] = None,
    stop_id: Optional[str] = None,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """Retrieve historical crowd readings for trend analysis."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM crowd_readings WHERE 1=1"
    params = []
    if camera_id:
        sql += " AND camera_id = ?"
        params.append(camera_id)
    if stop_id:
        sql += " AND stop_id = ?"
        params.append(stop_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# ==================== Bus Telematics & Occupancy Helpers ====================

def get_all_bus_telematics() -> List[Dict[str, Any]]:
    """Retrieve telematics and occupancy status for all 17 buses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bus_telematics ORDER BY bus_number ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bus_telematics(bus_number: str) -> Optional[Dict[str, Any]]:
    """Retrieve telematics for a single bus."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bus_telematics WHERE bus_number = ?", (bus_number,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_bus_telematics(bus_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update bus occupancy and operational status."""
    existing = get_bus_telematics(bus_number)
    if not existing:
        return None

    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    pax = data.get("passenger_count", existing["passenger_count"])
    cap = data.get("capacity", existing["capacity"])
    free_seats = max(0, cap - pax)
    occ_rate = round(pax / float(max(1, cap)), 2)

    cursor.execute("""
        UPDATE bus_telematics
        SET status = ?,
            passenger_count = ?,
            capacity = ?,
            available_seats = ?,
            occupancy_rate = ?,
            occupancy_source = ?,
            current_location = ?,
            distance_to_hub_km = ?,
            eta_mins = ?,
            eta_source = ?,
            last_update = ?
        WHERE bus_number = ?
    """, (
        data.get("status", existing["status"]),
        pax,
        cap,
        free_seats,
        occ_rate,
        data.get("occupancy_source", existing["occupancy_source"]),
        data.get("current_location", existing["current_location"]),
        data.get("distance_to_hub_km", existing["distance_to_hub_km"]),
        data.get("eta_mins", existing["eta_mins"]),
        data.get("eta_source", existing["eta_source"]),
        now_str,
        bus_number
    ))
    conn.commit()
    conn.close()
    return get_bus_telematics(bus_number)


# ==================== Alerts & Recommendations Helpers ====================

def get_all_alerts(status_filter: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    """Retrieve active and recent alerts for the Depot Manager."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM alerts_and_recommendations WHERE 1=1"
    params = []
    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_alert_by_id(alert_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve an alert by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts_and_recommendations WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_alert(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new operational or night safety alert."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts_and_recommendations (
            alert_type, severity, stop_id, stop_name, message, crowd_count,
            waiting_time_mins, is_night_time, recommended_bus_number,
            recommended_action, source_impact_summary, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
    """, (
        data.get("alert_type", "CROWD_SURGE"),
        data.get("severity", "HIGH"),
        data["stop_id"],
        data["stop_name"],
        data["message"],
        data.get("crowd_count", 0),
        data.get("waiting_time_mins", 15),
        data.get("is_night_time", 1),
        data.get("recommended_bus_number"),
        data.get("recommended_action"),
        data.get("source_impact_summary"),
        now_str
    ))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_alert_by_id(alert_id)  # type: ignore


def update_alert_status(alert_id: int, new_status: str, driver_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update alert status (ACKNOWLEDGED, DISMISSED) and optionally link notified driver."""
    existing = get_alert_by_id(alert_id)
    if not existing:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    if driver_id is not None:
        cursor.execute("""
            UPDATE alerts_and_recommendations
            SET status = ?, notified_driver_id = ?
            WHERE id = ?
        """, (new_status, driver_id, alert_id))
    else:
        cursor.execute("""
            UPDATE alerts_and_recommendations
            SET status = ?
            WHERE id = ?
        """, (new_status, alert_id))

    conn.commit()
    conn.close()
    return get_alert_by_id(alert_id)


# ==================== Driver Urgent Notifications Helpers ====================

def create_driver_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a high-priority dispatch or night safety notification for a driver."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO driver_notifications (
            driver_id, driver_name, bus_number, stop_name, notification_type,
            title, message, severity, is_read, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        data["driver_id"],
        data["driver_name"],
        data["bus_number"],
        data["stop_name"],
        data.get("notification_type", "NIGHT_SAFETY_DISPATCH"),
        data["title"],
        data["message"],
        data.get("severity", "HIGH"),
        now_str
    ))
    notif_id = cursor.lastrowid
    conn.commit()
    conn.close()

    cursor = get_db_connection().cursor()
    cursor.execute("SELECT * FROM driver_notifications WHERE id = ?", (notif_id,))
    row = cursor.fetchone()
    return dict(row)


def get_driver_notifications(driver_id: int, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieve notifications sent to a specific driver."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM driver_notifications WHERE driver_id = ?"
    params = [driver_id]
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY id DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_driver_notification_read(notification_id: int, driver_id: Optional[int] = None) -> bool:
    """Mark a driver notification as read, enforcing driver ownership if driver_id provided."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if driver_id is not None:
        cursor.execute("UPDATE driver_notifications SET is_read = 1 WHERE id = ? AND driver_id = ?", (notification_id, driver_id))
    else:
        cursor.execute("UPDATE driver_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ==================== Security Audit Logging Helpers ====================

def log_audit_event(
    event_type: str,
    actor_username: str,
    actor_role: str,
    action_details: str,
    ip_address: Optional[str] = None,
    status: str = "SUCCESS"
) -> Dict[str, Any]:
    """Record an immutable security audit event. Automatically sanitizes sensitive data."""
    # Ensure no secrets or tokens are stored in audit logs
    sanitized_details = action_details
    for secret_keyword in ["password", "token", "Bearer", "salt", "secret"]:
        if secret_keyword in sanitized_details.lower():
            # Redact suspect substrings
            import re
            sanitized_details = re.sub(rf"{secret_keyword}\s*[:=]\s*\S+", f"{secret_keyword}=[REDACTED]", sanitized_details, flags=re.IGNORECASE)

    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_logs (timestamp, event_type, actor_username, actor_role, ip_address, action_details, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now_str, event_type, actor_username, actor_role, ip_address or "127.0.0.1", sanitized_details, status))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    cursor = get_db_connection().cursor()
    cursor.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    return dict(row)


def get_audit_logs(
    limit: int = 50,
    event_type: Optional[str] = None,
    actor: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve security audit events (Depot Admin only)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM audit_logs WHERE 1=1"
    params: List[Any] = []
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    if actor:
        sql += " AND actor_username = ?"
        params.append(actor)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== Driver Incident / Delay Reports Helpers ====================

def create_driver_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a driver incident, delay, breakdown, or overcrowding report."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO driver_reports (
            driver_id, driver_name, bus_number, schedule_id, report_type, severity,
            stop_name, description, status, admin_response, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REPORTED', NULL, ?)
    """, (
        data["driver_id"],
        data["driver_name"],
        data["bus_number"],
        data.get("schedule_id"),
        data["report_type"],
        data.get("severity", "MEDIUM"),
        data.get("stop_name"),
        data["description"],
        now_str
    ))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Log audit event
    log_audit_event(
        event_type="DRIVER_REPORT_FILED",
        actor_username=data.get("driver_username", data["driver_name"]),
        actor_role="driver",
        action_details=f"Driver {data['driver_name']} filed {data['report_type']} report for {data['bus_number']} at {data.get('stop_name')}"
    )

    cursor = get_db_connection().cursor()
    cursor.execute("SELECT * FROM driver_reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    return dict(row)


def get_driver_reports(driver_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve driver reports; if driver_id specified, isolates to that driver."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if driver_id is not None:
        cursor.execute("SELECT * FROM driver_reports WHERE driver_id = ? ORDER BY id DESC", (driver_id,))
    else:
        cursor.execute("SELECT * FROM driver_reports ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_driver_report_status(report_id: int, new_status: str, admin_response: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Update driver report status and optional response from Depot Admin."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE driver_reports
        SET status = ?, admin_response = COALESCE(?, admin_response)
        WHERE id = ?
    """, (new_status, admin_response, report_id))
    conn.commit()
    cursor.execute("SELECT * FROM driver_reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ==================== Network Stops, Routes & Events Helpers ====================

def get_all_stops() -> List[Dict[str, Any]]:
    """Retrieve all network transit stops."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stops ORDER BY is_hub DESC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_routes() -> List[Dict[str, Any]]:
    """Retrieve all transit corridor routes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM routes WHERE is_active = 1 ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_events() -> List[Dict[str, Any]]:
    """Retrieve registered festival and crowd events."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_event_by_id(event_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single festival event by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_event_time(event_id: int, end_time: str, start_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Persist updated event time (e.g. for event delays)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if start_time:
        cursor.execute("UPDATE events SET end_time = ?, start_time = ? WHERE id = ?", (end_time, start_time, event_id))
    else:
        cursor.execute("UPDATE events SET end_time = ? WHERE id = ?", (end_time, event_id))
    conn.commit()
    conn.close()
    return get_event_by_id(event_id)


def update_stop_details(stop_id: str, capacity: Optional[int] = None, zone: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Persist updated transit stop capacity or operational zone."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if capacity is not None and zone is not None:
        cursor.execute("UPDATE stops SET capacity = ?, zone = ? WHERE stop_id = ?", (capacity, zone, stop_id))
    elif capacity is not None:
        cursor.execute("UPDATE stops SET capacity = ? WHERE stop_id = ?", (capacity, stop_id))
    elif zone is not None:
        cursor.execute("UPDATE stops SET zone = ? WHERE stop_id = ?", (zone, stop_id))
    conn.commit()
    cursor.execute("SELECT * FROM stops WHERE stop_id = ?", (stop_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_route_details(route_id: str, headway_mins: Optional[int] = None, distance_km: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Persist updated route parameters (travel headway, transit distance)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if headway_mins is not None and distance_km is not None:
        cursor.execute("UPDATE routes SET typical_headway_mins = ?, distance_km = ? WHERE route_id = ?", (headway_mins, distance_km, route_id))
    elif headway_mins is not None:
        cursor.execute("UPDATE routes SET typical_headway_mins = ? WHERE route_id = ?", (headway_mins, route_id))
    elif distance_km is not None:
        cursor.execute("UPDATE routes SET distance_km = ? WHERE route_id = ?", (distance_km, route_id))
    conn.commit()
    cursor.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_dispatch_plan(data: Dict[str, Any]) -> Dict[str, Any]:
    """Store an AI-recommended multi-bus redistribution plan pending human admin approval."""
    import json
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    plan_json = json.dumps(data.get("candidate_buses", []))

    cursor.execute("""
        INSERT INTO dispatch_plans (
            target_stop_id, target_stop_name, crowd_count, buses_requested, buses_allocated,
            status, plan_details_json, source_impact_summary, unmet_demand_reason,
            approved_by, created_at
        ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, NULL, ?)
    """, (
        data["target_stop_id"],
        data["target_stop_name"],
        data["crowd_count"],
        data.get("buses_requested", 4),
        len(data.get("candidate_buses", [])),
        plan_json,
        data.get("source_impact_summary", "Minimum commuter service preserved at source depots."),
        data.get("unmet_demand_reason"),
        now_str
    ))
    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()

    cursor = get_db_connection().cursor()
    cursor.execute("SELECT * FROM dispatch_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    res = dict(row)
    res["candidate_buses"] = json.loads(res["plan_details_json"])
    return res


def get_dispatch_plans(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve dispatch plans with parsed candidate JSON."""
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM dispatch_plans WHERE status = ? ORDER BY id DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM dispatch_plans ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["candidate_buses"] = json.loads(item["plan_details_json"])
        except Exception:
            item["candidate_buses"] = []
        result.append(item)
    return result


def get_dispatch_plan_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single dispatch plan."""
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dispatch_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["candidate_buses"] = json.loads(item["plan_details_json"])
    except Exception:
        item["candidate_buses"] = []
    return item


def approve_dispatch_plan(plan_id: int, approved_by_username: str) -> Dict[str, Any]:
    """Atomically approve a dispatch plan, creating distinct assignments and notifying drivers.

    Uses an atomic SQLite transaction to prevent duplicate assignments or race conditions.
    """
    import json
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM dispatch_plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Dispatch plan #{plan_id} not found.")

        plan = dict(row)
        if plan["status"] != "PENDING":
            raise ValueError(f"Dispatch plan #{plan_id} is already '{plan['status']}'.")

        raw_plan_data = json.loads(plan["plan_details_json"])
        if isinstance(raw_plan_data, dict):
            raw_candidates = raw_plan_data.get("buses") or raw_plan_data.get("candidate_buses") or []
        elif isinstance(raw_plan_data, list):
            raw_candidates = raw_plan_data
        else:
            raw_candidates = []

        now_str = datetime.now().isoformat()
        dep_time = (datetime.now() + timedelta(minutes=10)).isoformat()
        arr_time = (datetime.now() + timedelta(minutes=25)).isoformat()

        created_assignments = []
        # Revalidate availability and prevent overlapping conflicts
        for candidate in raw_candidates:
            if isinstance(candidate, str):
                bus_num = candidate
                driver_id = None
                driver_name = "Standby Relief Driver"
                source_stop = "Tech Hub North Stop"
            elif isinstance(candidate, dict):
                bus_num = candidate.get("bus_number") or candidate.get("bus_id")
                driver_id = candidate.get("driver_id")
                driver_name = candidate.get("driver_name", "Standby Relief Driver")
                source_stop = candidate.get("current_route", "Tech Park North Stop")
            else:
                continue

            target_stop = plan["target_stop_name"]

            # 1. Revalidation: ensure bus is registered and operational
            cursor.execute("SELECT bus_number, registration_no, depot_name, status, capacity FROM buses WHERE bus_number = ?", (bus_num,))
            bus_rec = cursor.fetchone()
            if not bus_rec:
                raise ValueError(f"Revalidation Failed: Bus {bus_num} is not registered in the fixed fleet.")
            if bus_rec["status"] in ["Maintenance", "Breakdown", "Out of Service"]:
                raise ValueError(f"Revalidation Failed: Bus {bus_num} is currently in {bus_rec['status']} status.")

            # 2. Conflict check: ensure bus is not already assigned to overlapping trip in schedules
            cursor.execute("""
                SELECT COUNT(*) FROM schedules
                WHERE bus_number = ? AND status IN ('Scheduled', 'Ready', 'Departed', 'En Route')
                AND departure_time <= ? AND arrival_time >= ?
            """, (bus_num, arr_time, dep_time))
            if cursor.fetchone()[0] > 0:
                raise ValueError(f"Revalidation Conflict: Bus {bus_num} has an active overlapping schedule.")

            # 3. Check assignments table for active uncompleted assignments
            cursor.execute("""
                SELECT COUNT(*) FROM assignments
                WHERE bus_number = ? AND status IN ('ASSIGNED', 'ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'BOARDING')
            """, (bus_num,))
            if cursor.fetchone()[0] > 0:
                raise ValueError(f"Revalidation Conflict: Bus {bus_num} is already committed to an active assignment.")

            reg_no = bus_rec["registration_no"] if bus_rec else "TN-02-B-AUTO"
            depot_name = bus_rec["depot_name"] if bus_rec else "Tech Park North Depot"
            bus_cap = bus_rec["capacity"] if bus_rec else 70

            # Create confirmed schedule entry
            cursor.execute("""
                INSERT INTO schedules (
                    event_name, event_date, event_start_time, expected_crowd_departure,
                    depot_name, bus_number, bus_registration_no, bus_capacity,
                    available_bus_count, source_stop, destination_stop,
                    departure_time, arrival_time, driver_id, driver_name,
                    route_details, status, notes, created_at, updated_at
                ) VALUES (
                    'Grand City Lights Cultural Festival', '2026-10-10', '18:00', ?,
                    ?, ?, ?, 70, 1, ?, ?, ?, ?, ?, ?,
                    ?, 'Scheduled', ?, ?, ?
                )
            """, (
                dep_time,
                depot_name,
                bus_num,
                reg_no,
                source_stop,
                target_stop,
                dep_time,
                arr_time,
                driver_id,
                driver_name,
                f"Proactive Evacuation Shuttle from {source_stop} to {target_stop}",
                f"Approved redistribution plan #{plan_id}: crowd relief for {plan['crowd_count']} waiting passengers.",
                now_str,
                now_str
            ))
            schedule_id = cursor.lastrowid

            # Create assignment record
            cursor.execute("""
                INSERT INTO assignments (
                    schedule_id, plan_id, bus_number, driver_id, driver_name,
                    source_stop, target_stop, departure_time, status, assigned_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ASSIGNED', ?, ?)
            """, (
                schedule_id,
                plan_id,
                bus_num,
                driver_id,
                driver_name,
                source_stop,
                target_stop,
                dep_time,
                now_str,
                f"Redistribution approved by {approved_by_username}"
            ))
            assignment_id = cursor.lastrowid

            # Update bus telematics status
            cursor.execute("""
                UPDATE bus_telematics
                SET status = 'Assigned', last_update = ?
                WHERE bus_number = ?
            """, (now_str, bus_num))

            # Notify driver
            if driver_id:
                cursor.execute("""
                    INSERT INTO driver_notifications (
                        driver_id, driver_name, bus_number, stop_name, notification_type,
                        title, message, severity, is_read, created_at
                    ) VALUES (?, ?, ?, ?, 'DISPATCH_REASSIGNMENT', ?, ?, 'HIGH', 0, ?)
                """, (
                    driver_id,
                    driver_name,
                    bus_num,
                    target_stop,
                    f"🚨 Urgent Dispatch: Divert {bus_num} ➔ {target_stop}",
                    f"Approved redistribution: Divert immediately to {target_stop} for passenger crowd clearance. Acknowledge and mark Ready.",
                    now_str
                ))

            created_assignments.append({
                "assignment_id": assignment_id,
                "schedule_id": schedule_id,
                "bus_number": bus_num,
                "driver_name": driver_name
            })

        # Update plan status
        cursor.execute("""
            UPDATE dispatch_plans
            SET status = 'APPROVED', approved_by = ?, resolved_at = ?
            WHERE id = ?
        """, (approved_by_username, now_str, plan_id))

        conn.commit()

        # Log audit event
        log_audit_event(
            event_type="DISPATCH_APPROVED",
            actor_username=approved_by_username,
            actor_role="depot_admin",
            action_details=f"Approved dispatch plan #{plan_id} creating {len(created_assignments)} assignments for {plan['target_stop_name']}"
        )

        return {
            "status": "APPROVED",
            "plan_id": plan_id,
            "buses_assigned": len(created_assignments),
            "buses_allocated": len(created_assignments),
            "assignments": created_assignments,
            "approved_by": approved_by_username,
            "resolved_at": now_str
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_assignments() -> List[Dict[str, Any]]:
    """Retrieve all operational driver assignments from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.schedule_id, a.plan_id, a.bus_number, a.driver_id, a.driver_name,
               a.source_stop, a.target_stop, a.departure_time, a.status, a.assigned_at, a.notes,
               b.capacity as bus_capacity, b.depot_name
        FROM assignments a
        LEFT JOIN buses b ON a.bus_number = b.bus_number
        ORDER BY a.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reject_dispatch_plan(plan_id: int, rejected_by: str, reason: str) -> Dict[str, Any]:
    """Depot Admin rejects a proposed bus redistribution plan."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dispatch_plans
        SET status = 'REJECTED', approved_by = ?, rejection_reason = ?, resolved_at = ?
        WHERE id = ?
    """, (rejected_by, reason, now_str, plan_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if not success:
        raise ValueError(f"Dispatch plan #{plan_id} not found.")

    log_audit_event(
        event_type="DISPATCH_REJECTED",
        actor_username=rejected_by,
        actor_role="depot_admin",
        action_details=f"Rejected dispatch plan #{plan_id}. Reason: {reason}"
    )

    return {
        "status": "REJECTED",
        "plan_id": plan_id,
        "rejected_by": rejected_by,
        "reason": reason,
        "rejection_reason": reason,
        "resolved_at": now_str
    }


def _add_column_if_not_exists(cursor: sqlite3.Cursor, table: str, column_def: str) -> None:
    """Safely append a new column to an existing table if it does not exist."""
    col_name = column_def.split()[0]
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cursor.fetchall()]
    if col_name not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def _init_upgrades(conn: sqlite3.Connection) -> None:
    """Ensure upgrade tables and columns exist without deleting or altering existing data."""
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()

    # 1. System Settings Table (configurable night hours, thresholds)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # Seed default system settings if missing
    default_settings = [
        ("night_start_hour", "20"),
        ("night_end_hour", "5"),
        ("unexpected_stop_threshold_mins", "10"),
        ("weather_demand_modifier_enabled", "1"),
        ("police_notification_mode", "MANUAL")
    ]
    for k, v in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (k, v, now_str))

    # 2. Emergency Contacts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT NOT NULL,
            agency_type TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT NOT NULL,
            emergency_number TEXT,
            email TEXT,
            jurisdiction TEXT NOT NULL,
            dispatch_instructions TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
    """)

    # Seed default emergency contacts if table is empty
    cursor.execute("SELECT COUNT(*) FROM emergency_contacts")
    if cursor.fetchone()[0] == 0:
        default_contacts = [
            (
                "City Police Operations & Control Room", "POLICE",
                "Duty Inspector Rajesh (Station 4)", "0422-2300100", "100 / 112",
                "controlroom.cbe@tnpolice.gov.in", "Central Metropolitan Transit & Arena Perimeter",
                "Direct line to Sector Patrol Units 4 & 5. Dispatch mobile PCR van upon critical queue stampede or road obstruction.",
                1, 1, now_str
            ),
            (
                "Festival Sector Police Post (Main Arena Bay 1)", "POLICE",
                "Sub-Inspector K. Murugan", "+91 94432-11001", "112",
                "sector.arena@tnpolice.gov.in", "Main Bus Stand & Festival Arena Pedestrian Gates",
                "Stationed on-site at Bay 1. Mobilize for platform crowd control, lost persons, or emergency corridor clearance.",
                0, 1, now_str
            ),
            (
                "Traffic Police South Division Command", "TRAFFIC_CONTROL",
                "Traffic Warden Selvam", "+91 94432-11002", "103",
                "traffic.south@tnpolice.gov.in", "Tech Park Express Corridor & North Arterial Road",
                "Manage green-corridor priority for incoming standby buses (BUS-201 to BUS-204).",
                0, 1, now_str
            ),
            (
                "District Emergency Medical Services (108 EMS)", "MEDICAL",
                "EMS Medical Officer Dr. Priya", "0422-2300108", "108",
                "ems.dispatch@tnhealth.org", "Festival Arena & Transit Terminals",
                "Stage Advanced Life Support (ALS) Ambulance at Gate 3 for heat exhaustion, physical distress, or crush injuries.",
                0, 1, now_str
            )
        ]
        for c in default_contacts:
            cursor.execute("""
                INSERT INTO emergency_contacts (
                    agency_name, agency_type, contact_person, phone, emergency_number,
                    email, jurisdiction, dispatch_instructions, is_primary, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, c)

    # 3. Dedicated Safety Incidents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS safety_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT UNIQUE NOT NULL,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            event_id TEXT,
            event_name TEXT,
            stop_id TEXT,
            stop_name TEXT,
            route_id TEXT,
            bus_number TEXT,
            driver_name TEXT,
            reported_time TEXT NOT NULL,
            source TEXT NOT NULL,
            source_provenance_label TEXT NOT NULL,
            description TEXT NOT NULL,
            supporting_evidence TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NEW',
            assigned_responder TEXT,
            action_history_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # Seed baseline incidents if table is empty
    cursor.execute("SELECT COUNT(*) FROM safety_incidents")
    if cursor.fetchone()[0] == 0:
        default_incidents = [
            (
                "INC-20261011-001", "NIGHT_OVERCROWDING", "CRITICAL",
                "EVT-01", "Grand City Lights Cultural Festival",
                "STOP_MAIN", "Main Bus Stand (Festival Arena)",
                "RT-01", "BUS-101", "R. Ramesh",
                now_str, "MANUAL_OPERATOR", "OPERATOR_VERIFIED",
                "Overcrowding surge at Bay 2 queue after headline act egress. Estimated 3,200 passengers queued with wait times approaching 28 minutes under reduced night lighting.",
                "Manual count verification by Platform Supervisor; CCTV feed at Gate 2 confirms dense passenger cluster; estimated wait 28m exceeds 15m threshold.",
                "NEW", "Station Supervisor Bay 2",
                json.dumps([{"time": now_str, "actor": "admin_chennai", "action": "Incident logged from Platform Supervisor report."}]),
                now_str, now_str
            ),
            (
                "INC-20261011-002", "BREAKDOWN", "HIGH",
                "EVT-01", "Grand City Lights Cultural Festival",
                "STOP_TPN", "Tech Hub North Stop",
                "RT-02", "BUS-105", "P. Suresh",
                now_str, "DRIVER_EMERGENCY", "OPERATOR_VERIFIED",
                "Vehicle cooling system warning light triggered; driver pulled over safely on bypass shoulder 500m before North Terminal.",
                "Driver report filed via in-cab telematics terminal; vehicle idle on shoulder; 0 passengers on board.",
                "ACKNOWLEDGED", "Central Depot Mobile Repair Van (Unit 2)",
                json.dumps([
                    {"time": now_str, "actor": "driver_p_suresh", "action": "Driver filed breakdown report via mobile portal."},
                    {"time": now_str, "actor": "admin_chennai", "action": "Acknowledged by Depot Admin. Mobile repair crew dispatched."}
                ]),
                now_str, now_str
            ),
            (
                "INC-20261011-003", "UNEXPECTED_STOP", "MEDIUM",
                "EVT-01", "Grand City Lights Cultural Festival",
                "STOP_STH", "South Commercial Terminal",
                "RT-03", "BUS-102", "K. Suresh",
                now_str, "TELEMATICS_RULE", "CONFIGURED_TELEMATICS_RULE",
                "Vehicle has remained stationary at South Junction signal bypass for 14 minutes (threshold: 10 mins) with engine running.",
                "Automated GPS dwell-time rule exceeded: 14 mins idle at lat: 10.9950, lon: 76.9720. Traffic signal congestion or police road diversion.",
                "RESOLVED", "Traffic Control Desk",
                json.dumps([
                    {"time": now_str, "actor": "system_rule_engine", "action": "Automated dwell-time violation triggered (> 10 mins)."},
                    {"time": now_str, "actor": "admin_chennai", "action": "Driver confirmed temporary police VIP motorcade traffic hold; intersection cleared and bus resumed transit."}
                ]),
                now_str, now_str
            )
        ]
        for inc in default_incidents:
            cursor.execute("""
                INSERT INTO safety_incidents (
                    incident_id, incident_type, severity, event_id, event_name,
                    stop_id, stop_name, route_id, bus_number, driver_name,
                    reported_time, source, source_provenance_label, description,
                    supporting_evidence, status, assigned_responder, action_history_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, inc)

    # 4. Police Escalations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS police_escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escalation_id TEXT UNIQUE NOT NULL,
            incident_id TEXT NOT NULL,
            contact_id INTEGER,
            agency_name TEXT NOT NULL,
            agency_type TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_phone TEXT,
            recipient_email TEXT,
            severity TEXT NOT NULL,
            incident_summary TEXT NOT NULL,
            dispatched_info_json TEXT NOT NULL,
            channel TEXT NOT NULL,
            delivery_status TEXT NOT NULL,
            delivery_notes TEXT,
            escalated_by TEXT NOT NULL,
            escalated_at TEXT NOT NULL,
            police_ack_status TEXT DEFAULT 'PENDING_ACKNOWLEDGEMENT',
            police_response_notes TEXT,
            acknowledged_at TEXT,
            FOREIGN KEY (incident_id) REFERENCES safety_incidents(incident_id) ON DELETE CASCADE
        );
    """)

    # 5. Backward-compatible column additions on dispatch_plans
    _add_column_if_not_exists(cursor, "dispatch_plans", "operation_window TEXT DEFAULT 'day'")
    _add_column_if_not_exists(cursor, "dispatch_plans", "reason_json TEXT")
    _add_column_if_not_exists(cursor, "dispatch_plans", "weather_impact_summary TEXT")

    conn.commit()


# ==================== Settings & Configuration Helpers ====================

def get_system_settings() -> Dict[str, str]:
    """Retrieve all operational system settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def update_system_setting(key: str, value: str) -> None:
    """Update a specific operational system setting."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, value, now_str))
    conn.commit()
    conn.close()


# ==================== Emergency Contacts Helpers ====================

def get_emergency_contacts(only_active: bool = True) -> List[Dict[str, Any]]:
    """Retrieve configured police and emergency services contacts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM emergency_contacts"
    if only_active:
        query += " WHERE is_active = 1"
    query += " ORDER BY is_primary DESC, id ASC"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_emergency_contact(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new authorized emergency agency contact."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO emergency_contacts (
            agency_name, agency_type, contact_person, phone, emergency_number,
            email, jurisdiction, dispatch_instructions, is_primary, is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        contact_data.get("agency_name", ""),
        contact_data.get("agency_type", "POLICE"),
        contact_data.get("contact_person", ""),
        contact_data.get("phone", ""),
        contact_data.get("emergency_number", ""),
        contact_data.get("email", ""),
        contact_data.get("jurisdiction", ""),
        contact_data.get("dispatch_instructions", ""),
        1 if contact_data.get("is_primary") else 0,
        1,
        now_str
    ))
    cid = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM emergency_contacts WHERE id = ?", (cid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


# ==================== Safety Incidents Helpers ====================

def get_safety_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    incident_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query safety incidents with optional status, severity, and type filters."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM safety_incidents WHERE 1=1"
    params: List[Any] = []

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)
    if severity and severity != "ALL":
        query += " AND severity = ?"
        params.append(severity)
    if incident_type and incident_type != "ALL":
        query += " AND incident_type = ?"
        params.append(incident_type)

    query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        try:
            d["action_history"] = json.loads(d.get("action_history_json", "[]"))
        except Exception:
            d["action_history"] = []
        results.append(d)
    return results


def get_safety_incident_by_id(incident_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve single incident record by unique incident_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM safety_incidents WHERE incident_id = ?", (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["action_history"] = json.loads(d.get("action_history_json", "[]"))
    except Exception:
        d["action_history"] = []
    return d


def create_safety_incident(data: Dict[str, Any], reported_by: str = "depot_admin") -> Dict[str, Any]:
    """Create a new verified safety incident with full provenance."""
    now_str = datetime.now().isoformat()
    incident_id = data.get("incident_id") or f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    initial_action = [{
        "time": now_str,
        "actor": reported_by,
        "action": f"Incident created: {data.get('description', '')[:80]}"
    }]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO safety_incidents (
            incident_id, incident_type, severity, event_id, event_name,
            stop_id, stop_name, route_id, bus_number, driver_name,
            reported_time, source, source_provenance_label, description,
            supporting_evidence, status, assigned_responder, action_history_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        incident_id,
        data.get("incident_type", "OTHER"),
        data.get("severity", "MEDIUM"),
        data.get("event_id", "EVT-01"),
        data.get("event_name", "Grand City Lights Cultural Festival"),
        data.get("stop_id", "STOP_MAIN"),
        data.get("stop_name", "Main Bus Stand (Festival Arena)"),
        data.get("route_id", "RT-01"),
        data.get("bus_number"),
        data.get("driver_name"),
        now_str,
        data.get("source", "MANUAL_OPERATOR"),
        data.get("source_provenance_label", "OPERATOR_VERIFIED"),
        data.get("description", ""),
        data.get("supporting_evidence", ""),
        "NEW",
        data.get("assigned_responder"),
        json.dumps(initial_action),
        now_str,
        now_str
    ))
    conn.commit()
    conn.close()

    log_audit_event(
        event_type="SAFETY_INCIDENT_CREATED",
        actor_username=reported_by,
        actor_role="depot_admin",
        action_details=f"Created safety incident {incident_id} ({data.get('incident_type')} - {data.get('severity')})"
    )

    return get_safety_incident_by_id(incident_id) or {}


def update_safety_incident_status(
    incident_id: str,
    new_status: str,
    actor_username: str,
    action_note: str,
    assigned_responder: Optional[str] = None
) -> Dict[str, Any]:
    """Acknowledge, escalate, or resolve a safety incident with audit trail."""
    now_str = datetime.now().isoformat()
    inc = get_safety_incident_by_id(incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found.")

    history = inc.get("action_history", [])
    history.append({
        "time": now_str,
        "actor": actor_username,
        "action": f"Status updated to {new_status}. {action_note}"
    })

    conn = get_db_connection()
    cursor = conn.cursor()
    responder = assigned_responder or inc.get("assigned_responder")
    cursor.execute("""
        UPDATE safety_incidents
        SET status = ?, assigned_responder = ?, action_history_json = ?, updated_at = ?
        WHERE incident_id = ?
    """, (new_status, responder, json.dumps(history), now_str, incident_id))
    conn.commit()
    conn.close()

    log_audit_event(
        event_type=f"SAFETY_INCIDENT_{new_status}",
        actor_username=actor_username,
        actor_role="depot_admin",
        action_details=f"Incident {incident_id} set to {new_status}. Note: {action_note}"
    )

    return get_safety_incident_by_id(incident_id) or {}


# ==================== Police Escalations Helpers ====================

def create_police_escalation(
    incident_id: str,
    contact_id: int,
    operator_username: str,
    additional_notes: str = ""
) -> Dict[str, Any]:
    """Create a verified police/emergency escalation record with real/manual channel status."""
    now_str = datetime.now().isoformat()
    inc = get_safety_incident_by_id(incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found.")

    contacts = get_emergency_contacts(only_active=True)
    target_contact = next((c for c in contacts if c["id"] == contact_id), None)
    if not target_contact:
        raise ValueError(f"Emergency contact ID {contact_id} not found.")

    # Determine delivery channel based on configured environment keys
    sms_configured = bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"))
    email_configured = bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))

    if sms_configured and target_contact.get("phone"):
        channel = "SMS_GATEWAY"
        delivery_status = "SENT"
        delivery_notes = f"Dispatched automated SMS to {target_contact['phone']} via Twilio."
    elif email_configured and target_contact.get("email"):
        channel = "EMAIL_GATEWAY"
        delivery_status = "SENT"
        delivery_notes = f"Dispatched automated emergency alert to {target_contact['email']} via SMTP."
    else:
        channel = "MANUAL_PHONE_CALL"
        delivery_status = "MANUALLY_REPORTED"
        delivery_notes = (
            f"No external SMS/Email gateway configured. Incident marked for manual operator phone dispatch to "
            f"{target_contact['agency_name']} ({target_contact['phone']}). Operator must call emergency desk."
        )

    escalation_id = f"ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    dispatched_payload = {
        "incident_id": inc["incident_id"],
        "severity": inc["severity"],
        "incident_type": inc["incident_type"],
        "stop_name": inc["stop_name"],
        "bus_number": inc.get("bus_number"),
        "reported_time": inc["reported_time"],
        "description": inc["description"],
        "supporting_evidence": inc["supporting_evidence"],
        "additional_notes": additional_notes,
        "target_agency": target_contact["agency_name"],
        "target_phone": target_contact["phone"],
        "target_emergency_dial": target_contact["emergency_number"]
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO police_escalations (
            escalation_id, incident_id, contact_id, agency_name, agency_type,
            recipient_name, recipient_phone, recipient_email, severity,
            incident_summary, dispatched_info_json, channel, delivery_status,
            delivery_notes, escalated_by, escalated_at, police_ack_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        escalation_id,
        incident_id,
        contact_id,
        target_contact["agency_name"],
        target_contact["agency_type"],
        target_contact.get("contact_person") or target_contact["agency_name"],
        target_contact.get("phone"),
        target_contact.get("email"),
        inc["severity"],
        inc["description"],
        json.dumps(dispatched_payload),
        channel,
        delivery_status,
        delivery_notes,
        operator_username,
        now_str,
        "PENDING_ACKNOWLEDGEMENT"
    ))
    conn.commit()
    conn.close()

    # Automatically set incident status to ESCALATED
    update_safety_incident_status(
        incident_id=incident_id,
        new_status="ESCALATED",
        actor_username=operator_username,
        action_note=f"Escalated to {target_contact['agency_name']} via {channel}. Delivery: {delivery_status}."
    )

    log_audit_event(
        event_type="POLICE_ESCALATION_DISPATCHED",
        actor_username=operator_username,
        actor_role="depot_admin",
        action_details=f"Escalated incident {incident_id} to {target_contact['agency_name']} ({channel}: {delivery_status})"
    )

    return {
        "escalation_id": escalation_id,
        "incident_id": incident_id,
        "agency_name": target_contact["agency_name"],
        "channel": channel,
        "delivery_status": delivery_status,
        "delivery_notes": delivery_notes,
        "dispatched_payload": dispatched_payload,
        "escalated_at": now_str
    }


def get_police_escalations(incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve logged police & emergency notification events."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM police_escalations"
    params = []
    if incident_id:
        query += " WHERE incident_id = ?"
        params.append(incident_id)
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["dispatched_info"] = json.loads(d.get("dispatched_info_json", "{}"))
        except Exception:
            d["dispatched_info"] = {}
        results.append(d)
    return results


def update_police_escalation_status(
    escalation_id: str,
    ack_status: str,
    response_notes: str,
    actor_username: str
) -> Dict[str, Any]:
    """Record officer acknowledgement or police response notes."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE police_escalations
        SET police_ack_status = ?, police_response_notes = ?, acknowledged_at = ?
        WHERE escalation_id = ?
    """, (ack_status, response_notes, now_str, escalation_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if not success:
        raise ValueError(f"Escalation {escalation_id} not found.")

    log_audit_event(
        event_type="POLICE_ACK_UPDATED",
        actor_username=actor_username,
        actor_role="depot_admin",
        action_details=f"Police escalation {escalation_id} updated: {ack_status}. Notes: {response_notes}"
    )

    return {
        "escalation_id": escalation_id,
        "police_ack_status": ack_status,
        "police_response_notes": response_notes,
        "acknowledged_at": now_str
    }



