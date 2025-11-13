#!/usr/bin/env python3
"""
Inspect CopyClip database schema to find the correct column names
"""

import sqlite3
from pathlib import Path

def inspect_schema(db_path):
    """Inspect database schema"""
    
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print(f"Database: {db_path}")
        print("=" * 80)
        
        # Get ZCLIPPING table schema
        cursor.execute("PRAGMA table_info(ZCLIPPING);")
        columns = cursor.fetchall()
        
        print("\nZCLIPPING table columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Get a sample row to see what data looks like
        print("\n" + "=" * 80)
        print("Sample data from ZCLIPPING (first 3 rows):")
        print("=" * 80)
        
        cursor.execute("SELECT * FROM ZCLIPPING LIMIT 3")
        rows = cursor.fetchall()
        
        for i, row in enumerate(rows, 1):
            print(f"\n--- Row {i} ---")
            for col_info, value in zip(columns, row):
                col_name = col_info[1]
                
                if value is None:
                    display_value = "NULL"
                elif isinstance(value, bytes):
                    try:
                        decoded = value.decode('utf-8')
                        display_value = decoded[:200]
                        if len(decoded) > 200:
                            display_value += "... (truncated)"
                    except:
                        display_value = f"<binary data, {len(value)} bytes>"
                elif isinstance(value, str):
                    display_value = value[:200]
                    if len(value) > 200:
                        display_value += "... (truncated)"
                else:
                    display_value = str(value)
                
                print(f"  {col_name}: {display_value}")
        
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
            inspect_schema(db_path)
            print("\n")
