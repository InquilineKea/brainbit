#!/bin/bash
# Setup automatic CopyClip backup using launchd (macOS)

SCRIPT_DIR="/Users/simfish/Downloads/Genome"
BACKUP_SCRIPT="$SCRIPT_DIR/backup_copyclip.py"
PLIST_FILE="$HOME/Library/LaunchAgents/com.copyclip.backup.plist"

echo "Setting up automatic CopyClip backup..."
echo ""

# Make backup script executable
chmod +x "$BACKUP_SCRIPT"

# Create launchd plist file
cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.copyclip.backup</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$BACKUP_SCRIPT</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/copyclip_backups/backup.log</string>
    
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/copyclip_backups/backup_error.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✓ Created launchd configuration at:"
echo "  $PLIST_FILE"
echo ""
echo "This will run the backup daily at 2:00 AM"
echo ""
echo "To activate the automatic backup, run:"
echo "  launchctl load $PLIST_FILE"
echo ""
echo "To stop automatic backups, run:"
echo "  launchctl unload $PLIST_FILE"
echo ""
echo "To manually run a backup anytime:"
echo "  python3 $BACKUP_SCRIPT"
echo ""
echo "Backup location:"
echo "  $SCRIPT_DIR/copyclip_backups/"
