#!/usr/bin/env python3
"""
Check the oldest and newest entries in CopyClip database
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def check_date_range(db_path):
    """Check the date range of clipboard entries"""
    
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print(f"Database: {db_path}")
        print("=" * 80)
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM ZCLIPPING")
        total_count = cursor.fetchone()[0]
        print(f"\nTotal entries: {total_count}")
        
        # Get oldest entry
        cursor.execute("""
            SELECT ZCONTENTS, ZDATERECORDED, ZSOURCE 
            FROM ZCLIPPING 
            ORDER BY ZDATERECORDED ASC 
            LIMIT 1
        """)
        oldest = cursor.fetchone()
        
        # Get newest entry
        cursor.execute("""
            SELECT ZCONTENTS, ZDATERECORDED, ZSOURCE 
            FROM ZCLIPPING 
            ORDER BY ZDATERECORDED DESC 
            LIMIT 1
        """)
        newest = cursor.fetchone()
        
        # Get oldest 10 entries
        cursor.execute("""
            SELECT ZCONTENTS, ZDATERECORDED, ZSOURCE 
            FROM ZCLIPPING 
            ORDER BY ZDATERECORDED ASC 
            LIMIT 10
        """)
        oldest_10 = cursor.fetchall()
        
        if oldest:
            text, date, source_id = oldest
            timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
            
            cursor.execute("SELECT ZNAME FROM ZSOURCEAPP WHERE Z_PK = ?", (source_id,))
            app_result = cursor.fetchone()
            app_name = app_result[0] if app_result else "Unknown"
            
            print("\n" + "=" * 80)
            print("OLDEST ENTRY")
            print("=" * 80)
            print(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Source: {app_name}")
            print(f"Text: {text[:500]}")
            if len(text) > 500:
                print("... (truncated)")
        
        if newest:
            text, date, source_id = newest
            timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
            
            cursor.execute("SELECT ZNAME FROM ZSOURCEAPP WHERE Z_PK = ?", (source_id,))
            app_result = cursor.fetchone()
            app_name = app_result[0] if app_result else "Unknown"
            
            print("\n" + "=" * 80)
            print("NEWEST ENTRY")
            print("=" * 80)
            print(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Source: {app_name}")
            print(f"Text: {text[:500]}")
            if len(text) > 500:
                print("... (truncated)")
        
        # Calculate time span
        if oldest and newest:
            oldest_date = datetime(2001, 1, 1) + timedelta(seconds=oldest[1])
            newest_date = datetime(2001, 1, 1) + timedelta(seconds=newest[1])
            time_span = newest_date - oldest_date
            
            print("\n" + "=" * 80)
            print("TIME SPAN ANALYSIS")
            print("=" * 80)
            print(f"Oldest entry: {oldest_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Newest entry: {newest_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Time span: {time_span.days} days ({time_span.days / 365.25:.1f} years)")
            print(f"Total entries: {total_count}")
            print(f"Average entries per day: {total_count / max(time_span.days, 1):.1f}")
        
        # Show oldest 10 entries to see if there's a pattern
        print("\n" + "=" * 80)
        print("OLDEST 10 ENTRIES")
        print("=" * 80)
        
        for i, (text, date, source_id) in enumerate(oldest_10, 1):
            timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
            
            cursor.execute("SELECT ZNAME FROM ZSOURCEAPP WHERE Z_PK = ?", (source_id,))
            app_result = cursor.fetchone()
            app_name = app_result[0] if app_result else "Unknown"
            
            print(f"\n--- Entry #{i} ---")
            print(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Source: {app_name}")
            print(f"Text: {text[:200]}")
            if len(text) > 200:
                print("... (truncated)")
        
        # Check if there's a 10,000 entry limit pattern
        print("\n" + "=" * 80)
        print("AUTO-DELETION ANALYSIS")
        print("=" * 80)
        
        if total_count == 9999 or total_count == 10000:
            print(f"\n⚠️  LIKELY AUTO-DELETION DETECTED!")
            print(f"The database has exactly {total_count} entries.")
            print("This suggests CopyClip has a 10,000 entry limit and is auto-deleting old entries.")
            print(f"Oldest entry is from {oldest_date.strftime('%Y-%m-%d')}, so entries before that have been deleted.")
        else:
            print(f"\nTotal entries: {total_count}")
            print("No obvious auto-deletion pattern detected (not at 10,000 limit).")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    db_paths = [
        "/Users/simfish/Library/Containers/com.fiplab.copyclip2/Data/Library/Application Support/CopyClip/copyclip.sqlite",
        "/Users/simfish/Library/Containers/com.fiplab.clipboard/Data/Library/Application Support/CopyClip/copyclip.sqlite"
    ]
    
    for db_path in db_paths:
        if Path(db_path).exists():
            check_date_range(db_path)
            print("\n")
