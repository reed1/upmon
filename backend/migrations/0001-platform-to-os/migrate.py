"""
Migrate access_log SQLite database:
  - Rename column `platform` → `os`
  - Re-parse `os` from `user_agent` for all rows
  - Set `client_type` to 'browser' where NULL

Usage: python migrate_platform_to_os.py <path-to-access-log.db>
"""

import shutil
import sqlite3
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-access-log.db>")
        sys.exit(1)

    db_path = sys.argv[1]
    backup_path = Path.home() / f"tmp_access_log_backup_{Path(db_path).stem}.db"
    shutil.copy2(db_path, backup_path)
    print(f"Backup created at {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")

    columns = [row[1] for row in conn.execute("PRAGMA table_info(access_log)")]
    if "platform" not in columns:
        print("Column 'platform' not found — already migrated?")
        sys.exit(1)

    conn.execute("BEGIN EXCLUSIVE")

    conn.execute("ALTER TABLE access_log RENAME COLUMN platform TO os")

    conn.execute(
        """
        UPDATE access_log SET os = CASE
            WHEN user_agent LIKE '%Android%' THEN 'android'
            WHEN user_agent LIKE '%iPhone%' OR user_agent LIKE '%iPad%' THEN 'ios'
            WHEN user_agent LIKE '%Macintosh%' THEN 'macos'
            WHEN user_agent LIKE '%Windows%' THEN 'windows'
            WHEN user_agent LIKE '%CrOS%' THEN 'chromeos'
            WHEN user_agent LIKE '%Linux%' THEN 'linux'
            ELSE NULL
        END
    """
    )

    conn.execute("UPDATE access_log SET client_type = 'browser' WHERE client_type IS NULL")

    conn.commit()

    # Report
    total = conn.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
    print(f"Total rows: {total}\n")

    print("OS counts:")
    for os_val, count in conn.execute(
        "SELECT COALESCE(os, '(null)'), COUNT(*) FROM access_log GROUP BY os ORDER BY COUNT(*) DESC"
    ):
        print(f"  {os_val}: {count}")

    print("\nClient type counts:")
    for ct, count in conn.execute(
        "SELECT COALESCE(client_type, '(null)'), COUNT(*) FROM access_log GROUP BY client_type ORDER BY COUNT(*) DESC"
    ):
        print(f"  {ct}: {count}")

    conn.close()
    print(f"\nMigration complete. Remove backup when verified:\n  rm {backup_path}")


if __name__ == "__main__":
    main()
