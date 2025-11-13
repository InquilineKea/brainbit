#!/usr/bin/env python3
"""
Calculate Polygenic Score (PGS) for Intracranial Volume based on significant SNPs
from genome-wide association studies.
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path

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

def extract_genotypes(vcf_file, snp_file, output_file):
    """Extract genotypes for SNPs of interest from VCF file"""
    # Create a temporary file with SNP positions
    temp_positions_file = "temp_positions.txt"
    snps_df = pd.read_csv(snp_file, sep='\t', header=None)
    
    # Check if the SNP file has headers
    if isinstance(snps_df.iloc[0, 0], str) and snps_df.iloc[0, 0].startswith('rs'):
        # File doesn't have headers, so add them
        snps_df.columns = ['SNP', 'CHR', 'POS', 'REF', 'ALT', 'ALT_FREQ', 'BETA', 'SE', 'PVAL']
    
    # Extract chromosome and position for filtering
    positions = snps_df[['CHR', 'POS']].copy()
    positions.to_csv(temp_positions_file, sep='\t', index=False, header=False)
    
    # Use bcftools to extract SNPs
    cmd = f"bcftools view -R {temp_positions_file} {vcf_file} -Ov -o {output_file}"
    result = run_command(cmd)
    
    # Clean up
    if os.path.exists(temp_positions_file):
        os.remove(temp_positions_file)
    
    return result is not None

def calculate_pgs(genotypes_file, snp_file, output_file):
    """Calculate polygenic score based on extracted genotypes"""
    # Read SNP weights
    snps_df = pd.read_csv(snp_file, sep='\t', header=None)
    
    # Check if the SNP file has headers
    if isinstance(snps_df.iloc[0, 0], str) and snps_df.iloc[0, 0].startswith('rs'):
        # File doesn't have headers, so add them
        snps_df.columns = ['SNP', 'CHR', 'POS', 'REF', 'ALT', 'ALT_FREQ', 'BETA', 'SE', 'PVAL']
    
    # Read genotypes
    try:
        # Try using vcftools to extract genotypes in a more readable format
        genotypes_table = "temp_genotypes.txt"
        cmd = f"bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT[\\t%GT]\\n' {genotypes_file} > {genotypes_table}"
        run_command(cmd)
        
        # Read the genotypes
        geno_df = pd.read_csv(genotypes_table, sep='\t', header=None)
        geno_df.columns = ['CHR', 'POS', 'REF', 'ALT', 'GT']
        
        # Convert genotype to dosage (count of effect alleles)
        def gt_to_dosage(gt, ref, alt, effect_allele):
            if gt == './.':  # Missing genotype
                return np.nan
            
            alleles = gt.replace('|', '/').split('/')
            
            # Count effect alleles
            if effect_allele == alt:
                return sum(1 for a in alleles if a == '1')
            else:  # effect_allele == ref
                return sum(1 for a in alleles if a == '0')
        
        # Calculate PGS
        pgs = 0
        found_snps = 0
        missing_snps = []
        
        for _, snp in snps_df.iterrows():
            # Find the genotype for this SNP
            matches = geno_df[(geno_df['CHR'] == snp['CHR']) & (geno_df['POS'] == snp['POS'])]
            
            if len(matches) == 0:
                missing_snps.append(f"{snp['SNP']} (chr{snp['CHR']}:{snp['POS']})")
                continue
                
            # Get the genotype
            gt = matches.iloc[0]['GT']
            ref = matches.iloc[0]['REF']
            alt = matches.iloc[0]['ALT']
            
            # Determine effect allele (assuming it's ALT in the GWAS)
            effect_allele = snp['ALT']
            
            # Calculate dosage
            dosage = gt_to_dosage(gt, ref, alt, effect_allele)
            
            if not np.isnan(dosage):
                # Add weighted contribution to PGS
                pgs += dosage * snp['BETA']
                found_snps += 1
        
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
        
        # Clean up
        if os.path.exists(genotypes_table):
            os.remove(genotypes_table)
            
        return True
        
    except Exception as e:
        print(f"Error calculating PGS: {e}")
        return False

def main():
    # Define file paths
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    snp_file = script_dir / "icv_significant_snps.txt"
    
    # Find VCF file
    vcf_file = None
    genome_dir = Path("/Users/simfish/Downloads/Genome")
    
    # Look for VCF files in the genome directory
    vcf_files = list(genome_dir.glob("*.vcf*"))
    if not vcf_files:
        print("No VCF files found in the genome directory.")
        sys.exit(1)
    
    # Use the first VCF file found
    vcf_file = vcf_files[0]
    print(f"Using VCF file: {vcf_file}")
    
    # Define output files
    extracted_genotypes = script_dir / "icv_extracted_genotypes.vcf"
    pgs_report = script_dir / "icv_pgs_report.txt"
    
    # Extract genotypes
    print("Extracting genotypes for ICV-associated SNPs...")
    if not extract_genotypes(vcf_file, snp_file, extracted_genotypes):
        print("Failed to extract genotypes.")
        sys.exit(1)
    
    # Calculate PGS
    print("Calculating polygenic score...")
    if not calculate_pgs(extracted_genotypes, snp_file, pgs_report):
        print("Failed to calculate polygenic score.")
        sys.exit(1)
    
    print(f"PGS calculation complete. Results saved to {pgs_report}")
    
    # Display the report
    with open(pgs_report, 'r') as f:
        print("\n" + f.read())

if __name__ == "__main__":
    main()
