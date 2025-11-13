#!/usr/bin/env python3
"""
Calculate Longevity Polygenic Score (PGS) using PGS000906 model
"""

import argparse
import gzip
import os
import sys
from collections import defaultdict

def parse_pgs_file(pgs_file):
    """Parse PGS scoring file and return a dictionary of variants with weights"""
    variant_weights = {}
    
    # Determine if file is gzipped
    open_func = gzip.open if pgs_file.endswith('.gz') else open
    mode = 'rt' if pgs_file.endswith('.gz') else 'r'
    
    with open_func(pgs_file, mode) as f:
        header = None
        for line in f:
            if line.startswith('#'):
                continue
            
            if header is None:
                header = line.strip().split('\t')
                continue
            
            fields = line.strip().split('\t')
            data = dict(zip(header, fields))
            
            # Create a unique variant key
            variant_key = (
                data['chr_name'], 
                int(data['chr_position']), 
                data['effect_allele'], 
                data['other_allele']
            )
            
            variant_weights[variant_key] = float(data['effect_weight'])
    
    print(f"Loaded {len(variant_weights)} variants from PGS file")
    return variant_weights

def parse_vcf_file(vcf_file, variant_weights):
    """Parse VCF file and calculate PGS score"""
    total_score = 0
    matched_variants = 0
    missing_variants = 0
    
    # Track variants found in VCF but not in PGS model
    pgs_chromosomes = set(chrom for chrom, _, _, _ in variant_weights.keys())
    
    # Convert chromosome names to ensure matching (some VCFs use 'chr1' while PGS may use '1')
    chr_mapping = {f"chr{c}": c for c in list(range(1, 23)) + ['X', 'Y']}
    chr_mapping.update({c: c for c in list(map(str, range(1, 23))) + ['X', 'Y']})
    
    # Open VCF file
    with open(vcf_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            
            fields = line.strip().split('\t')
            chrom = fields[0]
            pos = int(fields[1])
            ref = fields[3]
            alt_alleles = fields[4].split(',')
            
            # Skip non-biallelic variants for simplicity
            if len(alt_alleles) > 1:
                continue
                
            alt = alt_alleles[0]
            genotype = fields[9].split(':')[0]
            
            # Normalize chromosome name
            if chrom in chr_mapping:
                norm_chrom = chr_mapping[chrom]
            else:
                continue  # Skip if chromosome not in mapping
                
            if norm_chrom not in pgs_chromosomes:
                continue
                
            # Check if this variant is in our PGS model (try both REF/ALT orientations)
            variant_key1 = (norm_chrom, pos, ref, alt)
            variant_key2 = (norm_chrom, pos, alt, ref)
            
            weight = None
            effect_allele = None
            other_allele = None
            
            if variant_key1 in variant_weights:
                weight = variant_weights[variant_key1]
                effect_allele = ref
                other_allele = alt
            elif variant_key2 in variant_weights:
                weight = variant_weights[variant_key2]
                effect_allele = alt
                other_allele = ref
            
            if weight is not None:
                matched_variants += 1
                
                # Calculate contribution based on genotype
                if genotype == '0/0':  # Homozygous reference
                    if effect_allele == ref:
                        contribution = 2 * weight
                    else:
                        contribution = 0
                elif genotype == '0/1':  # Heterozygous
                    contribution = weight
                elif genotype == '1/1':  # Homozygous alternate
                    if effect_allele == alt:
                        contribution = 2 * weight
                    else:
                        contribution = 0
                else:
                    # Skip complex genotypes
                    continue
                
                total_score += contribution
            else:
                missing_variants += 1
    
    return total_score, matched_variants, missing_variants

def main():
    parser = argparse.ArgumentParser(description='Calculate Longevity Polygenic Score')
    parser.add_argument('--vcf', required=True, help='Input VCF file')
    parser.add_argument('--pgs', required=True, help='PGS Catalog scoring file')
    parser.add_argument('--output', help='Output file for PGS results')
    
    args = parser.parse_args()
    
    # Check if files exist
    if not os.path.exists(args.vcf):
        print(f"Error: VCF file {args.vcf} not found", file=sys.stderr)
        return 1
        
    if not os.path.exists(args.pgs):
        print(f"Error: PGS file {args.pgs} not found", file=sys.stderr)
        return 1
    
    # Parse PGS file
    print(f"Loading PGS model from {args.pgs}...")
    variant_weights = parse_pgs_file(args.pgs)
    
    # Calculate PGS
    print(f"Calculating PGS score from {args.vcf}...")
    total_score, matched_variants, missing_variants = parse_vcf_file(args.vcf, variant_weights)
    
    # Print results
    print("\n===== Longevity PGS Results =====")
    print(f"Total PGS Score: {total_score:.4f}")
    print(f"Matched variants: {matched_variants} out of {len(variant_weights)} in the model")
    print(f"Match rate: {matched_variants/len(variant_weights)*100:.2f}%")
    
    # Write to output file if specified
    if args.output:
        with open(args.output, 'w') as f:
            f.write("Metric\tValue\n")
            f.write(f"PGS_Score\t{total_score:.6f}\n")
            f.write(f"Matched_Variants\t{matched_variants}\n")
            f.write(f"Total_Model_Variants\t{len(variant_weights)}\n")
            f.write(f"Match_Rate\t{matched_variants/len(variant_weights)*100:.2f}%\n")
        print(f"Results written to {args.output}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
