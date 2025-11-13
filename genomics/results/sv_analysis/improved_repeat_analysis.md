# Improved Repetitive Element Analysis in Structural Variant Insertions

Analysis Date: Sun Mar  2 12:10:18 EST 2025

## Overview

Total complete sequences analyzed: 0
Total truncated sequences analyzed: 40
Total sequences analyzed: 40

## Repetitive Element Analysis - Complete Sequences

| Repeat Type | Count | Percentage |
|-------------|-------|------------|
| Alu | 0 | 0.00% |
| LINE | 0 | 0.00% |
| SINE | 0 | 0.00% |
| Simple Repeats | 0 | 0.00% |
| Microsatellites | 0 | 0.00% |
| Minisatellites | 0 | 0.00% |

## Repetitive Element Analysis - Truncated Sequences

| Repeat Type | Count | Percentage |
|-------------|-------|------------|
| Alu | 1 | 2.50% |
| LINE | 0 | 0.00% |
| SINE | 4 | 10.00% |
| Simple Repeats | 11 | 27.50% |
| Microsatellites | 10 | 25.00% |
| Minisatellites | 2 | 5.00% |

## Combined Repetitive Element Analysis

| Repeat Type | Complete | Truncated | Total | Overall Percentage |
|-------------|----------|-----------|-------|-------------------|
| Alu | 0 | 1 | 1 | 2.50% |
| LINE | 0 | 0 | 0 | 0.00% |
| SINE | 0 | 4 | 4 | 10.00% |
| Simple Repeats | 0 | 11 | 11 | 27.50% |
| Microsatellites | 0 | 10 | 10 | 25.00% |
| Minisatellites | 0 | 2 | 2 | 5.00% |

## Chromosome Distribution of Repetitive Elements

| Chromosome | Alu | LINE | SINE | Simple Repeats | Microsatellites | Minisatellites |
|------------|-----|------|------|----------------|-----------------|---------------|
| chr1 | 1 | 0 | 4 | 11 | 10 | 2 |

## Examples of Insertions with Repetitive Elements

### Alu Examples

**Example 1**: chr1:1929384 (Length: 261)
```
GAGGGGACAGGTCTGGGGAGGCAGGAGAGA
```
*Truncated sequence*

### SINE Examples

**Example 1**: chr1:7018128 (Length: 166)
```
AATGCCAGGGTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

**Example 2**: chr1:8386567 (Length: 344)
```
GAACTCTTTTTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

**Example 3**: chr1:23117477 (Length: 134)
```
TCTCTCTCTCCCCCCCCCCCCAACCAGCCC
```
*Truncated sequence*

### Simple Repeats Examples

**Example 1**: chr1:1929384 (Length: 261)
```
GAGGGGACAGGTCTGGGGAGGCAGGAGAGA
```
*Truncated sequence*

**Example 2**: chr1:8276902 (Length: 377)
```
ACACATACACACACCACACACATACACACA
```
*Truncated sequence*

**Example 3**: chr1:11373881 (Length: 555)
```
GTGTATGTGGTGTGTGTGGTCTGCATGTGG
```
*Truncated sequence*

### Microsatellites Examples

**Example 1**: chr1:7018128 (Length: 166)
```
AATGCCAGGGTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

**Example 2**: chr1:8276902 (Length: 377)
```
ACACATACACACACCACACACATACACACA
```
*Truncated sequence*

**Example 3**: chr1:8386567 (Length: 344)
```
GAACTCTTTTTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

### Minisatellites Examples

**Example 1**: chr1:7018128 (Length: 166)
```
AATGCCAGGGTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

**Example 2**: chr1:8386567 (Length: 344)
```
GAACTCTTTTTTTTTTTTTTTTTTTTTTTT
```
*Truncated sequence*

## Why Previous Analysis Showed Low Representation

The previous analysis showed low representation of SINE elements, simple repeats, and satellites for several reasons:

1. **Limited Sample Size**: The previous analysis only examined 10 complete sequences, which is too small to capture the diversity of repetitive elements.

2. **Exclusion of Truncated Sequences**: Sequences containing '...' were excluded, which likely removed many longer insertions that would contain repetitive elements.

3. **Narrow Pattern Definitions**: The previous patterns used to identify repetitive elements were too specific and missed many variants.

4. **Focus on Complete Matches**: The previous approach may have required more complete matches of repetitive element signatures.

## Biological Significance

Repetitive elements in structural variant insertions have important biological implications:

1. **Alu and LINE elements**: Mobile elements that can cause insertional mutagenesis and genomic instability
2. **SINE elements**: Can affect gene expression when inserted near genes
3. **Simple repeats and microsatellites**: Associated with genomic instability and certain genetic disorders
4. **Minisatellites**: Can influence recombination rates and chromosome stability

## Next Steps

1. Compare the distribution of repetitive elements in your genome with population databases
2. Analyze the genomic context of insertions containing specific repetitive elements
3. Investigate whether any repetitive element insertions are associated with genes or regulatory regions
4. Consider more detailed analysis of specific repetitive element families of interest
