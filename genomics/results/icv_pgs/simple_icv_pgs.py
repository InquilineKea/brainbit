#!/usr/bin/env python3
"""
Very Simple Intracranial Volume Polygenic Score Calculator
This script uses only standard library modules to calculate a basic PGS.
"""

import os
import sys
import gzip
import re
from pathlib import Path

def parse_snp_file(snp_file_path):
    """Parse the SNP file with effect sizes"""
    snps = []
    with open(snp_file_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 8 and parts[0].startswith('rs'):
                snp = {
                    'SNP': parts[0],
                    'CHR': parts[1],
                    'POS': int(parts[2]),
                    'REF': parts[3],
                    'ALT': parts[4],
                    'ALT_FREQ': float(parts[5]),
                    'BETA': float(parts[6]),
                    'SE': float(parts[7])
                }
                snps.append(snp)
    return snps

def find_vcf_file(genome_dir):
    """Find a VCF file in the genome directory"""
    for root, _, files in os.walk(genome_dir):
        for file in files:
            if file.endswith('.vcf') and not file.endswith('.vcf.gz'):
                return os.path.join(root, file)
    return None

def extract_variants_from_vcf(vcf_path, snps):
    """Extract variants from VCF file that match SNPs of interest"""
    # Create a dictionary for fast lookup of SNPs by chromosome and position
    snp_lookup = {}
    for snp in snps:
        key = f"{snp['CHR']}:{snp['POS']}"
        snp_lookup[key] = snp
    
    found_variants = []
    with open(vcf_path, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
                
            parts = line.strip().split('\t')
            if len(parts) < 10:
                continue
                
            chrom = parts[0]
            # Remove 'chr' prefix if present
            if chrom.startswith('chr'):
                chrom = chrom[3:]
                
            pos = int(parts[1])
            
            # Check if this variant is in our SNPs of interest
            key = f"{chrom}:{pos}"
            if key in snp_lookup:
                ref = parts[3]
                alt = parts[4]
                
                # Extract genotype
                format_field = parts[8].split(':')
                sample_data = parts[9].split(':')
                
                gt_idx = None
                for i, field in enumerate(format_field):
                    if field == 'GT':
                        gt_idx = i
                        break
                
                if gt_idx is not None and gt_idx < len(sample_data):
                    genotype = sample_data[gt_idx]
                else:
                    genotype = './.'
                
                variant = {
                    'CHROM': chrom,
                    'POS': pos,
                    'REF': ref,
                    'ALT': alt,
                    'GT': genotype,
                    'SNP': snp_lookup[key]['SNP'],
                    'BETA': snp_lookup[key]['BETA']
                }
                found_variants.append(variant)
    
    return found_variants

def calculate_pgs(variants, output_file):
    """Calculate polygenic score based on variants"""
    pgs = 0
    found_snps = 0
    missing_snps = []
    
    # Track which SNPs we've found
    found_snp_ids = set()
    for variant in variants:
        found_snp_ids.add(variant['SNP'])
        
        # Parse genotype
        gt = variant['GT']
        if gt == './.' or gt == '.|.':
            continue
            
        # Calculate dosage (count of effect alleles)
        alleles = gt.replace('|', '/').split('/')
        dosage = 0
        
        for a in alleles:
            if a == '1':  # Assuming ALT is the effect allele
                dosage += 1
        
        # Add weighted contribution to PGS
        pgs += dosage * variant['BETA']
        found_snps += 1
    
    # Normalize by number of SNPs found
    if found_snps > 0:
        pgs = pgs / found_snps
    
    # Write results
    with open(output_file, 'w') as f:
        f.write("# Intracranial Volume Polygenic Score Report\n\n")
        f.write(f"Total SNPs analyzed: {len(variants)}\n")
        f.write(f"SNPs found with genotypes: {found_snps}\n\n")
        
        f.write(f"Your Intracranial Volume Polygenic Score: {pgs:.6f}\n\n")
        
        # Interpret the score
        f.write("## Interpretation\n\n")
        f.write("The polygenic score represents your genetic predisposition for intracranial volume.\n")
        f.write("Positive scores suggest a genetic tendency toward larger intracranial volume,\n")
        f.write("while negative scores suggest a genetic tendency toward smaller intracranial volume.\n\n")
        
        f.write("Note: This score is based on published genome-wide significant variants and is for\n")
        f.write("research purposes only. It should not be used for clinical decision-making.\n")
        f.write("Intracranial volume is influenced by both genetic and environmental factors.\n")
    
    return pgs, found_snps

def main():
    # Define file paths
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    snp_file = script_dir / "icv_significant_snps.txt"
    pgs_report = script_dir / "icv_pgs_report.txt"
    
    # Parse SNP data
    print("Reading SNP data...")
    snps = parse_snp_file(snp_file)
    print(f"Found {len(snps)} SNPs in the SNP file.")
    
    # Find VCF file
    genome_dir = "/Users/simfish/Downloads/Genome"
    vcf_file = find_vcf_file(genome_dir)
    
    if not vcf_file:
        print("No suitable VCF file found in the genome directory.")
        sys.exit(1)
    
    print(f"Using VCF file: {vcf_file}")
    
    # Extract variants
    print("Extracting variants from VCF file...")
    variants = extract_variants_from_vcf(vcf_file, snps)
    print(f"Found {len(variants)} matching variants in the VCF file.")
    
    # Calculate PGS
    print("Calculating polygenic score...")
    pgs, found_snps = calculate_pgs(variants, pgs_report)
    
    print(f"PGS calculation complete. Results saved to {pgs_report}")
    print(f"Your Intracranial Volume Polygenic Score: {pgs:.6f} (based on {found_snps} variants)")
    
    # Display the report
    with open(pgs_report, 'r') as f:
        print("\n" + f.read())

if __name__ == "__main__":
    main()
