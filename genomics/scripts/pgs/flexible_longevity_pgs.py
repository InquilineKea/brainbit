#!/usr/bin/env python3
"""
Flexible Longevity PGS Calculator - Designed to handle various VCF formats and improve variant matching
"""

import argparse
import gzip
import os
import sys
import csv
from collections import defaultdict

def parse_pgs_file(pgs_file):
    """Parse PGS scoring file and return a dictionary of variants with weights"""
    variant_weights = {}
    metadata = {}
    rsid_to_variant = {}
    
    # Determine if file is gzipped
    open_func = gzip.open if pgs_file.endswith('.gz') else open
    mode = 'rt' if pgs_file.endswith('.gz') else 'r'
    
    with open_func(pgs_file, mode) as f:
        header = None
        for line in f:
            # Extract metadata from header
            if line.startswith('#'):
                if '=' in line:
                    key, value = line.strip('#').strip().split('=', 1)
                    metadata[key] = value
                continue
            
            if header is None:
                header = line.strip().split('\t')
                continue
            
            fields = line.strip().split('\t')
            data = dict(zip(header, fields))
            
            # Store by position
            chrom = data['chr_name']
            pos = int(data['chr_position'])
            ref = data['effect_allele']
            alt = data['other_allele']
            weight = float(data['effect_weight'])
            rsid = data.get('rsID', '')
            
            # Store by chromosome and position
            # Try both orientations (ref/alt and alt/ref)
            variant_weights[(chrom, pos, ref, alt)] = (weight, 'direct')
            variant_weights[(chrom, pos, alt, ref)] = (-weight, 'flipped')  # Flip the weight if alleles are flipped
            
            # Also store by rsID if available
            if rsid and rsid != '.':
                rsid_to_variant[rsid] = (chrom, pos, ref, alt, weight)
    
    print(f"Loaded {len(rsid_to_variant)} variants from PGS file")
    return variant_weights, rsid_to_variant, metadata

