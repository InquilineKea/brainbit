#!/bin/bash

# Script to extract and analyze CNV data from VCF file
# Created: 2025-03-02

# Define file paths
CNV_FILE="/Users/simfish/Downloads/Genome/010625-WGS-C3156486.cnv.uncompressed.vcf"
CNV_SUMMARY="/Users/simfish/Downloads/Genome/cnv_summary.txt"
CNV_LOSSES="/Users/simfish/Downloads/Genome/cnv_losses.txt"
CNV_GAINS="/Users/simfish/Downloads/Genome/cnv_gains.txt"
CNV_SIGNIFICANT="/Users/simfish/Downloads/Genome/cnv_significant.txt"

# Create summary of CNV file
echo "# CNV Analysis Summary" > $CNV_SUMMARY
echo "Generated: $(date)" >> $CNV_SUMMARY
echo "" >> $CNV_SUMMARY

# Count total CNVs
TOTAL_CNVS=$(grep -v "^#" $CNV_FILE | wc -l | tr -d ' ')
echo "Total entries: $TOTAL_CNVS" >> $CNV_SUMMARY

# Count reference regions
REF_REGIONS=$(grep "DRAGEN:REF" $CNV_FILE | wc -l | tr -d ' ')
echo "Reference regions: $REF_REGIONS" >> $CNV_SUMMARY

# Count losses and gains
LOSSES=$(grep "DRAGEN:LOSS" $CNV_FILE | wc -l | tr -d ' ')
GAINS=$(grep "DRAGEN:GAIN" $CNV_FILE | wc -l | tr -d ' ')
echo "Copy number losses: $LOSSES" >> $CNV_SUMMARY
echo "Copy number gains: $GAINS" >> $CNV_SUMMARY
echo "Total CNVs (losses + gains): $(($LOSSES + $GAINS))" >> $CNV_SUMMARY

echo "" >> $CNV_SUMMARY
echo "# CNV Quality Distribution" >> $CNV_SUMMARY
echo "High quality CNVs (PASS): $(grep -v "^#" $CNV_FILE | grep -v "DRAGEN:REF" | grep "PASS" | wc -l | tr -d ' ')" >> $CNV_SUMMARY
echo "Low quality CNVs (cnvQual): $(grep -v "^#" $CNV_FILE | grep -v "DRAGEN:REF" | grep "cnvQual" | wc -l | tr -d ' ')" >> $CNV_SUMMARY
echo "Size-filtered CNVs (cnvLength): $(grep -v "^#" $CNV_FILE | grep -v "DRAGEN:REF" | grep "cnvLength" | wc -l | tr -d ' ')" >> $CNV_SUMMARY

# Extract losses to a separate file
echo "# Copy Number Losses" > $CNV_LOSSES
echo "# Chromosome | Start | End | Length | Quality | CN" >> $CNV_LOSSES
grep "DRAGEN:LOSS" $CNV_FILE | awk -F'\t' '{
    split($8, info, ";");
    end = "";
    len = "";
    for (i in info) {
        if (info[i] ~ /^END=/) {
            end = substr(info[i], 5);
        }
        if (info[i] ~ /^REFLEN=/) {
            len = substr(info[i], 8);
        }
    }
    split($10, format, ":");
    cn = format[3];
    printf "%s\t%s\t%s\t%s\t%s\t%s\n", $1, $2, end, len, $6, cn;
}' | sort -k1,1V -k2,2n >> $CNV_LOSSES

# Extract gains to a separate file
echo "# Copy Number Gains" > $CNV_GAINS
echo "# Chromosome | Start | End | Length | Quality | CN" >> $CNV_GAINS
grep "DRAGEN:GAIN" $CNV_FILE | awk -F'\t' '{
    split($8, info, ";");
    end = "";
    len = "";
    for (i in info) {
        if (info[i] ~ /^END=/) {
            end = substr(info[i], 5);
        }
        if (info[i] ~ /^REFLEN=/) {
            len = substr(info[i], 8);
        }
    }
    split($10, format, ":");
    cn = format[3];
    printf "%s\t%s\t%s\t%s\t%s\t%s\n", $1, $2, end, len, $6, cn;
}' | sort -k1,1V -k2,2n >> $CNV_GAINS

# Extract significant CNVs (high quality and large size)
echo "# Significant CNVs (QUAL>50 and Size>10kb)" > $CNV_SIGNIFICANT
echo "# Type | Chromosome | Start | End | Length | Quality | CN" >> $CNV_SIGNIFICANT
grep -v "^#" $CNV_FILE | grep -v "DRAGEN:REF" | awk -F'\t' '{
    split($8, info, ";");
    end = "";
    len = "";
    type = "";
    for (i in info) {
        if (info[i] ~ /^END=/) {
            end = substr(info[i], 5);
        }
        if (info[i] ~ /^REFLEN=/) {
            len = substr(info[i], 8);
        }
        if (info[i] ~ /^SVTYPE=/) {
            type = substr(info[i], 8);
        }
    }
    split($10, format, ":");
    cn = format[3];
    if ($6 > 50 && len > 10000) {
        if ($1 ~ /LOSS/) {
            cnv_type = "LOSS";
        } else if ($1 ~ /GAIN/) {
            cnv_type = "GAIN";
        } else {
            cnv_type = type;
        }
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", cnv_type, $1, $2, end, len, $6, cn;
    }
}' | sort -k2,2V -k3,3n >> $CNV_SIGNIFICANT

echo "CNV analysis complete. Results saved to:"
echo "- $CNV_SUMMARY"
echo "- $CNV_LOSSES"
echo "- $CNV_GAINS"
echo "- $CNV_SIGNIFICANT"
