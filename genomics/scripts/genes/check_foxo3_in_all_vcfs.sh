#!/bin/bash

# Script to check for FOXO3 longevity variants across all VCF files
# Created: 2025-03-02

echo "Searching for FOXO3 longevity variants across all VCF files..."
echo ""

# Define key FOXO3 variants to search for
VARIANTS=(
    "rs2802292"
    "rs2764264"
    "rs13217795"
    "rs1935949"
    "rs4946935"
    "rs9400239"
    "rs479744"
)

# Find all VCF files in the directory
VCF_FILES=$(find /Users/simfish/Downloads/Genome -name "*.vcf*" | grep -v "Hard")

# Search each VCF file for the variants
echo "=== FOXO3 Longevity Variants Search Results ==="
echo ""

for vcf in $VCF_FILES; do
    echo "Checking file: $vcf"
    
    # Try different methods to search based on file type
    if [[ $vcf == *.gz ]]; then
        echo "  (Compressed file, using zgrep)"
        for variant in "${VARIANTS[@]}"; do
            result=$(zgrep -i "$variant" "$vcf" | wc -l | tr -d ' ')
            if [[ $result -gt 0 ]]; then
                echo "  * $variant: FOUND ($result occurrences)"
                zgrep -i "$variant" "$vcf" | head -1
            else
                echo "  * $variant: Not found"
            fi
        done
    else
        echo "  (Uncompressed file)"
        for variant in "${VARIANTS[@]}"; do
            result=$(grep -i "$variant" "$vcf" | wc -l | tr -d ' ')
            if [[ $result -gt 0 ]]; then
                echo "  * $variant: FOUND ($result occurrences)"
                grep -i "$variant" "$vcf" | head -1
            else
                echo "  * $variant: Not found"
            fi
        done
    fi
    
    echo ""
done

echo "Search complete."
