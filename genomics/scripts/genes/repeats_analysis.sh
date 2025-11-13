#!/bin/bash

# Script to analyze repeat expansions from VCF file
# Created: 2025-03-02

# Define file paths
REPEATS_FILE="/Users/simfish/Downloads/Genome/010625-WGS-C3156486.repeats.uncompressed.vcf"
REPEATS_SUMMARY="/Users/simfish/Downloads/Genome/repeats_summary.txt"
REPEATS_DETAILS="/Users/simfish/Downloads/Genome/repeats_details.txt"
REPEATS_EXPANSIONS="/Users/simfish/Downloads/Genome/repeats_expansions.txt"

# Create summary of repeats file
echo "# Short Tandem Repeat (STR) Analysis Summary" > $REPEATS_SUMMARY
echo "Generated: $(date)" >> $REPEATS_SUMMARY
echo "" >> $REPEATS_SUMMARY

# Count total repeats
TOTAL_REPEATS=$(grep -v "^#" $REPEATS_FILE | wc -l | tr -d ' ')
echo "Total repeat loci analyzed: $TOTAL_REPEATS" >> $REPEATS_SUMMARY

# Count reference repeats (no expansion/contraction)
REF_REPEATS=$(grep -v "^#" $REPEATS_FILE | grep -c "0/0")
echo "Reference repeats (no expansion/contraction): $REF_REPEATS" >> $REPEATS_SUMMARY

# Count heterozygous repeats
HET_REPEATS=$(grep -v "^#" $REPEATS_FILE | grep -c "0/1\|1/0\|1/2\|2/1")
echo "Heterozygous repeat variants: $HET_REPEATS" >> $REPEATS_SUMMARY

# Count homozygous repeats
HOM_REPEATS=$(grep -v "^#" $REPEATS_FILE | grep -c "1/1\|2/2")
echo "Homozygous repeat variants: $HOM_REPEATS" >> $REPEATS_SUMMARY

# Extract repeat details
echo "# Short Tandem Repeat Details" > $REPEATS_DETAILS
echo "# Chromosome | Position | RepeatID | ReferenceUnits | ReferenceLength | RepeatUnit | Genotype | RepeatCopyNumber" >> $REPEATS_DETAILS

grep -v "^#" $REPEATS_FILE | awk -F'\t' '{
    # Extract repeat ID
    repid = "";
    match($8, /REPID=([^;]+)/, repid_arr);
    if (length(repid_arr) > 0) {
        repid = repid_arr[1];
    }
    
    # Extract reference copy number
    ref_cn = "";
    match($8, /REF=([0-9]+)/, ref_arr);
    if (length(ref_arr) > 0) {
        ref_cn = ref_arr[1];
    }
    
    # Extract reference length
    ref_len = "";
    match($8, /RL=([0-9]+)/, rl_arr);
    if (length(rl_arr) > 0) {
        ref_len = rl_arr[1];
    }
    
    # Extract repeat unit
    repeat_unit = "";
    match($8, /RU=([^;]+)/, ru_arr);
    if (length(ru_arr) > 0) {
        repeat_unit = ru_arr[1];
    }
    
    # Extract genotype and repeat copy number
    split($10, format, ":");
    genotype = format[1];
    repcn = format[3];
    
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", $1, $2, repid, ref_cn, ref_len, repeat_unit, genotype, repcn;
}' | sort -k1,1V -k2,2n >> $REPEATS_DETAILS

# Extract potential pathogenic expansions
echo "# Potentially Significant Repeat Expansions" > $REPEATS_EXPANSIONS
echo "# RepeatID | Chromosome | Position | ReferenceUnits | YourCopyNumber | RepeatUnit | Gene/Disease Association" >> $REPEATS_EXPANSIONS

# Known pathogenic repeat expansions and their thresholds
# Format: RepeatID|Threshold|Gene/Disease
declare -a PATHOGENIC_REPEATS=(
    "FMR1|55|Fragile X Syndrome"
    "HTT|40|Huntington's Disease"
    "ATXN1|39|Spinocerebellar Ataxia Type 1"
    "ATXN2|32|Spinocerebellar Ataxia Type 2"
    "ATXN3|55|Spinocerebellar Ataxia Type 3"
    "CACNA1A|20|Spinocerebellar Ataxia Type 6"
    "ATXN7|19|Spinocerebellar Ataxia Type 7"
    "PPP2R2B|55|Spinocerebellar Ataxia Type 12"
    "JPH3|41|Huntington's Disease-Like 2"
    "DMPK|50|Myotonic Dystrophy Type 1"
    "CNBP|75|Myotonic Dystrophy Type 2"
    "NOTCH2NLC|30|Neuronal Intranuclear Inclusion Disease"
    "C9orf72|30|ALS/FTD"
    "FXN|66|Friedreich's Ataxia"
    "AR|38|Spinal and Bulbar Muscular Atrophy"
    "TBP|42|Spinocerebellar Ataxia Type 17"
    "ATN1|48|Dentatorubral-Pallidoluysian Atrophy"
)

# Check each repeat against known pathogenic repeats
while read -r line; do
    # Skip header
    if [[ $line == \#* ]]; then
        continue
    fi
    
    # Parse line
    repid=$(echo "$line" | awk '{print $3}')
    chrom=$(echo "$line" | awk '{print $1}')
    pos=$(echo "$line" | awk '{print $2}')
    ref_cn=$(echo "$line" | awk '{print $4}')
    repeat_unit=$(echo "$line" | awk '{print $6}')
    genotype=$(echo "$line" | awk '{print $7}')
    repcn=$(echo "$line" | awk '{print $8}')
    
    # Extract the highest copy number
    highest_cn=$(echo "$repcn" | tr '/' ' ' | awk '{if ($1 > $2) print $1; else print $2}')
    
    # Check against known pathogenic repeats
    for path_repeat in "${PATHOGENIC_REPEATS[@]}"; do
        IFS='|' read -r path_repid path_threshold path_disease <<< "$path_repeat"
        
        if [[ "$repid" == "$path_repid" && "$highest_cn" -ge "$path_threshold" ]]; then
            echo "$repid | $chrom | $pos | $ref_cn | $repcn | $repeat_unit | $path_disease (Threshold: $path_threshold)" >> $REPEATS_EXPANSIONS
        fi
    done
    
    # Also report any repeat that is significantly expanded compared to reference
    # (more than 2x the reference copy number)
    if [[ "$highest_cn" -gt $(( ref_cn * 2 )) && "$highest_cn" -gt 20 ]]; then
        # Check if not already reported as pathogenic
        if ! grep -q "^$repid " $REPEATS_EXPANSIONS; then
            echo "$repid | $chrom | $pos | $ref_cn | $repcn | $repeat_unit | Significant expansion (>2x reference)" >> $REPEATS_EXPANSIONS
        fi
    fi
    
done < $REPEATS_DETAILS

# If no significant expansions found
if [[ ! -s $REPEATS_EXPANSIONS || $(grep -v "^#" $REPEATS_EXPANSIONS | wc -l) -eq 0 ]]; then
    echo "No known pathogenic repeat expansions detected." >> $REPEATS_EXPANSIONS
fi

echo "Repeat analysis complete. Results saved to:"
echo "- $REPEATS_SUMMARY"
echo "- $REPEATS_DETAILS"
echo "- $REPEATS_EXPANSIONS"
