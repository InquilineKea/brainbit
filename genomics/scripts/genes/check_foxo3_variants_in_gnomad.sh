#!/bin/bash

# This script will help you look up your most interesting FOXO3 variants in the gnomAD browser

echo "FOXO3 Variant Frequencies in gnomAD"
echo "==================================="
echo
echo "To check these variants in gnomAD, visit the following URLs:"
echo

# Homozygous structural variants
echo "1. Homozygous deletion of 10 T's at chr6:108569987"
echo "   https://gnomad.broadinstitute.org/variant/6-108569987-GTTTTTTTTTT-G?dataset=gnomad_r3"
echo

# Homozygous 3' UTR variants
echo "2. Homozygous 3' UTR variant at chr6:108682118 (T>C)"
echo "   https://gnomad.broadinstitute.org/variant/6-108682118-T-C?dataset=gnomad_r3"
echo
echo "3. Homozygous 3' UTR variant at chr6:108682786 (C>A)"
echo "   https://gnomad.broadinstitute.org/variant/6-108682786-C-A?dataset=gnomad_r3"
echo

# Multi-allelic variants
echo "4. Multi-allelic variant at chr6:108585022"
echo "   https://gnomad.broadinstitute.org/variant/6-108585022-C-CTTTTT?dataset=gnomad_r3"
echo "   https://gnomad.broadinstitute.org/variant/6-108585022-C-CTTTT?dataset=gnomad_r3"
echo
echo "5. Multi-allelic variant at chr6:108586936"
echo "   https://gnomad.broadinstitute.org/variant/6-108586936-ATATTATTAT-ATAT?dataset=gnomad_r3"
echo "   https://gnomad.broadinstitute.org/variant/6-108586936-ATATTATTAT-A?dataset=gnomad_r3"
echo

# Heterozygous variants
echo "6. Heterozygous variant at chr6:108611098 (AT>A)"
echo "   https://gnomad.broadinstitute.org/variant/6-108611098-AT-A?dataset=gnomad_r3"
echo
echo "7. Heterozygous variant at chr6:108613318 (T>C)"
echo "   https://gnomad.broadinstitute.org/variant/6-108613318-T-C?dataset=gnomad_r3"
echo
echo "8. Heterozygous 3' UTR variant at chr6:108683599 (T>C)"
echo "   https://gnomad.broadinstitute.org/variant/6-108683599-T-C?dataset=gnomad_r3"
echo

echo "Instructions:"
echo "1. Copy each URL into your web browser to check if the variant exists in gnomAD"
echo "2. For each variant, note the allele frequency (AF) value"
echo "3. Variants with low AF or not found in gnomAD are likely to be rare"
echo "4. Pay special attention to the population-specific frequencies"
