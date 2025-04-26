#!/usr/bin/env python3
"""
List all sheets in an Excel file
"""

import os
import pandas as pd

# Define file path
EXCEL_FILE = "/Users/simfish/Downloads/Genome/media-2.xlsx"

def list_excel_sheets():
    """List all sheets in the Excel file."""
    try:
        # Get the Excel file information
        xl = pd.ExcelFile(EXCEL_FILE)
        
        # Print all sheet names
        print(f"Sheets in {EXCEL_FILE}:")
        for i, sheet_name in enumerate(xl.sheet_names, 1):
            print(f"{i}. {sheet_name}")
        
        # For each sheet, print some basic info
        for sheet_name in xl.sheet_names:
            try:
                df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
                print(f"\nSheet: {sheet_name}")
                print(f"  Rows: {len(df)}")
                print(f"  Columns: {len(df.columns)}")
                print(f"  Column names: {df.columns.tolist()[:5]}...")
            except Exception as e:
                print(f"\nError reading sheet {sheet_name}: {e}")
        
        return True
    except Exception as e:
        print(f"Error listing Excel sheets: {e}")
        return False

if __name__ == "__main__":
    list_excel_sheets()
