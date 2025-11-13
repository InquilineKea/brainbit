#!/usr/bin/env python3
"""
Backup CopyClip database and create a consolidated archive of all clipboard history
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import os

# Paths
SOURCE_DB = "/Users/simfish/Library/Containers/com.fiplab.clipboard/Data/Library/Application Support/CopyClip/copyclip.sqlite"
BACKUP_DIR = Path("/Users/simfish/Downloads/Genome/copyclip_backups")
ARCHIVE_DB = BACKUP_DIR / "copyclip_archive.sqlite"

def create_backup():
    """Create a timestamped backup of the current database"""
    
    if not Path(SOURCE_DB).exists():
        print(f"Error: Source database not found at {SOURCE_DB}")
        return None
    
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"copyclip_backup_{timestamp}.sqlite"
    
    print(f"Creating backup: {backup_path}")
    shutil.copy2(SOURCE_DB, backup_path)
    print(f"✓ Backup created successfully")
    
    return backup_path

def merge_into_archive(backup_path):
    """Merge backup entries into the permanent archive database"""
    
    if not backup_path or not backup_path.exists():
        print("Error: Backup file not found")
        return
    
    print(f"\nMerging into archive: {ARCHIVE_DB}")
    
    # Create archive database if it doesn't exist
    archive_exists = ARCHIVE_DB.exists()
    
    archive_conn = sqlite3.connect(ARCHIVE_DB)
    archive_cursor = archive_conn.cursor()
    
    if not archive_exists:
        print("Creating new archive database...")
        # Create tables matching CopyClip schema
        archive_cursor.execute("""
            CREATE TABLE IF NOT EXISTS ZCLIPPING (
                Z_PK INTEGER PRIMARY KEY,
                Z_ENT INTEGER,
                Z_OPT INTEGER,
                ZDISPLAYNAMELENGTH INTEGER,
                ZSOURCE INTEGER,
                ZDATERECORDED TIMESTAMP,
                ZCONTENTS VARCHAR,
                ZDISPLAYNAME VARCHAR,
                ZTYPE VARCHAR,
                UNIQUE(ZDATERECORDED, ZCONTENTS)
            )
        """)
        
        archive_cursor.execute("""
            CREATE TABLE IF NOT EXISTS ZSOURCEAPP (
                Z_PK INTEGER PRIMARY KEY,
                Z_ENT INTEGER,
                Z_OPT INTEGER,
                ZISBLACKLISTED INTEGER,
                ZNAME VARCHAR,
                ZICON BLOB
            )
        """)
        
        archive_cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_date ON ZCLIPPING(ZDATERECORDED)
        """)
        
        archive_conn.commit()
    
    # Connect to backup database
    backup_conn = sqlite3.connect(backup_path)
    backup_cursor = backup_conn.cursor()
    
    # Get statistics before merge
    archive_cursor.execute("SELECT COUNT(*) FROM ZCLIPPING")
    before_count = archive_cursor.fetchone()[0]
    
    # Merge ZSOURCEAPP entries
    backup_cursor.execute("SELECT * FROM ZSOURCEAPP")
    source_apps = backup_cursor.fetchall()
    
    for app in source_apps:
        try:
            archive_cursor.execute("""
                INSERT OR IGNORE INTO ZSOURCEAPP 
                (Z_PK, Z_ENT, Z_OPT, ZISBLACKLISTED, ZNAME, ZICON)
                VALUES (?, ?, ?, ?, ?, ?)
            """, app)
        except sqlite3.Error as e:
            # Skip if already exists
            pass
    
    # Merge ZCLIPPING entries (avoiding duplicates)
    backup_cursor.execute("SELECT * FROM ZCLIPPING")
    clippings = backup_cursor.fetchall()
    
    new_entries = 0
    for clip in clippings:
        try:
            # Try to insert, ignore if duplicate (based on date + content)
            archive_cursor.execute("""
                INSERT OR IGNORE INTO ZCLIPPING 
                (Z_PK, Z_ENT, Z_OPT, ZDISPLAYNAMELENGTH, ZSOURCE, 
                 ZDATERECORDED, ZCONTENTS, ZDISPLAYNAME, ZTYPE)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, clip)
            if archive_cursor.rowcount > 0:
                new_entries += 1
        except sqlite3.Error as e:
            # Skip problematic entries
            pass
    
    archive_conn.commit()
    
    # Get statistics after merge
    archive_cursor.execute("SELECT COUNT(*) FROM ZCLIPPING")
    after_count = archive_cursor.fetchone()[0]
    
    archive_cursor.execute("SELECT MIN(ZDATERECORDED), MAX(ZDATERECORDED) FROM ZCLIPPING")
    date_range = archive_cursor.fetchone()
    
    print(f"\n✓ Merge complete!")
    print(f"  Entries before: {before_count}")
    print(f"  New entries added: {new_entries}")
    print(f"  Total entries now: {after_count}")
    
    if date_range[0] and date_range[1]:
        from datetime import timedelta
        oldest = datetime(2001, 1, 1) + timedelta(seconds=date_range[0])
        newest = datetime(2001, 1, 1) + timedelta(seconds=date_range[1])
        span = newest - oldest
        print(f"  Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
        print(f"  Time span: {span.days} days ({span.days / 365.25:.1f} years)")
    
    backup_conn.close()
    archive_conn.close()

def show_archive_stats():
    """Display statistics about the archive"""
    
    if not ARCHIVE_DB.exists():
        print("No archive database found yet.")
        return
    
    conn = sqlite3.connect(ARCHIVE_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM ZCLIPPING")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(ZDATERECORDED), MAX(ZDATERECORDED) FROM ZCLIPPING")
    date_range = cursor.fetchone()
    
    print("\n" + "=" * 80)
    print("ARCHIVE DATABASE STATISTICS")
    print("=" * 80)
    print(f"Location: {ARCHIVE_DB}")
    print(f"Total entries: {total:,}")
    
    if date_range[0] and date_range[1]:
        from datetime import timedelta
        oldest = datetime(2001, 1, 1) + timedelta(seconds=date_range[0])
        newest = datetime(2001, 1, 1) + timedelta(seconds=date_range[1])
        span = newest - oldest
        print(f"Oldest entry: {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Newest entry: {newest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Time span: {span.days} days ({span.days / 365.25:.1f} years)")
        print(f"Average per day: {total / max(span.days, 1):.1f}")
    
    # Show some statistics
    cursor.execute("""
        SELECT ZSOURCEAPP.ZNAME, COUNT(*) as count 
        FROM ZCLIPPING 
        JOIN ZSOURCEAPP ON ZCLIPPING.ZSOURCE = ZSOURCEAPP.Z_PK 
        GROUP BY ZSOURCEAPP.ZNAME 
        ORDER BY count DESC 
        LIMIT 10
    """)
    top_sources = cursor.fetchall()
    
    print("\nTop 10 source applications:")
    for app, count in top_sources:
        print(f"  {app:30} {count:6,} entries")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 80)
    print("COPYCLIP BACKUP & ARCHIVE SYSTEM")
    print("=" * 80)
    
    # Create backup
    backup_path = create_backup()
    
    if backup_path:
        # Merge into archive
        merge_into_archive(backup_path)
        
        # Show statistics
        show_archive_stats()
        
        print("\n" + "=" * 80)
        print("BACKUP COMPLETE")
        print("=" * 80)
        print(f"\nYour clipboard history is now preserved in:")
        print(f"  • Latest backup: {backup_path}")
        print(f"  • Permanent archive: {ARCHIVE_DB}")
        print(f"\nRun this script regularly to keep your archive up to date!")
