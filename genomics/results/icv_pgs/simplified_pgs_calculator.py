#!/usr/bin/env python3
"""
Simplified Polygenic Score (PGS) Calculator for Intracranial Volume
This script calculates a PGS without requiring bcftools by directly parsing VCF files.
"""

import os
import sys
import gzip
import pandas as pd
import numpy as np
from pathlib import Path

def parse_vcf(vcf_path):
    """Parse a VCF file and return a DataFrame with variant information"""
    # Check if the file is gzipped
    is_gzipped = vcf_path.endswith('.gz')
    
    # Open the file with appropriate method
    opener = gzip.open if is_gzipped else open
    
    variants = []
    with opener(vcf_path, 'rt') as f:
        for line in f:
            # Skip header lines
            if line.startswith('#'):
                if line.startswith('#CHROM'):
                    # Get the sample name from the header
                    header_parts = line.strip().split('\t')
                    sample_idx = 9  # VCF format has sample data starting at column 10 (index 9)
                continue
            
            # Parse variant line
            parts = line.strip().split('\t')
            if len(parts) < 10:  # VCF must have at least 10 columns
                continue
                
            chrom = parts[0]
            # Remove 'chr' prefix if present for consistent matching
            if chrom.startswith('chr'):
                chrom = chrom[3:]
                
            pos = int(parts[1])
            rsid = parts[2]
            ref = parts[3]
            alt = parts[4]
            
            # Get genotype
            format_field = parts[8].split(':')
            sample_data = parts[9].split(':')
            
            # Find GT field index
            gt_idx = format_field.index('GT') if 'GT' in format_field else None
            
            if gt_idx is not None:
                genotype = sample_data[gt_idx]
            else:
                genotype = './.'  # Missing genotype
            
            variants.append({
                'CHROM': chrom,
                'POS': pos,
                'ID': rsid,
                'REF': ref,
                'ALT': alt,
                'GT': genotype
            })
    
    return pd.DataFrame(variants)

def calculate_pgs(variants_df, snps_df, output_file):
    """Calculate polygenic score based on variants"""
    # Ensure chromosome is string type for both dataframes for proper matching
    variants_df['CHROM'] = variants_df['CHROM'].astype(str)
    snps_df['CHR'] = snps_df['CHR'].astype(str)
    
    # Calculate PGS
    pgs = 0
    found_snps = 0
    missing_snps = []
    
    for _, snp in snps_df.iterrows():
        # Find the genotype for this SNP
        matches = variants_df[
            (variants_df['CHROM'] == str(snp['CHR'])) & 
            (variants_df['POS'] == snp['POS'])
        ]
        
        if len(matches) == 0:
            missing_snps.append(f"{snp['SNP']} (chr{snp['CHR']}:{snp['POS']})")
            continue
            
        # Get the genotype
        gt = matches.iloc[0]['GT']
        ref = matches.iloc[0]['REF']
        alt = matches.iloc[0]['ALT']
        
        # Skip if genotype is missing
        if gt == './.' or gt == '.|.':
            missing_snps.append(f"{snp['SNP']} (chr{snp['CHR']}:{snp['POS']}) - missing genotype")
            continue
        
        # Determine effect allele (assuming it's ALT in the GWAS)
        effect_allele = snp['ALT']
        
        # Calculate dosage (count of effect alleles)
        alleles = gt.replace('|', '/').split('/')
        
        try:
            # Convert allele indices to actual alleles
            actual_alleles = []
            for a in alleles:
                if a == '0':
                    actual_alleles.append(ref)
                elif a == '1':
                    actual_alleles.append(alt)
                else:
                    # Handle multi-allelic sites or missing data
                    actual_alleles.append(None)
            
            # Count effect alleles
            dosage = sum(1 for a in actual_alleles if a == effect_allele and a is not None)
            
            # Add weighted contribution to PGS
            pgs += dosage * snp['BETA']
            found_snps += 1
            
        except Exception as e:
            print(f"Error processing SNP {snp['SNP']}: {e}")
            missing_snps.append(f"{snp['SNP']} (chr{snp['CHR']}:{snp['POS']}) - error")
    
    # Normalize by number of SNPs found
    if found_snps > 0:
        pgs = pgs / found_snps
    
    # Write results
    with open(output_file, 'w') as f:
        f.write("# Intracranial Volume Polygenic Score Report\n\n")
        f.write(f"Total SNPs in model: {len(snps_df)}\n")
        f.write(f"SNPs found in your genome: {found_snps}\n")
        f.write(f"SNPs missing from your genome: {len(missing_snps)}\n\n")
        
        if missing_snps:
            f.write("Missing SNPs:\n")
            for snp in missing_snps[:10]:  # Show only first 10
                f.write(f"- {snp}\n")
            if len(missing_snps) > 10:
                f.write(f"... and {len(missing_snps) - 10} more\n")
            f.write("\n")
        
        f.write(f"Your Intracranial Volume Polygenic Score: {pgs:.6f}\n\n")
        
        # Interpret the score
        f.write("## Interpretation\n\n")
        f.write("The polygenic score represents your genetic predisposition for intracranial volume.\n")
        f.write("Positive scores suggest a genetic tendency toward larger intracranial volume,\n")
        f.write("while negative scores suggest a genetic tendency toward smaller intracranial volume.\n\n")
        
        f.write("Note: This score is based on published genome-wide significant variants and is for\n")
        f.write("research purposes only. It should not be used for clinical decision-making.\n")
        f.write("Intracranial volume is influenced by both genetic and environmental factors.\n")
    
    return True

def main():
    # Define file paths
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    snp_file = script_dir / "icv_significant_snps.txt"
    pgs_report = script_dir / "icv_pgs_report.txt"
    
    # Read SNP data
    snps_df = pd.read_csv(snp_file, sep='\t', header=None)
    
    # Check if the SNP file has headers
    if isinstance(snps_df.iloc[0, 0], str) and snps_df.iloc[0, 0].startswith('rs'):
        # File doesn't have headers, so add them
        snps_df.columns = ['SNP', 'CHR', 'POS', 'REF', 'ALT', 'ALT_FREQ', 'BETA', 'SE', 'PVAL']
    
    # Find VCF file
    genome_dir = Path("/Users/simfish/Downloads/Genome")
    
    # Look for VCF files in the genome directory
    vcf_files = list(genome_dir.glob("*.vcf")) + list(genome_dir.glob("*.vcf.gz"))
    if not vcf_files:
        print("No VCF files found in the genome directory.")
        sys.exit(1)
    
    # Use the first VCF file found
    vcf_file = vcf_files[0]
    print(f"Using VCF file: {vcf_file}")
    
    # Parse VCF file
    print("Parsing VCF file...")
    try:
        variants_df = parse_vcf(vcf_file)
        print(f"Found {len(variants_df)} variants in the VCF file.")
    except Exception as e:
        print(f"Error parsing VCF file: {e}")
        sys.exit(1)
    
    # Calculate PGS
    print("Calculating polygenic score...")
    if not calculate_pgs(variants_df, snps_df, pgs_report):
        print("Failed to calculate polygenic score.")
        sys.exit(1)
    
    print(f"PGS calculation complete. Results saved to {pgs_report}")
    
    # Display the report
    with open(pgs_report, 'r') as f:
        print("\n" + f.read())

if __name__ == "__main__":
    main()
