#!/usr/bin/env python3
"""
Extract ICV (Intracranial Volume) Variants

This script extracts only the ICV (brain size) variants from the cleaned brain size variants file
and creates a dedicated file for ICV analysis.
"""

import os
import pandas as pd

# Define file paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
INPUT_FILE = os.path.join(BASE_DIR, "brainsize_variants_clean.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "icv_variants.csv")

def extract_icv_variants():
    """Extract only ICV variants from the brain size variants file."""
    try:
        # Read the cleaned CSV file
        print(f"Reading {INPUT_FILE}...")
        df = pd.read_csv(INPUT_FILE)
        
        # Filter for ICV (Intracranial Volume) variants only
        icv_df = df[df['Phenotype'] == 'ICV']
        
        # Sort by p-value (most significant first)
        icv_df = icv_df.sort_values(by='p-value')
        
        # Save to CSV
        icv_df.to_csv(OUTPUT_FILE, index=False)
        print(f"Successfully extracted {len(icv_df)} ICV variants to: {OUTPUT_FILE}")
        
        # Display the first few rows for verification
        print("\nFirst 10 most significant ICV variants:")
        print(icv_df.head(10))
        
        # Create a summary file with additional information
        create_summary_file(icv_df)
        
        return True
    except Exception as e:
        print(f"Error extracting ICV variants: {e}")
        return False

def create_summary_file(icv_df):
    """Create a summary markdown file with information about the ICV variants."""
    summary_file = os.path.join(BASE_DIR, "icv_variants_summary.md")
    
    with open(summary_file, 'w') as f:
        f.write("# Intracranial Volume (ICV) Genetic Variants Summary\n\n")
        f.write("This file contains genetic variants significantly associated with intracranial volume (brain size) ")
        f.write("based on MAGMA gene-based test results.\n\n")
        
        f.write(f"## Overview\n\n")
        f.write(f"Total ICV-associated variants: {len(icv_df)}\n\n")
        
        f.write("## Chromosome Distribution\n\n")
        chrom_counts = icv_df['Chromosome'].value_counts().sort_index()
        for chrom, count in chrom_counts.items():
            f.write(f"- Chromosome {chrom}: {count} variants\n")
        
        f.write("\n## Top 20 Most Significant Genes\n\n")
        f.write("| Gene Symbol | Chromosome | Position | p-value |\n")
        f.write("|------------|------------|----------|--------|\n")
        
        for _, row in icv_df.head(20).iterrows():
            f.write(f"| {row['Symbol']} | {row['Chromosome']} | {row['Start basepair']}-{row['Stop basepair']} | {row['p-value']} |\n")
    
    print(f"Created summary file: {summary_file}")

if __name__ == "__main__":
    extract_icv_variants()
