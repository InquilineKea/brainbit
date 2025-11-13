#!/bin/bash

# Script to check all EFS file systems for Boltz2 data

echo "=== Checking All EFS File Systems ==="
echo ""

# EFS IDs
EFS_IDS=("fs-0c7f0529a33bc7dd6" "fs-099a29bc92cb6e100" "fs-0d93085a06853419d")
EFS_DATES=("Oct 21 11:31 AM" "Oct 21 4:28 PM" "Oct 20 4:50 PM")

for i in "${!EFS_IDS[@]}"; do
    EFS_ID="${EFS_IDS[$i]}"
    DATE="${EFS_DATES[$i]}"
    MOUNT_POINT="/mnt/efs_${i}"
    
    echo "----------------------------------------"
    echo "EFS $((i+1)): $EFS_ID"
    echo "Created: $DATE"
    echo "Mount point: $MOUNT_POINT"
    echo ""
    
    # Create mount point
    sudo mkdir -p "$MOUNT_POINT"
    
    # Mount the EFS
    echo "Mounting..."
    sudo mount -t efs -o tls "$EFS_ID:/" "$MOUNT_POINT" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✓ Mounted successfully"
        
        # Check size
        SIZE=$(df -h "$MOUNT_POINT" | tail -1 | awk '{print $3}')
        echo "Size used: $SIZE"
        
        # List contents
        echo ""
        echo "Contents:"
        sudo ls -lah "$MOUNT_POINT"
        
        # Count files
        FILE_COUNT=$(sudo find "$MOUNT_POINT" -type f 2>/dev/null | wc -l)
        echo ""
        echo "Total files: $FILE_COUNT"
        
        # If files exist, show tree structure
        if [ "$FILE_COUNT" -gt 0 ]; then
            echo ""
            echo "Directory structure:"
            sudo find "$MOUNT_POINT" -type f 2>/dev/null | head -20
        fi
    else
        echo "✗ Failed to mount"
    fi
    
    echo ""
done

echo "========================================"
echo "Summary complete. Check above for any EFS with files."
