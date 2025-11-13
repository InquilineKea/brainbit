# Brain Size Variants Analysis

This directory contains files related to the analysis of genetic variants associated with brain size, extracted from the supplementary tables of a genomic study.

## Files Created

1. **brainsize_variants.csv**
   - Raw export of Supplementary Table 5 from media-2.xlsx
   - Contains all statistically significant gene-based test results from MAGMA analysis
   - Includes variants for all brain regions (amygdala, thalamus, ICV, etc.)

2. **brainsize_variants_clean.csv**
   - Cleaned version of the raw export with proper column headers
   - Contains the same data as brainsize_variants.csv but in a more usable format

3. **icv_variants.csv**
   - Filtered dataset containing only variants associated with Intracranial Volume (ICV)
   - ICV is the primary measure of overall brain size
   - Contains 132 genetic variants significantly associated with brain size
   - Sorted by p-value (most significant first)

4. **icv_variants_summary.md**
   - Summary report of the ICV variants
   - Includes chromosome distribution and top 20 most significant genes
   - Provides a quick overview of the brain size genetic variants

## Data Overview

The extracted data shows 132 genetic variants significantly associated with intracranial volume (brain size). The most significant genes include TARBP2, USMG5, INA, TAF5, and PDCD11. Chromosomes 3, 10, 12, and 17 contain the highest number of brain size-associated variants.

## Usage

These files can be used for further analysis of genetic factors influencing brain size, potentially in conjunction with other genomic data or for comparison with other phenotypic traits.

## Source

The data was extracted from Supplementary Table 5 of the media-2.xlsx file, which contains genome-wide significant gene-based test results using MAGMA analysis for various brain structures.
