"""Secure Password Reset Utility for FestivalFlow AI Depot Administrators.

Usage:
  Interactive prompt:
    python scripts/reset_admin_password.py

  Non-interactive / automation:
    python scripts/reset_admin_password.py --username admin_chennai --password "<NEW_PASSWORD>"
"""

import sys
import os
import argparse
import getpass
import sqlite3
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import get_db_path, get_db_connection, hash_password


def reset_password(username: str, new_password: str) -> bool:
    """Reset the password for a specific user securely using bcrypt."""
    if len(new_password) < 8:
        print("[ERROR] Password must be at least 8 characters long.")
        return False

    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file not found at: {db_path}")
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify user exists
    cursor.execute("SELECT id, username, role, full_name FROM users WHERE username = ?", (username.strip(),))
    user = cursor.fetchone()

    if not user:
        print(f"[ERROR] User '{username}' does not exist in the database.")
        conn.close()
        return False

    # Compute secure bcrypt hash
    new_hash, salt = hash_password(new_password)

    now_str = datetime.now().isoformat()

    # Update password and salt
    cursor.execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
        (new_hash, salt, username.strip())
    )

    # Invalidate active sessions for this user for security
    cursor.execute("DELETE FROM sessions WHERE username = ?", (username.strip(),))

    # Record security audit log
    cursor.execute("""
        INSERT INTO audit_logs (event_type, actor_username, actor_role, action_details, timestamp)
        VALUES ('PASSWORD_RESET', ?, ?, 'Admin password reset executed via local CLI utility', ?)
    """, (username.strip(), user["role"], now_str))

    conn.commit()
    conn.close()

    print(f"[SUCCESS] Password for user '{username}' ({user['role']} - {user['full_name']}) has been successfully updated.")
    print("[INFO] Active sessions were invalidated. You can now log in with your new password.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Secure Admin Password Reset Utility for FestivalFlow AI")
    parser.add_argument("--username", "-u", default=None, help="Username to reset (e.g. admin_chennai)")
    parser.add_argument("--password", "-p", default=None, help="New password (if omitted, prompts securely)")
    args = parser.parse_args()

    username = args.username
    if not username:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, role, full_name, depot_name FROM users WHERE role = 'depot_admin'")
        admins = cur.fetchall()
        conn.close()

        print("=" * 65)
        print("FestivalFlow AI — Secure Administrator Password Reset")
        print("=" * 65)
        print("Available Administrator Accounts:")
        for idx, adm in enumerate(admins, 1):
            print(f"  [{idx}] Username: {adm['username']:<15} | {adm['full_name']} ({adm['depot_name']})")
        print("=" * 65)

        default_user = admins[0]["username"] if admins else "admin_chennai"
        inp = input(f"Enter username to reset [{default_user}]: ").strip()
        username = inp if inp else default_user

    new_password = args.password
    if not new_password:
        new_password = getpass.getpass(f"Enter new password for '{username}': ")
        confirm_password = getpass.getpass("Confirm new password: ")
        if new_password != confirm_password:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)

    success = reset_password(username, new_password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
