#!/bin/bash

# Script to analyze structural variants from VCF file
# Created: 2025-03-02
# Fixed: 2025-03-02 - Fixed awk regex pattern issues
# Updated: 2025-03-03 - Fixed extraction issues and improved parsing for macOS compatibility

# Define file paths
SV_FILE="/Users/simfish/Downloads/Genome/010625-WGS-C3156486.sv.uncompressed.vcf"
SV_SUMMARY="/Users/simfish/Downloads/Genome/sv_summary.txt"
SV_DELETIONS="/Users/simfish/Downloads/Genome/sv_deletions.txt"
SV_INSERTIONS="/Users/simfish/Downloads/Genome/sv_insertions.txt"
SV_DUPLICATIONS="/Users/simfish/Downloads/Genome/sv_duplications.txt"
SV_INVERSIONS="/Users/simfish/Downloads/Genome/sv_inversions.txt"
SV_TRANSLOCATIONS="/Users/simfish/Downloads/Genome/sv_translocations.txt"
SV_LARGE="/Users/simfish/Downloads/Genome/sv_large.txt"
SV_GENES="/Users/simfish/Downloads/Genome/sv_genes_affected.txt"

# Create summary of SV file
echo "# Structural Variant (SV) Analysis Summary" > $SV_SUMMARY
echo "Generated: $(date)" >> $SV_SUMMARY
echo "" >> $SV_SUMMARY

# Count total SVs
TOTAL_SVS=$(grep -v "^#" $SV_FILE | wc -l | tr -d ' ')
echo "Total structural variants: $TOTAL_SVS" >> $SV_SUMMARY

# Count by SV type
DEL_COUNT=$(grep -v "^#" $SV_FILE | grep -c "SVTYPE=DEL")
INS_COUNT=$(grep -v "^#" $SV_FILE | grep -c "SVTYPE=INS")
DUP_COUNT=$(grep -v "^#" $SV_FILE | grep -c "SVTYPE=DUP")
INV_COUNT=$(grep -v "^#" $SV_FILE | grep -c "SVTYPE=INV")
BND_COUNT=$(grep -v "^#" $SV_FILE | grep -c "SVTYPE=BND")

echo "Deletions: $DEL_COUNT" >> $SV_SUMMARY
echo "Insertions: $INS_COUNT" >> $SV_SUMMARY
echo "Duplications: $DUP_COUNT" >> $SV_SUMMARY
echo "Inversions: $INV_COUNT" >> $SV_SUMMARY
echo "Translocations/Breakends: $BND_COUNT" >> $SV_SUMMARY

# Count by genotype
HET_COUNT=$(grep -v "^#" $SV_FILE | grep -c "0/1\|1/0")
HOM_COUNT=$(grep -v "^#" $SV_FILE | grep -c "1/1")

echo "Heterozygous SVs: $HET_COUNT" >> $SV_SUMMARY
echo "Homozygous SVs: $HOM_COUNT" >> $SV_SUMMARY

# Count by quality
PASS_COUNT=$(grep -v "^#" $SV_FILE | grep -c "PASS")
FILTERED_COUNT=$(grep -v "^#" $SV_FILE | grep -v -c "PASS")

echo "High-quality SVs (PASS): $PASS_COUNT" >> $SV_SUMMARY
echo "Filtered SVs: $FILTERED_COUNT" >> $SV_SUMMARY

# Count by size using more compatible grep patterns
SMALL_COUNT=$(grep -v "^#" $SV_FILE | grep "SVLEN" | grep -E "SVLEN=-?[0-9]{1,3}[^0-9]|SVLEN=-?[0-9]{1,2}$" | wc -l | tr -d ' ')
MEDIUM_COUNT=$(grep -v "^#" $SV_FILE | grep "SVLEN" | grep -E "SVLEN=-?[0-9]{4,}|SVLEN=-?[1-9][0-9]{3}" | grep -v -E "SVLEN=-?[0-9]{5,}|SVLEN=-?[1-9][0-9]{4}" | wc -l | tr -d ' ')
LARGE_COUNT=$(grep -v "^#" $SV_FILE | grep "SVLEN" | grep -E "SVLEN=-?[0-9]{5,}|SVLEN=-?[1-9][0-9]{4}" | wc -l | tr -d ' ')

echo "Small SVs (<1kb): $SMALL_COUNT" >> $SV_SUMMARY
echo "Medium SVs (1kb-10kb): $MEDIUM_COUNT" >> $SV_SUMMARY
echo "Large SVs (>10kb): $LARGE_COUNT" >> $SV_SUMMARY

# Extract deletions to a separate file
echo "# Deletions" > $SV_DELETIONS
echo "# Chromosome | Start | End | Length | Quality | Genotype | Filter" >> $SV_DELETIONS

