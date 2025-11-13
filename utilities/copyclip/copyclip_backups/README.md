# CopyClip Backup & Archive System

## 📁 What's Here

This directory contains your complete CopyClip clipboard history, preserved forever!

### Files:
- **`copyclip_archive.sqlite`** - Your permanent archive with ALL clipboard history
- **`copyclip_backup_YYYYMMDD_HHMMSS.sqlite`** - Timestamped backup snapshots
- **`backup.log`** - Log of automatic backups
- **`backup_error.log`** - Error log (if any issues occur)

## 📊 Current Archive Stats

- **Total entries**: 9,998 clipboard items
- **Date range**: August 2, 2024 → November 6, 2025 (461 days)
- **Top sources**: Arc (3,306), Firefox (2,399), ChatGPT (993)

## 🔧 How to Use

### Manual Backup (Run Anytime)
```bash
cd /Users/simfish/Downloads/Genome
python3 backup_copyclip.py
```

This will:
1. Create a timestamped backup of your current CopyClip database
2. Merge new entries into the permanent archive (avoiding duplicates)
3. Show statistics about your archive

### Search Your Archive
```bash
# Search for specific text
python3 search_copyclip_archive.py "entropy"
python3 search_copyclip_archive.py "https://github.com"

# View recent entries
python3 search_copyclip_archive.py --recent 50
```

### Setup Automatic Daily Backups
```bash
# Run the setup script
./setup_auto_backup.sh

# Activate automatic backups (runs daily at 2 AM)
launchctl load ~/Library/LaunchAgents/com.copyclip.backup.plist

# To stop automatic backups
launchctl unload ~/Library/LaunchAgents/com.copyclip.backup.plist
```

## 🎯 Why This Matters

**CopyClip auto-deletes entries after 10,000 items!**

At your current rate (~22 clips/day), you lose clipboard history older than ~460 days.

This backup system:
- ✅ Preserves ALL your clipboard history forever
- ✅ Merges new entries automatically (no duplicates)
- ✅ Lets you search through years of clipboard data
- ✅ Creates timestamped snapshots for extra safety

## 📈 Recommended Schedule

Run backups:
- **Daily**: If you copy a lot of important stuff
- **Weekly**: For normal usage
- **Before major work**: When doing research/writing

The automatic backup (if enabled) runs daily at 2 AM.

## 🔍 Advanced Usage

### Query the Archive Directly
```bash
sqlite3 copyclip_archive.sqlite

# Example queries:
SELECT COUNT(*) FROM ZCLIPPING;
SELECT ZNAME, COUNT(*) FROM ZCLIPPING JOIN ZSOURCEAPP ON ZSOURCE=Z_PK GROUP BY ZNAME;
```

### Export to Text
```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('copyclip_archive.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT ZCONTENTS, ZDATERECORDED FROM ZCLIPPING ORDER BY ZDATERECORDED")

with open('clipboard_history.txt', 'w') as f:
    for content, date in cursor.fetchall():
        timestamp = datetime(2001, 1, 1) + timedelta(seconds=date)
        f.write(f"\n{'='*80}\n{timestamp}\n{'='*80}\n{content}\n")
```

## 🛡️ Data Safety

- Archive is stored locally on your machine
- No cloud sync (your data stays private)
- Multiple backup copies for redundancy
- SQLite format is portable and future-proof

## 📝 Notes

- Archive grows over time (currently ~10MB for 10k entries)
- Duplicates are automatically skipped during merge
- Original CopyClip database is never modified
- Safe to run backup script multiple times

---

**Last updated**: November 6, 2025
**Archive location**: `/Users/simfish/Downloads/Genome/copyclip_backups/`
