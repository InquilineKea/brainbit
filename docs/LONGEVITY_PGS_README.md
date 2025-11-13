# Longevity Polygenic Score (PGS) Analysis Toolkit

This toolkit provides tools for calculating and analyzing longevity-related polygenic scores from personal genetic data.

## Overview

Polygenic Scores (PGS) are statistical tools that aggregate the effects of many genetic variants into a single score that can predict a person's genetic predisposition for a particular trait or disease. This toolkit focuses specifically on longevity-related PGS models from the PGS Catalog.

## Available Tools

1. **calculate_longevity_pgs.py** - Basic script to calculate a longevity PGS from a VCF file
2. **longevity_pgs_toolkit.py** - Comprehensive toolkit with support for multiple models and visualization
3. **convert_pgs_to_hg38.py** - Utility to convert PGS models from GRCh37/hg19 to GRCh38/hg38

## Requirements

- Python 3.6+
- Required Python packages:
  - pyliftover (for coordinate conversion)
  - matplotlib (for visualization)

## Usage Instructions

### Basic PGS Calculation

```bash
./calculate_longevity_pgs.py --vcf your_variants.vcf --pgs pgs000906.txt.gz --output results.txt
```

### Using the Comprehensive Toolkit

```bash
# Basic usage
./longevity_pgs_toolkit.py --vcf your_variants.vcf --pgs-id PGS000906 --output-prefix longevity

# With visualization
./longevity_pgs_toolkit.py --vcf your_variants.vcf --pgs-id PGS000906 --output-prefix longevity --visualize
```

### Converting PGS Models to hg38/GRCh38

If your VCF file is based on GRCh38/hg38 but the PGS model is in GRCh37/hg19 (which is common):

```bash
./convert_pgs_to_hg38.py --input pgs000906.txt.gz --output pgs000906.hg38.txt.gz
```

Then use the converted model:

```bash
./longevity_pgs_toolkit.py --vcf your_variants.vcf --pgs pgs000906.hg38.txt.gz --output-prefix longevity
```

## Available Longevity PGS Models

The toolkit supports the following longevity-related models from the PGS Catalog:

1. **PGS000906** - Longevity PRS-5 (Tesi et al. 2021)
   - 330 variants
   - Based on GRCh37/hg19

2. **PGS002795** - Longevity (Deelen et al. 2019)
   - Available through the PGS Catalog

## Interpreting Results

The toolkit generates several output files:

1. **{prefix}_report.txt** - Detailed report with score and interpretation
2. **{prefix}_variant_details.csv** - CSV file with all variant contributions
3. **{prefix}_top_variants.png** - Visualization of top contributing variants (if --visualize is used)

Higher scores generally indicate a greater genetic predisposition for longevity, but interpretation should consider:

- The specific PGS model used and its validation statistics
- The match rate between your variants and the model
- The fact that longevity is influenced by many non-genetic factors

## Troubleshooting

### No Matching Variants Found

If the script reports 0 matching variants, possible causes include:

1. **Genome build mismatch** - Use the conversion script to match your VCF build
2. **Chromosome naming differences** - The script attempts to handle both "1" and "chr1" formats
3. **VCF format issues** - Ensure your VCF follows standard format

### Visualization Errors

If you encounter errors with visualization:

```bash
pip install matplotlib
```

## Disclaimer

This toolkit is for research and educational purposes only. The results should not be used for medical decisions without consultation with healthcare professionals. Longevity is a complex trait influenced by many factors beyond genetics.