grep -v "^#" $SV_FILE | grep "SVTYPE=DEL" | head -n 100 | while read line; do
    chrom=$(echo "$line" | cut -f1)
    pos=$(echo "$line" | cut -f2)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    info=$(echo "$line" | cut -f8)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract SV length using sed instead of grep -P
    svlen=$(echo "$info" | sed -n 's/.*SVLEN=-\([0-9]*\).*/\1/p')
    if [ -z "$svlen" ]; then
        # Try to extract END position
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p')
        if [ -n "$end" ]; then
            svlen=$((end - pos))
        else
            svlen="unknown"
        fi
    fi
    
    # Calculate end position
    if [ "$svlen" != "unknown" ]; then
        end=$((pos + svlen))
    else
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p' || echo "unknown")
    fi
    
    echo -e "$chrom\t$pos\t$end\t$svlen\t$qual\t$genotype\t$filter" >> $SV_DELETIONS
done

# Extract insertions to a separate file
echo "# Insertions" > $SV_INSERTIONS
echo "# Chromosome | Position | Length | Sequence | Quality | Genotype | Filter" >> $SV_INSERTIONS

grep -v "^#" $SV_FILE | grep "SVTYPE=INS" | head -n 100 | while read line; do
    chrom=$(echo "$line" | cut -f1)
    pos=$(echo "$line" | cut -f2)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    info=$(echo "$line" | cut -f8)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract SV length using sed instead of grep -P
    svlen=$(echo "$info" | sed -n 's/.*SVLEN=\([0-9]*\).*/\1/p')
    
    # Extract insertion sequences using sed
    left_seq=$(echo "$info" | sed -n 's/.*LEFT_SVINSSEQ=\([^;]*\).*/\1/p')
    right_seq=$(echo "$info" | sed -n 's/.*RIGHT_SVINSSEQ=\([^;]*\).*/\1/p')
    
    if [ -z "$svlen" ]; then
        if [ -n "$left_seq" ]; then
            left_len=${#left_seq}
            right_len=0
            if [ -n "$right_seq" ]; then
                right_len=${#right_seq}
            fi
            svlen=$((left_len + right_len))
            seq="${left_seq}${right_seq}"
            # Truncate sequence if too long
            if [ ${#seq} -gt 30 ]; then
                seq="${seq:0:30}..."
            fi
        else
            svlen="unknown"
            seq="unknown"
        fi
    else
        if [ -n "$left_seq" ]; then
            seq="${left_seq}"
            # Truncate sequence if too long
            if [ ${#seq} -gt 30 ]; then
                seq="${seq:0:30}..."
            fi
        else
            seq="unknown"
        fi
    fi
    
    echo -e "$chrom\t$pos\t$svlen\t$seq\t$qual\t$genotype\t$filter" >> $SV_INSERTIONS
done

# Extract duplications to a separate file
echo "# Duplications" > $SV_DUPLICATIONS
echo "# Chromosome | Start | End | Length | Quality | Genotype | Filter" >> $SV_DUPLICATIONS

grep -v "^#" $SV_FILE | grep "SVTYPE=DUP" | head -n 100 | while read line; do
    chrom=$(echo "$line" | cut -f1)
    pos=$(echo "$line" | cut -f2)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    info=$(echo "$line" | cut -f8)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract SV length using sed instead of grep -P
    svlen=$(echo "$info" | sed -n 's/.*SVLEN=-\([0-9]*\).*/\1/p')
    if [ -z "$svlen" ]; then
        # Try to extract END position
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p')
        if [ -n "$end" ]; then
            svlen=$((end - pos))
        else
            svlen="unknown"
        fi
    fi
    
    # Calculate end position
    if [ "$svlen" != "unknown" ]; then
        end=$((pos + svlen))
    else
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p' || echo "unknown")
    fi
    
    echo -e "$chrom\t$pos\t$end\t$svlen\t$qual\t$genotype\t$filter" >> $SV_DUPLICATIONS
done

# Extract inversions to a separate file
echo "# Inversions" > $SV_INVERSIONS
echo "# Chromosome | Start | End | Length | Quality | Genotype | Filter" >> $SV_INVERSIONS

grep -v "^#" $SV_FILE | grep "SVTYPE=INV" | head -n 100 | while read line; do
    chrom=$(echo "$line" | cut -f1)
    pos=$(echo "$line" | cut -f2)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    info=$(echo "$line" | cut -f8)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract SV length using sed instead of grep -P
    svlen=$(echo "$info" | sed -n 's/.*SVLEN=-\([0-9]*\).*/\1/p')
    if [ -z "$svlen" ]; then
        # Try to extract END position
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p')
        if [ -n "$end" ]; then
            svlen=$((end - pos))
        else
            svlen="unknown"
        fi
    fi
    
    # Calculate end position
    if [ "$svlen" != "unknown" ]; then
        end=$((pos + svlen))
    else
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p' || echo "unknown")
    fi
    
    echo -e "$chrom\t$pos\t$end\t$svlen\t$qual\t$genotype\t$filter" >> $SV_INVERSIONS
done

# Extract translocations/breakends to a separate file
echo "# Translocations/Breakends" > $SV_TRANSLOCATIONS
echo "# Chromosome1 | Position1 | Chromosome2 | Position2 | Quality | Genotype | Filter" >> $SV_TRANSLOCATIONS

grep -v "^#" $SV_FILE | grep "SVTYPE=BND" | head -n 100 | while read line; do
    chrom1=$(echo "$line" | cut -f1)
    pos1=$(echo "$line" | cut -f2)
    alt=$(echo "$line" | cut -f5)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract second location from ALT field
    if [[ $alt =~ \[([^:]+):([0-9]+)\[ ]]; then
        chrom2="${BASH_REMATCH[1]}"
        pos2="${BASH_REMATCH[2]}"
    elif [[ $alt =~ \]([^:]+):([0-9]+)\] ]]; then
        chrom2="${BASH_REMATCH[1]}"
        pos2="${BASH_REMATCH[2]}"
    elif [[ $alt =~ ([^:]+):([0-9]+)\] ]]; then
        chrom2="${BASH_REMATCH[1]}"
        pos2="${BASH_REMATCH[2]}"
    elif [[ $alt =~ ([^:]+):([0-9]+)\[ ]]; then
        chrom2="${BASH_REMATCH[1]}"
        pos2="${BASH_REMATCH[2]}"
    else
        chrom2="unknown"
        pos2="unknown"
    fi
    
    echo -e "$chrom1\t$pos1\t$chrom2\t$pos2\t$qual\t$genotype\t$filter" >> $SV_TRANSLOCATIONS
done

# Extract large SVs to a separate file
echo "# Large Structural Variants (>10kb)" > $SV_LARGE
echo "# Type | Chromosome | Start | End | Length | Quality | Genotype | Filter" >> $SV_LARGE

grep -v "^#" $SV_FILE | grep -E "SVLEN=-?[0-9]{5,}|SVLEN=-?[1-9][0-9]{4}" | head -n 100 | while read line; do
    chrom=$(echo "$line" | cut -f1)
    pos=$(echo "$line" | cut -f2)
    qual=$(echo "$line" | cut -f6)
    filter=$(echo "$line" | cut -f7)
    info=$(echo "$line" | cut -f8)
    genotype=$(echo "$line" | cut -f10 | cut -d':' -f1)
    
    # Extract SV type using sed instead of grep -P
    svtype=$(echo "$info" | sed -n 's/.*SVTYPE=\([^;]*\).*/\1/p')
    
    # Extract SV length using sed
    svlen_with_sign=$(echo "$info" | sed -n 's/.*SVLEN=\(-\?[0-9]*\).*/\1/p')
    if [ -n "$svlen_with_sign" ]; then
        # Remove negative sign if present
        svlen=${svlen_with_sign#-}
    else
        svlen="unknown"
    fi
    
    # Calculate end position
    if [ "$svlen" != "unknown" ]; then
        end=$((pos + svlen))
    else
        end=$(echo "$info" | sed -n 's/.*END=\([0-9]*\).*/\1/p' || echo "unknown")
    fi
    
    echo -e "$svtype\t$chrom\t$pos\t$end\t$svlen\t$qual\t$genotype\t$filter" >> $SV_LARGE
done

# Create a new analysis for genes potentially affected by SVs
echo "# Genes Potentially Affected by Structural Variants" > $SV_GENES
echo "# This is a preliminary analysis and requires further validation" >> $SV_GENES
echo "# Chromosome | Start | End | SV Type | Length | Gene/Region (if known)" >> $SV_GENES

# Add a section for potential gene impact analysis in the future
echo "# Note: Gene annotation requires additional reference data" >> $SV_GENES
echo "# Future enhancement: Integrate with gene annotation databases" >> $SV_GENES

echo "Structural variant analysis complete. Results saved to:"
echo "- $SV_SUMMARY"
echo "- $SV_DELETIONS"
echo "- $SV_INSERTIONS"
echo "- $SV_DUPLICATIONS"
echo "- $SV_INVERSIONS"
echo "- $SV_TRANSLOCATIONS"
echo "- $SV_LARGE"
echo "- $SV_GENES"
