#!/bin/bash
# Quick stats about your CopyClip archive

ARCHIVE_DB="/Users/simfish/Downloads/Genome/copyclip_backups/copyclip_archive.sqlite"

if [ ! -f "$ARCHIVE_DB" ]; then
    echo "Archive not found. Run backup_copyclip.py first."
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                        COPYCLIP ARCHIVE STATISTICS"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Total entries
TOTAL=$(sqlite3 "$ARCHIVE_DB" "SELECT COUNT(*) FROM ZCLIPPING;")
echo "📊 Total entries: $TOTAL"

# Date range
sqlite3 "$ARCHIVE_DB" <<EOF
.mode line
SELECT 
    datetime(MIN(ZDATERECORDED) + 978307200, 'unixepoch', 'localtime') as 'Oldest entry',
    datetime(MAX(ZDATERECORDED) + 978307200, 'unixepoch', 'localtime') as 'Newest entry',
    CAST((MAX(ZDATERECORDED) - MIN(ZDATERECORDED)) / 86400.0 AS INT) as 'Days of history'
FROM ZCLIPPING;
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                           TOP 10 SOURCE APPS"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

sqlite3 "$ARCHIVE_DB" <<EOF
.mode column
.headers on
SELECT 
    ZSOURCEAPP.ZNAME as 'Application',
    COUNT(*) as 'Entries',
    ROUND(COUNT(*) * 100.0 / $TOTAL, 1) || '%' as 'Percentage'
FROM ZCLIPPING 
JOIN ZSOURCEAPP ON ZCLIPPING.ZSOURCE = ZSOURCEAPP.Z_PK 
GROUP BY ZSOURCEAPP.ZNAME 
ORDER BY COUNT(*) DESC 
LIMIT 10;
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                           RECENT ACTIVITY"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

sqlite3 "$ARCHIVE_DB" <<EOF
.mode column
.headers on
SELECT 
    DATE(ZDATERECORDED + 978307200, 'unixepoch', 'localtime') as 'Date',
    COUNT(*) as 'Clips'
FROM ZCLIPPING 
WHERE ZDATERECORDED > (SELECT MAX(ZDATERECORDED) - 604800 FROM ZCLIPPING)
GROUP BY DATE(ZDATERECORDED + 978307200, 'unixepoch', 'localtime')
ORDER BY Date DESC
LIMIT 7;
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "💡 To search: python3 search_copyclip_archive.py \"search term\""
echo "💡 To backup: python3 backup_copyclip.py"
echo ""
