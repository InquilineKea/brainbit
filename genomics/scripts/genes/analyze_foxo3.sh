#!/bin/bash

# Script to analyze FOXO3 gene variants
# Created: 2025-03-02

# Define file paths
GENOME_VCF="/Users/simfish/Downloads/Genome/WGS C3156486.vcf"
FOXO3_REGION="chr6:108554790-108693686"
FOXO3_VARIANTS="/Users/simfish/Downloads/Genome/foxo3_variants.txt"
FOXO3_ANALYSIS="/Users/simfish/Downloads/Genome/foxo3_analysis.txt"

# Extract FOXO3 variants from your genome
echo "Extracting FOXO3 variants from your genome..."
echo "# FOXO3 Variants" > $FOXO3_VARIANTS
echo "# Chromosome | Position | ID | Reference | Alternate | Quality | Filter | Info | Format | Genotype" >> $FOXO3_VARIANTS

# Use quotes around the filename to handle spaces
grep -v "^#" "$GENOME_VCF" | awk -F'\t' '
    $1 == "chr6" && $2 >= 108554790 && $2 <= 108693686 {print $0}
    $1 == "6" && $2 >= 108554790 && $2 <= 108693686 {print $0}
' | sort -k2,2n >> $FOXO3_VARIANTS

# Count variants
VARIANT_COUNT=$(grep -v "^#" $FOXO3_VARIANTS | wc -l | tr -d ' ')

# Create analysis report
echo "# FOXO3 Gene Analysis" > $FOXO3_ANALYSIS
echo "Generated: $(date)" >> $FOXO3_ANALYSIS
echo "" >> $FOXO3_ANALYSIS

echo "## Background" >> $FOXO3_ANALYSIS
echo "FOXO3 (Forkhead Box O3) is a transcription factor that plays important roles in:" >> $FOXO3_ANALYSIS
echo "- Regulating longevity and aging" >> $FOXO3_ANALYSIS
echo "- Stress resistance" >> $FOXO3_ANALYSIS
echo "- Cell cycle regulation" >> $FOXO3_ANALYSIS
echo "- Apoptosis" >> $FOXO3_ANALYSIS
echo "- Autophagy" >> $FOXO3_ANALYSIS
echo "- Metabolism" >> $FOXO3_ANALYSIS
echo "" >> $FOXO3_ANALYSIS
echo "Variants in FOXO3 have been associated with increased human longevity in multiple populations." >> $FOXO3_ANALYSIS
echo "" >> $FOXO3_ANALYSIS

echo "## Your FOXO3 Variants" >> $FOXO3_ANALYSIS
echo "Total variants found in FOXO3 region: $VARIANT_COUNT" >> $FOXO3_ANALYSIS
echo "" >> $FOXO3_ANALYSIS

# Check for known longevity-associated variants
echo "## Known Longevity-Associated Variants" >> $FOXO3_ANALYSIS

# List of known longevity-associated FOXO3 SNPs
declare -a LONGEVITY_SNPS=(
    "rs2802292|G|Longevity-associated allele"
    "rs2764264|C|Longevity-associated allele"
    "rs13217795|C|Longevity-associated allele"
    "rs1935949|T|Longevity-associated allele"
    "rs4946935|A|Longevity-associated allele"
    "rs9400239|C|Longevity-associated allele"
    "rs479744|T|Longevity-associated allele"
)

# Check for each longevity SNP
for snp in "${LONGEVITY_SNPS[@]}"; do
    IFS='|' read -r rsid beneficial_allele description <<< "$snp"
    
    # Check if SNP is present in your variants
    if grep -q "$rsid" $FOXO3_VARIANTS; then
        # Extract genotype
        genotype=$(grep "$rsid" $FOXO3_VARIANTS | awk -F'\t' '{print $10}')
        ref=$(grep "$rsid" $FOXO3_VARIANTS | awk -F'\t' '{print $4}')
        alt=$(grep "$rsid" $FOXO3_VARIANTS | awk -F'\t' '{print $5}')
        
        echo "* $rsid: Found - Genotype: $genotype (Ref: $ref, Alt: $alt)" >> $FOXO3_ANALYSIS
        echo "  - $description" >> $FOXO3_ANALYSIS
        
        # Determine if beneficial allele is present
        if [[ "$ref" == "$beneficial_allele" && "$genotype" == *"0"* ]]; then
            echo "  - You have the beneficial allele" >> $FOXO3_ANALYSIS
        elif [[ "$alt" == "$beneficial_allele" && "$genotype" == *"1"* ]]; then
            echo "  - You have the beneficial allele" >> $FOXO3_ANALYSIS
        else
            echo "  - You do not have the beneficial allele" >> $FOXO3_ANALYSIS
        fi
    else
        echo "* $rsid: Not found in your genome data" >> $FOXO3_ANALYSIS
        echo "  - $description" >> $FOXO3_ANALYSIS
    fi
    echo "" >> $FOXO3_ANALYSIS
