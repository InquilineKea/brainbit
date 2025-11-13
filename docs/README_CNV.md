# Copy Number Variant (CNV) Analysis

This document provides an overview of the CNV analysis performed on your genome data.

## Overview

Copy Number Variants (CNVs) are a type of structural variation where segments of DNA are duplicated (gains) or deleted (losses). CNVs can range in size from a few hundred base pairs to several megabases and can affect gene function by altering gene dosage, disrupting coding sequences, or affecting gene regulation.

## Analysis Files

The following files have been generated from your CNV data:

1. **010625-WGS-C3156486.cnv.uncompressed.vcf**: The original CNV data in VCF format, decompressed from the binary BGZF format
2. **cnv_summary.txt**: Summary statistics of the CNVs in your genome
3. **cnv_losses.txt**: Detailed list of all copy number losses
4. **cnv_gains.txt**: Detailed list of all copy number gains
5. **cnv_significant.txt**: List of high-quality, large CNVs that may be of interest

## Summary of Findings

Your genome contains:
- 694 total CNVs (479 losses and 215 gains)
- 192 high-quality CNVs (PASS filter)
- 65 CNVs with lower quality scores
- 471 CNVs filtered due to small size

## Understanding CNV Data

The CNV data includes the following information:
- **Chromosome and Position**: Genomic location of the CNV
- **End**: End position of the CNV
- **Length**: Size of the CNV in base pairs
- **Quality**: Confidence score for the CNV call (higher is better)
- **CN**: Copy number (2 is normal, 0-1 are losses, 3+ are gains)

## Significant CNVs

Significant CNVs are those with:
- High quality scores (QUAL > 50)
- Large size (> 10,000 base pairs)

These CNVs are more likely to have functional impacts and may be worth investigating further, especially if they overlap with known genes.

## Next Steps

To further analyze your CNV data, you might consider:

1. **Gene Overlap Analysis**: Determine which genes are affected by your CNVs
2. **Phenotype Association**: Research if any of your CNVs are associated with specific traits or conditions
3. **Population Frequency**: Compare your CNVs with population databases to assess rarity
4. **Validation**: Consider validating important findings with alternative methods

## Technical Details

The CNV data was generated using the DRAGEN platform (version 05.121.645.4.0.3) with the following parameters:
- Reference genome: hg38
- CNV segmentation mode: slm (Segment-Level Method)
- Self-normalization enabled

The original file was in BGZF (Blocked GNU Zip Format) and has been converted to a standard VCF format for easier analysis.
