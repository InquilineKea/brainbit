#!/usr/bin/env python3
"""
Extract Brain Size Variants from Excel File

This script extracts Supplementary Table 5 from media-2.xlsx and exports it to a new CSV file
specifically for brain size variants.
"""

import os
import pandas as pd

# Define file paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
EXCEL_FILE = os.path.join(BASE_DIR, "media-2.xlsx")
OUTPUT_FILE = os.path.join(BASE_DIR, "brainsize_variants.csv")

def extract_brainsize_variants():
    """Extract brain size variants from Excel file and save to CSV."""
    try:
        # Read the Excel file, specifically Supplementary Table 5
        print(f"Reading Supplementary Table 5 from {EXCEL_FILE}...")
        df = pd.read_excel(EXCEL_FILE, sheet_name="Supplementary Table 5")
        
        # Display basic information about the sheet
        print(f"Sheet contains {len(df)} rows and {len(df.columns)} columns")
        print("Column names:", df.columns.tolist())
        
        # Save to CSV
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"Successfully exported brain size variants to {OUTPUT_FILE}")
        
        # Display the first few rows for verification
        print("\nFirst 5 rows of the exported data:")
        print(df.head())
        
        return True
    except Exception as e:
        print(f"Error extracting brain size variants: {e}")
        return False

if __name__ == "__main__":
    extract_brainsize_variants()