done

# Check for potentially damaging variants
echo "## Potentially Damaging Variants" >> $FOXO3_ANALYSIS

# List of potentially damaging FOXO3 variants
declare -a DAMAGING_VARIANTS=(
    "rs121908700|Missense variant (p.Arg211Gly)|Potentially affects DNA binding"
    "rs121908701|Missense variant (p.Ser253Asn)|Potentially affects phosphorylation"
    "rs121908702|Missense variant (p.His212Arg)|Potentially affects DNA binding"
)

# Check for each potentially damaging variant
for variant in "${DAMAGING_VARIANTS[@]}"; do
    IFS='|' read -r rsid variant_type effect <<< "$variant"
    
    # Check if variant is present in your genome
    if grep -q "$rsid" $FOXO3_VARIANTS; then
        genotype=$(grep "$rsid" $FOXO3_VARIANTS | awk -F'\t' '{print $10}')
        echo "* $rsid: Found - Genotype: $genotype" >> $FOXO3_ANALYSIS
        echo "  - $variant_type" >> $FOXO3_ANALYSIS
        echo "  - $effect" >> $FOXO3_ANALYSIS
        echo "  - This variant may affect FOXO3 function" >> $FOXO3_ANALYSIS
    else
        echo "* $rsid: Not found (good)" >> $FOXO3_ANALYSIS
    fi
    echo "" >> $FOXO3_ANALYSIS
done

# Check for structural variants affecting FOXO3
echo "## Structural Variants Affecting FOXO3" >> $FOXO3_ANALYSIS

# Check if any SVs overlap with FOXO3
if [[ -f "/Users/simfish/Downloads/Genome/010625-WGS-C3156486.sv.uncompressed.vcf" ]]; then
    # Extract SVs that overlap with FOXO3
    FOXO3_SVS=$(grep -v "^#" "/Users/simfish/Downloads/Genome/010625-WGS-C3156486.sv.uncompressed.vcf" | awk -F'\t' '
        $1 == "chr6" && $2 >= 108554790-10000 && $2 <= 108693686+10000 {print $0}
        $1 == "6" && $2 >= 108554790-10000 && $2 <= 108693686+10000 {print $0}
    ' | wc -l | tr -d ' ')
    
    if [[ "$FOXO3_SVS" -gt 0 ]]; then
        echo "Found $FOXO3_SVS structural variants that may affect FOXO3." >> $FOXO3_ANALYSIS
        echo "This could potentially impact gene function." >> $FOXO3_ANALYSIS
    else
        echo "No structural variants found affecting FOXO3 (good)." >> $FOXO3_ANALYSIS
    fi
else
    echo "Structural variant data not available for analysis." >> $FOXO3_ANALYSIS
fi
echo "" >> $FOXO3_ANALYSIS

# Summary
echo "## Summary" >> $FOXO3_ANALYSIS
echo "Based on the available data, here's an assessment of your FOXO3 gene:" >> $FOXO3_ANALYSIS
echo "" >> $FOXO3_ANALYSIS

# Check if any damaging variants were found
if grep -q "Found - Genotype" $FOXO3_ANALYSIS | grep -q "potentially damaging"; then
    echo "⚠️ You have potentially damaging variants in FOXO3 that may affect its function." >> $FOXO3_ANALYSIS
else
    echo "✅ No known damaging variants were found in your FOXO3 gene." >> $FOXO3_ANALYSIS
fi

# Check if any beneficial variants were found
if grep -q "You have the beneficial allele" $FOXO3_ANALYSIS; then
    echo "✅ You have one or more longevity-associated variants in FOXO3." >> $FOXO3_ANALYSIS
else
    echo "ℹ️ You don't have any of the known longevity-associated variants in FOXO3." >> $FOXO3_ANALYSIS
fi

echo "" >> $FOXO3_ANALYSIS
echo "## Limitations" >> $FOXO3_ANALYSIS
echo "This analysis is based on currently known variants and may not be comprehensive." >> $FOXO3_ANALYSIS
echo "Many variants have unknown effects, and the impact of specific combinations of variants is not well understood." >> $FOXO3_ANALYSIS
echo "This information is for research purposes only and should not be used for medical decisions." >> $FOXO3_ANALYSIS

echo "FOXO3 analysis complete. Results saved to:"
echo "- $FOXO3_VARIANTS"
echo "- $FOXO3_ANALYSIS"

# Display the analysis
cat $FOXO3_ANALYSIS
