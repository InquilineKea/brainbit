#!/usr/bin/env python3
"""
Clean Brain Size Variants CSV

This script cleans the exported brain size variants CSV file by:
1. Fixing column headers
2. Removing any unnecessary rows
3. Creating a more readable format
"""

import os
import pandas as pd

# Define file paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
INPUT_FILE = os.path.join(BASE_DIR, "brainsize_variants.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "brainsize_variants_clean.csv")

def clean_brainsize_variants():
    """Clean the brain size variants CSV file."""
    try:
        # Read the CSV file
        print(f"Reading {INPUT_FILE}...")
        df = pd.read_csv(INPUT_FILE)
        
        # The first row contains the actual column names
        # Extract them and set as new column names
        new_columns = df.iloc[0].tolist()
        
        # Create a new dataframe with proper column names, skipping the first row
        clean_df = pd.DataFrame(df.values[1:], columns=new_columns)
        
        # Clean up column names if needed
        clean_df.columns = [col.strip() for col in clean_df.columns]
        
        # Save to CSV
        clean_df.to_csv(OUTPUT_FILE, index=False)
        print(f"Successfully created cleaned brain size variants file: {OUTPUT_FILE}")
        
        # Display the first few rows for verification
        print("\nFirst 5 rows of the cleaned data:")
        print(clean_df.head())
        
        # Display summary statistics
        print("\nSummary of brain regions in the dataset:")
        region_counts = clean_df['Phenotype'].value_counts()
        for region, count in region_counts.items():
            print(f"  {region}: {count} variants")
        
        return True
    except Exception as e:
        print(f"Error cleaning brain size variants: {e}")
        return False

if __name__ == "__main__":
    clean_brainsize_variants()
