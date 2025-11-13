#!/usr/bin/env python3
"""
Analyze CopyClip SQLite database to extract and display clipboard content
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def analyze_copyclip_db(db_path):
    """Analyze CopyClip database and display contents"""
    
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("=" * 80)
        print("COPYCLIP DATABASE ANALYSIS")
        print("=" * 80)
        print(f"\nDatabase: {db_path}")
        print(f"\nTables found: {[t[0] for t in tables]}\n")
        
        # Analyze each table
        for table_name in [t[0] for t in tables]:
            print(f"\n{'=' * 80}")
            print(f"TABLE: {table_name}")
            print("=" * 80)
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print(f"\nColumns: {[col[1] for col in columns]}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"Total rows: {count}")
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 100;")
            rows = cursor.fetchall()
            
            if rows:
                print(f"\nShowing first {len(rows)} entries:")
                print("-" * 80)
                
                for i, row in enumerate(rows, 1):
                    print(f"\nEntry #{i}:")
                    for col_info, value in zip(columns, row):
                        col_name = col_info[1]
                        
                        # Format the value based on type
                        if value is None:
                            display_value = "NULL"
                        elif isinstance(value, bytes):
                            try:
                                display_value = value.decode('utf-8')[:200]
                                if len(value) > 200:
                                    display_value += "... (truncated)"
                            except:
                                display_value = f"<binary data, {len(value)} bytes>"
                        elif isinstance(value, str):
                            display_value = value[:500]
                            if len(value) > 500:
                                display_value += "... (truncated)"
                        else:
                            display_value = str(value)
                        
                        print(f"  {col_name}: {display_value}")
            else:
                print("\nNo data in this table.")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Try both CopyClip database locations
    db_paths = [
        "/Users/simfish/Library/Containers/com.fiplab.copyclip2/Data/Library/Application Support/CopyClip/copyclip.sqlite",
        "/Users/simfish/Library/Containers/com.fiplab.clipboard/Data/Library/Application Support/CopyClip/copyclip.sqlite"
    ]
    
    for db_path in db_paths:
        if Path(db_path).exists():
            print(f"\nAnalyzing: {db_path}\n")
            analyze_copyclip_db(db_path)
            print("\n" + "=" * 80 + "\n")
