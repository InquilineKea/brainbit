#!/usr/bin/env python3
"""
Brain Components Polygenic Score Calculator

This script calculates polygenic scores for intracranial volume (ICV) and other brain components
using variants extracted from the supplementary table of a genomic study.
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
import time
import re

def run_command(cmd):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error message: {e.stderr}")
        return None

def prepare_brain_variants(variants_file, output_dir):
    """Prepare brain variants data for PGS calculation"""
    print(f"Reading brain variants from {variants_file}...")
    
    # Read the brain variants file
    df = pd.read_csv(variants_file)
    
    # Group by brain component (Phenotype)
    phenotypes = df['Phenotype'].unique()
    print(f"Found {len(phenotypes)} brain components in the dataset")
    
    # Create a directory for component-specific files if it doesn't exist
    components_dir = os.path.join(output_dir, "components")
    os.makedirs(components_dir, exist_ok=True)
    
    # Process each brain component
    component_files = {}
    for phenotype in phenotypes:
        # Skip non-brain component entries
        if isinstance(phenotype, float) or len(phenotype) > 50:
            continue
            
        # Filter variants for this component
        component_df = df[df['Phenotype'] == phenotype].copy()
        
        # Skip if no variants
        if len(component_df) == 0:
            continue
            
        # Convert p-values to numeric (they might be stored as strings)
        component_df['p-value'] = pd.to_numeric(component_df['p-value'], errors='coerce')
        
        # Sort by significance (p-value)
        component_df = component_df.sort_values(by='p-value')
        
        # Create a file for this component
        component_file = os.path.join(components_dir, f"{phenotype.lower().replace(' ', '_')}_variants.txt")
        
        # Prepare for PGS calculation
        # We need: CHR, POS, REF, ALT, BETA
        # Since we don't have REF/ALT in the original data, we'll use placeholders
        # and the actual alleles will be determined from the VCF
        pgs_df = pd.DataFrame({
            'SNP': component_df['Symbol'],
            'CHR': component_df['Chromosome'],
            'POS': component_df['Start basepair'],
            'REF': 'A',  # Placeholder
            'ALT': 'G',  # Placeholder
            'BETA': 1.0,  # Use uniform effect size since we don't have actual betas
            'PVAL': component_df['p-value']
        })
        
        # Save to file
        pgs_df.to_csv(component_file, sep='\t', index=False)
        component_files[phenotype] = component_file
        print(f"  - {phenotype}: {len(component_df)} variants saved to {component_file}")
    
    return component_files

def find_largest_vcf(genome_dir):
    """Find the largest VCF file in the genome directory"""
    largest_size = 0
    largest_vcf = None
    
    for root, _, files in os.walk(genome_dir):
        for file in files:
            if file.endswith('.vcf') and not file.endswith('.vcf.gz'):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                
                if file_size > largest_size:
                    largest_size = file_size
                    largest_vcf = file_path
    
    return largest_vcf

def extract_variants_with_grep(vcf_file, snp_file, output_file):
    """Extract variants using grep instead of bcftools"""
    try:
        # Read SNP file
        snps_df = pd.read_csv(snp_file, sep='\t')
        
        # Create a temporary file to store the extracted variants
        with open(output_file, 'w') as out_f:
            # First, extract the header from the VCF file
            cmd = f"grep -m 1000 '^#' {vcf_file} > {output_file}"
            run_command(cmd)
            
            # Process each chromosome and position
            total_variants = len(snps_df)
            found_variants = 0
            
            print(f"  Searching for {total_variants} variants in VCF file...")
            
            # Process in batches to avoid command line length limitations
            batch_size = 20
            for i in range(0, len(snps_df), batch_size):
                batch = snps_df.iloc[i:i+batch_size]
                
                # Create grep patterns for each variant
                patterns = []
                for _, row in batch.iterrows():
                    chr_str = str(row['CHR']).replace('.0', '')  # Remove decimal if present
                    pos_str = str(int(row['POS'])) if not pd.isna(row['POS']) else None
                    
                    if pos_str:
                        # Handle different chromosome formats (with or without 'chr' prefix)
                        patterns.append(f"^{chr_str}\\s+{pos_str}\\s+")
                        patterns.append(f"^chr{chr_str}\\s+{pos_str}\\s+")
                
                if patterns:
                    # Combine patterns with OR (|)
                    pattern_str = '|'.join(patterns)
                    
                    # Use grep to find matching variants
                    grep_cmd = f"grep -E '{pattern_str}' {vcf_file} >> {output_file}"
                    result = run_command(grep_cmd)
                    
                    if result is not None:
                        found_variants += len(patterns) // 2  # Divide by 2 because we have 2 patterns per variant
                
                # Show progress
                progress = min(100, int((i + batch_size) / total_variants * 100))
                print(f"  Progress: {progress}% ({i + min(batch_size, len(snps_df) - i)}/{total_variants})", end='\r')
            
            print(f"\n  Found approximately {found_variants} matching variants")
        
        return True
    except Exception as e:
        print(f"Error extracting variants: {e}")
        return False

def parse_vcf_genotypes(vcf_file):
    """Parse genotypes from a VCF file"""
    genotypes = []
    
    with open(vcf_file, 'r') as f:
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
                
            pos = parts[1]
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
            
            genotypes.append({
                'CHR': chrom,
                'POS': pos,
                'REF': ref,
                'ALT': alt,
                'GT': genotype
            })
    
    return genotypes

def calculate_pgs_from_vcf(vcf_file, snp_file, output_file):
    """Calculate PGS directly from extracted VCF file"""
    try:
        # Read SNP weights
        snps_df = pd.read_csv(snp_file, sep='\t')
        
        # Parse genotypes from VCF
        print("  Parsing genotypes from VCF file...")
        genotypes = parse_vcf_genotypes(vcf_file)
        
        if not genotypes:
            print("  No genotypes found in the VCF file")
            return False
        
        print(f"  Found {len(genotypes)} genotypes in the VCF file")
        
        # Create a lookup dictionary for faster matching
        genotype_lookup = {}
        for g in genotypes:
            key = f"{g['CHR']}:{g['POS']}"
            genotype_lookup[key] = g
        
        # Calculate PGS
        pgs = 0
        found_snps = 0
        missing_snps = []
        
        for _, snp in snps_df.iterrows():
            chr_str = str(snp['CHR']).replace('.0', '')
            pos_str = str(int(snp['POS'])) if not pd.isna(snp['POS']) else None
            
            if not pos_str:
                missing_snps.append(f"{snp['SNP']} (invalid position)")
                continue
            
            # Try to find the genotype
            key = f"{chr_str}:{pos_str}"
            if key in genotype_lookup:
                gt = genotype_lookup[key]['GT']
                
                # Skip missing genotypes
                if gt == './.' or gt == '.|.':
                    missing_snps.append(f"{snp['SNP']} (chr{chr_str}:{pos_str} - no genotype)")
                    continue
                
                # Calculate dosage (count of effect alleles)
                alleles = gt.replace('|', '/').split('/')
                dosage = sum(1 for a in alleles if a == '1')  # Assuming ALT is the effect allele
                
                # Add weighted contribution to PGS
                pgs += dosage * snp['BETA']
                found_snps += 1
            else:
                missing_snps.append(f"{snp['SNP']} (chr{chr_str}:{pos_str} - not found)")
        
        # Normalize by number of SNPs found
        normalized_pgs = 0
        if found_snps > 0:
            normalized_pgs = pgs / found_snps
        
        # Write results
        with open(output_file, 'w') as f:
            f.write(f"Total SNPs in model: {len(snps_df)}\n")
            f.write(f"SNPs found in your genome: {found_snps}\n")
            f.write(f"SNPs missing from your genome: {len(missing_snps)}\n\n")
            
            if missing_snps:
                f.write("Missing SNPs (first 10):\n")
                for snp in missing_snps[:10]:
                    f.write(f"- {snp}\n")
                if len(missing_snps) > 10:
                    f.write(f"... and {len(missing_snps) - 10} more\n")
                f.write("\n")
            
            f.write(f"Raw Polygenic Score: {pgs:.6f}\n")
            f.write(f"Normalized Polygenic Score: {normalized_pgs:.6f}\n")
        
        return normalized_pgs, found_snps, len(missing_snps)
        
    except Exception as e:
        print(f"Error calculating PGS: {e}")
        return False

def main():
    # Define file paths
    base_dir = Path("/Users/simfish/Downloads/Genome")
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    brain_variants_file = base_dir / "brainsize_variants_clean.csv"
    output_dir = script_dir
    
    # Create output directory for results
    results_dir = output_dir / "results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Prepare brain variants data
    component_files = prepare_brain_variants(brain_variants_file, output_dir)
    
    # Find the largest VCF file
    vcf_file = find_largest_vcf(base_dir)
    if not vcf_file:
        print("No VCF files found in the genome directory.")
        sys.exit(1)
    
    print(f"Using VCF file: {vcf_file}")
    
    # Calculate PGS for each brain component
    results = []
    for component, snp_file in component_files.items():
        print(f"\nProcessing {component}...")
        
        # Define output files
        extracted_vcf = results_dir / f"{component.lower().replace(' ', '_')}_variants.vcf"
        pgs_report = results_dir / f"{component.lower().replace(' ', '_')}_pgs.txt"
        
        # Extract variants using grep
        print(f"  Extracting variants for {component}...")
        if not extract_variants_with_grep(vcf_file, snp_file, extracted_vcf):
            print(f"  Failed to extract variants for {component}.")
            continue
        
        # Calculate PGS
        print(f"  Calculating polygenic score for {component}...")
        pgs_result = calculate_pgs_from_vcf(extracted_vcf, snp_file, pgs_report)
        
        if pgs_result:
            normalized_pgs, found_snps, missing_snps = pgs_result
            results.append({
                'Component': component,
                'PGS': normalized_pgs,
                'SNPs_Found': found_snps,
                'SNPs_Missing': missing_snps,
                'Total_SNPs': found_snps + missing_snps
            })
            print(f"  PGS calculation complete for {component}. Score: {normalized_pgs:.6f}")
        else:
            print(f"  Failed to calculate polygenic score for {component}.")
    
    # Create summary report
    summary_file = results_dir / "brain_components_pgs_summary.md"
    with open(summary_file, 'w') as f:
        f.write("# Brain Components Polygenic Score Summary\n\n")
        f.write("This report summarizes the polygenic scores for various brain components based on\n")
        f.write("genetic variants associated with brain structure sizes.\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Analysis completed on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"VCF file used: {os.path.basename(vcf_file)}\n\n")
        
        # Sort results by PGS (highest first)
        results.sort(key=lambda x: x['PGS'], reverse=True)
        
        f.write("## Polygenic Scores by Brain Component\n\n")
        f.write("| Brain Component | Polygenic Score | SNPs Found | Total SNPs | % SNPs Found |\n")
        f.write("|----------------|----------------|------------|------------|-------------|\n")
        
        for result in results:
            percent_found = (result['SNPs_Found'] / result['Total_SNPs'] * 100) if result['Total_SNPs'] > 0 else 0
            f.write(f"| {result['Component']} | {result['PGS']:.6f} | {result['SNPs_Found']} | {result['Total_SNPs']} | {percent_found:.1f}% |\n")
        
        f.write("\n## Interpretation\n\n")
        f.write("The polygenic scores represent your genetic predisposition for the size of each brain component.\n")
        f.write("Higher scores suggest a genetic tendency toward larger volumes for that brain component.\n\n")
        
        f.write("### Your Brain Size Profile\n\n")
        f.write("Based on your genetic variants, you may have:\n\n")
        
        # Provide interpretations for top and bottom components
        if results:
            top_components = results[:3]
            bottom_components = results[-3:] if len(results) >= 3 else []
            
            f.write("**Potentially Larger Components:**\n")
            for comp in top_components:
                f.write(f"- {comp['Component']} (Score: {comp['PGS']:.6f})\n")
            
            f.write("\n**Potentially Smaller Components:**\n")
            for comp in reversed(bottom_components):
                f.write(f"- {comp['Component']} (Score: {comp['PGS']:.6f})\n")
        
        f.write("\n## Disclaimer\n\n")
        f.write("These scores are based on published genome-wide significant variants and are for\n")
        f.write("research purposes only. They should not be used for clinical decision-making.\n")
        f.write("Brain structure is influenced by both genetic and environmental factors.\n")
    
    print(f"\nAnalysis complete! Summary report saved to {summary_file}")
    
    # Display the summary report
    with open(summary_file, 'r') as f:
        print("\n" + f.read())

if __name__ == "__main__":
    main()
