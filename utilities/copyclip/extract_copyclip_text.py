#!/usr/bin/env python3
"""
Extract text content from CopyClip SQLite database
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import re

def extract_text_content(db_path):
    """Extract and analyze text content from CopyClip database"""
    
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query the clipping table for text content
        cursor.execute("""
            SELECT ZCONTENTS, ZDATERECORDED, ZSOURCE 
            FROM ZCLIPPING 
            WHERE ZCONTENTS IS NOT NULL 
            ORDER BY ZDATERECORDED DESC
        """)
        
        rows = cursor.fetchall()
        
        print("=" * 80)
        print("COPYCLIP TEXT CONTENT EXTRACTION")
        print("=" * 80)
        print(f"\nDatabase: {db_path}")
        print(f"Total text entries found: {len(rows)}\n")
        
        # Collect all words
        all_words = []
        
        print("=" * 80)
        print("RECENT CLIPBOARD ENTRIES")
        print("=" * 80)
        
        for i, (text, date, source_app_id) in enumerate(rows[:50], 1):  # Show first 50
            # Convert Core Data timestamp to readable date
            # Core Data uses reference date of 2001-01-01
            if date:
                timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
                date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = "Unknown"
            
            # Get source app name
            cursor.execute("SELECT ZNAME FROM ZSOURCEAPP WHERE Z_PK = ?", (source_app_id,))
            app_result = cursor.fetchone()
            app_name = app_result[0] if app_result else "Unknown"
            
            print(f"\n--- Entry #{i} ---")
            print(f"Date: {date_str}")
            print(f"Source: {app_name}")
            print(f"Text: {text[:300]}")  # Show first 300 chars
            if len(text) > 300:
                print("... (truncated)")
            
            # Extract words for analysis
            words = re.findall(r'\b\w+\b', text.lower())
            all_words.extend(words)
        
        # Word frequency analysis
        print("\n" + "=" * 80)
        print("WORD FREQUENCY ANALYSIS")
        print("=" * 80)
        
        word_counts = Counter(all_words)
        print(f"\nTotal unique words: {len(word_counts)}")
        print(f"Total word occurrences: {sum(word_counts.values())}")
        
        print("\nTop 50 most common words:")
        print("-" * 80)
        for word, count in word_counts.most_common(50):
            print(f"{word:30} {count:5} times")
        
        # Statistics by length
        print("\n" + "=" * 80)
        print("STATISTICS")
        print("=" * 80)
        
        total_entries = len(rows)
        total_chars = sum(len(text) for text, _, _ in rows if text)
        avg_length = total_chars / total_entries if total_entries > 0 else 0
        
        print(f"\nTotal clipboard entries: {total_entries}")
        print(f"Total characters: {total_chars:,}")
        print(f"Average entry length: {avg_length:.1f} characters")
        
        # Entry length distribution
        lengths = [len(text) for text, _, _ in rows if text]
        if lengths:
            print(f"\nShortest entry: {min(lengths)} characters")
            print(f"Longest entry: {max(lengths)} characters")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Try both CopyClip database locations
    db_paths = [
        "/Users/simfish/Library/Containers/com.fiplab.copyclip2/Data/Library/Application Support/CopyClip/copyclip.sqlite",
        "/Users/simfish/Library/Containers/com.fiplab.clipboard/Data/Library/Application Support/CopyClip/copyclip.sqlite"
    ]
    
    for db_path in db_paths:
        if Path(db_path).exists():
            print(f"\nAnalyzing: {db_path}\n")
            extract_text_content(db_path)
            print("\n" + "=" * 80 + "\n")
