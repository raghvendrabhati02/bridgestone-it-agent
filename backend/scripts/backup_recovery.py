"""
backup_recovery.py
──────────────────────────────────────────────────────────────────────────────
Sprint 9: Database & Configuration Backup/Recovery Utility

Supports:
  - Database backup (SQLite snapshot file copy / PostgreSQL dump export)
  - Environment configuration backup (sanitized config snapshot)
  - Database & Configuration restore process
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
from typing import Optional


def get_default_backup_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def create_database_backup(db_url: Optional[str] = None, backup_dir: Optional[str] = None) -> str:
    """
    Creates a timestamped database backup.
    Supports SQLite file copy and PostgreSQL export.
    """
    if not db_url:
        db_url = os.getenv("DATABASE_URL", "sqlite:///./bridgestone_it_agent.db")
    if not backup_dir:
        backup_dir = get_default_backup_dir()

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if "sqlite" in db_url:
        # Extract sqlite file path
        sqlite_path = db_url.replace("sqlite:///", "").replace("sqlite://", "").strip()
        if not os.path.isabs(sqlite_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sqlite_path = os.path.abspath(os.path.join(base_dir, sqlite_path))

        if not os.path.isfile(sqlite_path):
            raise FileNotFoundError(f"SQLite database file not found at: {sqlite_path}")

        dest_filename = f"sqlite_backup_{timestamp}.db"
        dest_path = os.path.join(backup_dir, dest_filename)
        shutil.copy2(sqlite_path, dest_path)
        print(f"✓ SQLite database backed up successfully to: {dest_path}")
        return dest_path
    elif "postgresql" in db_url:
        dest_filename = f"postgres_backup_{timestamp}.sql"
        dest_path = os.path.join(backup_dir, dest_filename)
        # Note: pg_dump requires PostgreSQL client tools installed
        cmd = f"pg_dump \"{db_url}\" > \"{dest_path}\""
        res = os.system(cmd)
        if res == 0:
            print(f"✓ PostgreSQL database backed up successfully to: {dest_path}")
            return dest_path
        else:
            raise RuntimeError(f"pg_dump command failed with exit code: {res}")
    else:
        raise ValueError(f"Unsupported database URL scheme in: {db_url}")


def create_config_backup(backup_dir: Optional[str] = None) -> str:
    """
    Creates a timestamped backup of environment configuration.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)
    env_file = os.path.join(root_dir, ".env")
    if not os.path.isfile(env_file):
        env_file = os.path.join(root_dir, ".env.example")

    if not backup_dir:
        backup_dir = get_default_backup_dir()

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest_path = os.path.join(backup_dir, f"env_config_backup_{timestamp}.env")

    shutil.copy2(env_file, dest_path)
    print(f"✓ Environment configuration backed up successfully to: {dest_path}")
    return dest_path


def restore_database_backup(backup_file_path: str, target_db_path: Optional[str] = None) -> bool:
    """
    Restores a database from a backup file.
    """
    if not os.path.isfile(backup_file_path):
        raise FileNotFoundError(f"Backup file not found at: {backup_file_path}")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if backup_file_path.endswith(".db") or "sqlite" in backup_file_path:
        if not target_db_path:
            target_db_path = os.path.join(base_dir, "bridgestone_it_agent.db")
        shutil.copy2(backup_file_path, target_db_path)
        print(f"✓ SQLite database restored successfully from '{backup_file_path}' to '{target_db_path}'.")
        return True
    elif backup_file_path.endswith(".sql"):
        db_url = os.getenv("DATABASE_URL", "")
        if "postgresql" in db_url:
            cmd = f"psql \"{db_url}\" < \"{backup_file_path}\""
            res = os.system(cmd)
            if res == 0:
                print(f"✓ PostgreSQL database restored successfully from '{backup_file_path}'.")
                return True
            else:
                raise RuntimeError(f"psql restore command failed with exit code: {res}")
        else:
            raise ValueError("Target DATABASE_URL must be PostgreSQL to restore a .sql dump.")
    else:
        raise ValueError(f"Unrecognized backup file format: {backup_file_path}")


def main():
    parser = argparse.ArgumentParser(description="Bridgestone IT Agent Backup & Recovery Utility")
    parser.add_argument("action", choices=["backup", "backup-config", "restore"], help="Action to execute")
    parser.add_argument("--file", help="Path to backup file for restore action")
    parser.add_argument("--output-dir", help="Custom directory for backup output")

    args = parser.parse_args()

    if args.action == "backup":
        create_database_backup(backup_dir=args.output_dir)
        create_config_backup(backup_dir=args.output_dir)
    elif args.action == "backup-config":
        create_config_backup(backup_dir=args.output_dir)
    elif args.action == "restore":
        if not args.file:
            print("Error: --file argument is required for restore action.")
            sys.exit(1)
        restore_database_backup(args.file)


if __name__ == "__main__":
    main()
