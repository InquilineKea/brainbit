#!/usr/bin/env python3
"""
Search through the CopyClip archive database
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
import re

ARCHIVE_DB = Path("/Users/simfish/Downloads/Genome/copyclip_backups/copyclip_archive.sqlite")

def search_archive(query, limit=50, case_sensitive=False):
    """Search the archive for clipboard entries matching the query"""
    
    if not ARCHIVE_DB.exists():
        print(f"Error: Archive database not found at {ARCHIVE_DB}")
        print("Run backup_copyclip.py first to create the archive.")
        return
    
    conn = sqlite3.connect(ARCHIVE_DB)
    cursor = conn.cursor()
    
    # Build search query
    if case_sensitive:
        search_condition = "ZCONTENTS LIKE ?"
        search_param = f"%{query}%"
    else:
        search_condition = "LOWER(ZCONTENTS) LIKE LOWER(?)"
        search_param = f"%{query}%"
    
    cursor.execute(f"""
        SELECT ZCLIPPING.ZCONTENTS, ZCLIPPING.ZDATERECORDED, ZSOURCEAPP.ZNAME
        FROM ZCLIPPING
        LEFT JOIN ZSOURCEAPP ON ZCLIPPING.ZSOURCE = ZSOURCEAPP.Z_PK
        WHERE {search_condition}
        ORDER BY ZCLIPPING.ZDATERECORDED DESC
        LIMIT ?
    """, (search_param, limit))
    
    results = cursor.fetchall()
    
    print("=" * 80)
    print(f"SEARCH RESULTS FOR: '{query}'")
    print("=" * 80)
    print(f"Found {len(results)} matches (showing up to {limit})\n")
    
    if not results:
        print("No matches found.")
        conn.close()
        return
    
    for i, (content, date, source) in enumerate(results, 1):
        timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"--- Match #{i} ---")
        print(f"Date: {date_str}")
        print(f"Source: {source or 'Unknown'}")
        
        # Highlight the search term in the content
        if case_sensitive:
            highlighted = content
        else:
            # Case-insensitive highlighting
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            highlighted = pattern.sub(lambda m: f">>>{m.group()}<<<", content)
        
        # Show content with some context
        if len(highlighted) > 500:
            # Try to show context around the match
            match_pos = highlighted.lower().find(query.lower())
            if match_pos > 0:
                start = max(0, match_pos - 200)
                end = min(len(highlighted), match_pos + 300)
                snippet = highlighted[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(highlighted):
                    snippet = snippet + "..."
                print(f"Content: {snippet}")
            else:
                print(f"Content: {highlighted[:500]}...")
        else:
            print(f"Content: {highlighted}")
        print()
    
    conn.close()

def list_recent(limit=20):
    """List the most recent clipboard entries"""
    
    if not ARCHIVE_DB.exists():
        print(f"Error: Archive database not found at {ARCHIVE_DB}")
        return
    
    conn = sqlite3.connect(ARCHIVE_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ZCLIPPING.ZCONTENTS, ZCLIPPING.ZDATERECORDED, ZSOURCEAPP.ZNAME
        FROM ZCLIPPING
        LEFT JOIN ZSOURCEAPP ON ZCLIPPING.ZSOURCE = ZSOURCEAPP.Z_PK
        ORDER BY ZCLIPPING.ZDATERECORDED DESC
        LIMIT ?
    """, (limit,))
    
    results = cursor.fetchall()
    
    print("=" * 80)
    print(f"MOST RECENT {limit} CLIPBOARD ENTRIES")
    print("=" * 80)
    
    for i, (content, date, source) in enumerate(results, 1):
        timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n--- Entry #{i} ---")
        print(f"Date: {date_str}")
        print(f"Source: {source or 'Unknown'}")
        print(f"Content: {content[:300]}")
        if len(content) > 300:
            print("... (truncated)")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Search: python3 search_copyclip_archive.py <search_term>")
        print("  Recent: python3 search_copyclip_archive.py --recent [limit]")
        print("\nExamples:")
        print("  python3 search_copyclip_archive.py 'entropy'")
        print("  python3 search_copyclip_archive.py 'https://github.com'")
        print("  python3 search_copyclip_archive.py --recent 50")
        sys.exit(1)
    
    if sys.argv[1] == "--recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        list_recent(limit)
    else:
        query = sys.argv[1]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        search_archive(query, limit)
