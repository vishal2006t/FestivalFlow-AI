# FestivalFlow AI — Database Backup and Recovery Procedure

This document outlines the backup, restore, and data integrity procedures for the SQLite operational database (`app/data/festivalflow.db`).

## 1. Automated Online Backup (Zero Downtime)

SQLite supports live online backups without taking the FastAPI backend offline. Run the following command in PowerShell while the application is running:

```powershell
# In PowerShell:
.\.venv\Scripts\python.exe -c "import sqlite3; conn = sqlite3.connect('app/data/festivalflow.db'); conn.execute(\"VACUUM INTO 'app/data/festivalflow_backup.db'\"); conn.close(); print('Backup complete.')"
```

The `VACUUM INTO` command creates a consistent, unfragmented snapshot of the active database even if concurrent transactions are executing.

## 2. Cold Backup (Maintenance Window)

If the backend server is stopped:
```powershell
# Copy database file to backup directory with timestamp
$backupTime = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "app\data\festivalflow.db" "app\data\festivalflow_$backupTime.db"
```

## 3. Database Restore Procedure

To restore the operational database from a backup:

1. Stop the FastAPI backend server process (`uvicorn`).
2. Rename or archive the current database:
   ```powershell
   Move-Item "app\data\festivalflow.db" "app\data\festivalflow_corrupted_archive.db"
   ```
3. Copy the backup file into place:
   ```powershell
   Copy-Item "app\data\festivalflow_backup.db" "app\data\festivalflow.db"
   ```
4. Verify database integrity:
   ```powershell
   .\.venv\Scripts\python.exe -c "import sqlite3; conn = sqlite3.connect('app/data/festivalflow.db'); cur = conn.cursor(); cur.execute('PRAGMA integrity_check;'); print(cur.fetchall()); conn.close()"
   ```
   Output should be: `[('ok',)]`
5. Restart the FastAPI backend server.

## 4. Reset & Seed (Development / Staging Only)

To re-seed clean prototype demo data (Depot Admin accounts, Drivers, Fleet of 17 buses, initial schedules):
```powershell
.\.venv\Scripts\python.exe -c "from app.database import init_db; init_db(force_reset=True); print('Database reset and seeded.')"
```
*(Never run `force_reset=True` on a production deployment).*