def parse_vcf_file(vcf_file, variant_weights, rsid_to_variant):
    """Parse VCF file and calculate PGS score with flexible matching"""
    total_score = 0
    matched_variants = 0
    missing_variants = 0
    variant_contributions = []
    
    # Convert chromosome names to ensure matching
    chr_mapping = {}
    # Map both with and without 'chr' prefix
    for c in list(range(1, 23)) + ['X', 'Y']:
        chr_mapping[f"chr{c}"] = str(c)
        chr_mapping[str(c)] = str(c)
    
    # Process VCF file
    with open(vcf_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            
            fields = line.strip().split('\t')
            if len(fields) < 10:  # Need at least 10 columns for a valid VCF
                continue
                
            chrom = fields[0]
            pos = int(fields[1])
            rsid = fields[2]
            ref = fields[3]
            alt_alleles = fields[4].split(',')
            
            # Get genotype
            format_fields = fields[8].split(':')
            sample_fields = fields[9].split(':')
            
            if 'GT' not in format_fields:
                continue
                
            gt_index = format_fields.index('GT')
            genotype = sample_fields[gt_index]
            
            # Skip complex genotypes
            if genotype not in ['0/0', '0/1', '1/0', '1/1']:
                continue
            
            # Normalize chromosome name
            if chrom in chr_mapping:
                norm_chrom = chr_mapping[chrom]
            else:
                # Try to remove 'chr' prefix if present
                if chrom.startswith('chr'):
                    norm_chrom = chrom[3:]
                else:
                    continue  # Skip if chromosome not recognized
            
            # Try to match by position and alleles
            matched = False
            contribution = 0
            
            # For each alt allele
            for i, alt in enumerate(alt_alleles):
                # Check if this variant is in our PGS model
                variant_key = (norm_chrom, pos, ref, alt)
                
                if variant_key in variant_weights:
                    weight, orientation = variant_weights[variant_key]
                    matched = True
                    
                    # Calculate contribution based on genotype
                    if genotype == '0/0':  # Homozygous reference
                        if orientation == 'direct':
                            contribution = 0  # No effect alleles
                        else:
                            contribution = 2 * weight  # Two effect alleles (flipped orientation)
                    elif genotype in ['0/1', '1/0']:  # Heterozygous
                        contribution = weight
                    elif genotype == '1/1':  # Homozygous alternate
                        if orientation == 'direct':
                            contribution = 2 * weight  # Two effect alleles
                        else:
                            contribution = 0  # No effect alleles (flipped orientation)
                
                # If not matched by position/alleles, try by rsID
                if not matched and rsid and rsid != '.' and rsid in rsid_to_variant:
                    pgs_chrom, pgs_pos, pgs_ref, pgs_alt, pgs_weight = rsid_to_variant[rsid]
                    
                    # Check if position is close (allow some flexibility)
                    if abs(pos - pgs_pos) <= 5:
                        matched = True
                        
                        # Determine if alleles match or are flipped
                        if (ref == pgs_ref and alt == pgs_alt):
                            weight = pgs_weight
                            orientation = 'direct'
                        elif (ref == pgs_alt and alt == pgs_ref):
                            weight = -pgs_weight
                            orientation = 'flipped'
                        else:
                            # Alleles don't match, but positions are close
                            # This is a partial match
                            weight = pgs_weight
                            orientation = 'partial'
                        
                        # Calculate contribution based on genotype
                        if genotype == '0/0':  # Homozygous reference
                            if orientation == 'direct':
                                contribution = 0
                            else:
                                contribution = 2 * weight
                        elif genotype in ['0/1', '1/0']:  # Heterozygous
                            contribution = weight
                        elif genotype == '1/1':  # Homozygous alternate
                            if orientation == 'direct':
                                contribution = 2 * weight
                            else:
                                contribution = 0
            
            if matched:
                matched_variants += 1
                total_score += contribution
                variant_contributions.append((f"{chrom}:{pos}", ref, alt, genotype, weight, contribution))
            else:
                missing_variants += 1
    
    return total_score, matched_variants, missing_variants, variant_contributions

def generate_report(pgs_id, metadata, total_score, matched_variants, total_variants, 
                   top_contributions, output_file=None):
    """Generate a detailed report of the PGS results"""
    
    report = []
    report.append("=" * 50)
    report.append(f"LONGEVITY POLYGENIC SCORE REPORT - {pgs_id}")
    report.append("=" * 50)
    report.append("")
    
    # PGS Information
    report.append("PGS MODEL INFORMATION:")
    report.append(f"  PGS ID: {pgs_id}")
    if 'pgs_name' in metadata:
        report.append(f"  Name: {metadata['pgs_name']}")
    if 'trait_reported' in metadata:
        report.append(f"  Trait: {metadata['trait_reported']}")
    if 'genome_build' in metadata:
        report.append(f"  Genome Build: {metadata['genome_build']}")
    report.append("")
    
    # Score Information
    report.append("SCORE SUMMARY:")
    report.append(f"  Raw PGS Score: {total_score:.6f}")
    report.append(f"  Matched Variants: {matched_variants} out of {total_variants} ({matched_variants/total_variants*100:.2f}%)")
    report.append("")
    
    # Top Contributing Variants
    report.append("TOP CONTRIBUTING VARIANTS:")
    for variant, ref, alt, genotype, weight, contribution in top_contributions:
        report.append(f"  {variant} {ref}>{alt} [Genotype: {genotype}] - Weight: {weight:.4f}, Contribution: {contribution:.4f}")
    report.append("")
    
    # Interpretation
    report.append("INTERPRETATION:")
    report.append("  This score represents your genetic predisposition for longevity based on common genetic variants.")
    report.append("  Higher scores generally indicate a greater genetic predisposition for longevity.")
    report.append("  Note that longevity is influenced by many factors beyond genetics, including lifestyle and environment.")
    report.append("")
    
    # Disclaimer
    report.append("DISCLAIMER:")
    report.append("  This analysis is for research and educational purposes only.")
    report.append("  It should not be used for medical decisions without consultation with healthcare professionals.")
    report.append("=" * 50)
    
    # Print to console
    print("\n".join(report))
    
    # Write to file if specified
    if output_file:
        with open(output_file, 'w') as f:
            f.write("\n".join(report))
        print(f"Report written to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Calculate Longevity Polygenic Score with flexible matching')
    parser.add_argument('--vcf', required=True, help='Input VCF file')
    parser.add_argument('--pgs', required=True, help='PGS Catalog scoring file')
    parser.add_argument('--output-prefix', help='Prefix for output files')
    
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
    variant_weights, rsid_to_variant, metadata = parse_pgs_file(args.pgs)
    
    # Calculate PGS
    print(f"Calculating PGS score from {args.vcf} with flexible matching...")
    total_score, matched_variants, missing_variants, variant_contributions = parse_vcf_file(
        args.vcf, variant_weights, rsid_to_variant
    )
    
    # Sort contributions by absolute value for reporting
    sorted_contributions = sorted(variant_contributions, key=lambda x: abs(x[5]), reverse=True)
    top_contributions = sorted_contributions[:10]  # Top 10 contributing variants
    
    # Generate report
    output_report = f"{args.output_prefix}_report.txt" if args.output_prefix else None
    generate_report(
        os.path.basename(args.pgs).split('.')[0],
        metadata,
        total_score,
        matched_variants,
        len(rsid_to_variant),
        top_contributions,
        output_report
    )
    
    # Write detailed results to CSV if output prefix is specified
    if args.output_prefix:
        csv_file = f"{args.output_prefix}_variant_details.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Variant', 'Ref', 'Alt', 'Genotype', 'Weight', 'Contribution'])
            for contrib in sorted_contributions:
                writer.writerow(contrib)
        print(f"Detailed variant contributions written to {csv_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
