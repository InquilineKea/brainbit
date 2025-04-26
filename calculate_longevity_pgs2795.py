#!/usr/bin/env python3
"""
Calculate Longevity PGS using the PGS002795 model (4 key variants)
"""

import argparse
import gzip
import os
import sys
import csv

def parse_pgs002795(pgs_file):
    """Parse the PGS002795 model file"""
    variants = []
    metadata = {}
    
    # Determine if file is gzipped
    open_func = gzip.open if pgs_file.endswith('.gz') else open
    mode = 'rt' if pgs_file.endswith('.gz') else 'r'
    
    with open_func(pgs_file, mode) as f:
        header = None
        for line in f:
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
            
            # Extract variant information
            rsid = data['rsID']
            effect_allele = data['effect_allele']
            other_allele = data['other_allele']
            weight = float(data['effect_weight'])
            locus = data.get('locus_name', '')
            
            variants.append({
                'rsid': rsid,
                'effect_allele': effect_allele,
                'other_allele': other_allele,
                'weight': weight,
                'locus': locus
            })
    
    print(f"Loaded {len(variants)} variants from PGS file")
    return variants, metadata

def find_variants_in_vcf(vcf_file, variants):
    """Find the PGS variants in the VCF file"""
    found_variants = []
    rsids_to_find = {v['rsid']: v for v in variants}
    
    # Process VCF file
    with open(vcf_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            
            fields = line.strip().split('\t')
            if len(fields) < 10:  # Need at least 10 columns for a valid VCF
                continue
                
            rsid = fields[2]
            
            # Check if this is one of our target variants
            if rsid in rsids_to_find:
                chrom = fields[0]
                pos = fields[1]
                ref = fields[3]
                alt = fields[4]
                
                # Get genotype
                format_fields = fields[8].split(':')
                sample_fields = fields[9].split(':')
                
                if 'GT' not in format_fields:
                    continue
                    
                gt_index = format_fields.index('GT')
                genotype = sample_fields[gt_index]
                
                # Store the found variant
                variant_info = rsids_to_find[rsid].copy()
                variant_info.update({
                    'chrom': chrom,
                    'pos': pos,
                    'ref': ref,
                    'alt': alt,
                    'genotype': genotype
                })
                
                found_variants.append(variant_info)
                print(f"Found variant {rsid} at {chrom}:{pos} {ref}>{alt} with genotype {genotype}")
    
    return found_variants

def calculate_pgs_score(found_variants):
    """Calculate the PGS score from the found variants"""
    total_score = 0
    variant_contributions = []
    
    for variant in found_variants:
        rsid = variant['rsid']
        genotype = variant['genotype']
        weight = variant['weight']
        effect_allele = variant['effect_allele']
        other_allele = variant['other_allele']
        ref = variant['ref']
        alt = variant['alt']
        
        # Determine contribution based on genotype and allele matching
        contribution = 0
        
        # Check if reference allele matches effect allele
        ref_is_effect = ref == effect_allele
        alt_is_effect = alt == effect_allele
        
        if genotype == '0/0':  # Homozygous reference
            if ref_is_effect:
                contribution = 2 * weight  # Two effect alleles
            else:
                contribution = 0  # No effect alleles
        elif genotype in ['0/1', '1/0']:  # Heterozygous
            contribution = weight  # One effect allele
        elif genotype == '1/1':  # Homozygous alternate
            if alt_is_effect:
                contribution = 2 * weight  # Two effect alleles
            else:
                contribution = 0  # No effect alleles
        
        total_score += contribution
        variant_contributions.append({
            'rsid': rsid,
            'chrom': variant['chrom'],
            'pos': variant['pos'],
            'ref': ref,
            'alt': alt,
            'genotype': genotype,
            'weight': weight,
            'contribution': contribution,
            'locus': variant['locus']
        })
    
    return total_score, variant_contributions

def generate_report(pgs_id, metadata, total_score, found_variants, variant_contributions, output_file=None):
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
    report.append("")
    
    # Score Information
    report.append("SCORE SUMMARY:")
    report.append(f"  Raw PGS Score: {total_score:.6f}")
    report.append(f"  Found Variants: {len(found_variants)} out of {metadata.get('variants_number', '?')}")
    report.append("")
    
    # Variant Details
    report.append("VARIANT DETAILS:")
    for vc in variant_contributions:
        report.append(f"  {vc['rsid']} ({vc['locus']}) - {vc['chrom']}:{vc['pos']} {vc['ref']}>{vc['alt']}")
        report.append(f"    Genotype: {vc['genotype']}, Weight: {vc['weight']:.4f}, Contribution: {vc['contribution']:.4f}")
    report.append("")
    
    # Interpretation
    report.append("INTERPRETATION:")
    report.append("  This score represents your genetic predisposition for longevity based on key genetic variants.")
    report.append("  Higher scores generally indicate a greater genetic predisposition for longevity.")
    report.append("  The PGS002795 model focuses specifically on variants in the APOE and NECTIN2 genes,")
    report.append("  which have been strongly associated with longevity in multiple studies.")
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
    parser = argparse.ArgumentParser(description='Calculate Longevity PGS using PGS002795 model')
    parser.add_argument('--vcf', required=True, help='Input VCF file')
    parser.add_argument('--pgs', required=True, help='PGS002795 scoring file')
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
    variants, metadata = parse_pgs002795(args.pgs)
    
    # Find variants in VCF
    print(f"Searching for variants in {args.vcf}...")
    found_variants = find_variants_in_vcf(args.vcf, variants)
    
    # Calculate PGS score
    print(f"Calculating PGS score...")
    total_score, variant_contributions = calculate_pgs_score(found_variants)
    
    # Generate report
    generate_report(
        "PGS002795",
        metadata,
        total_score,
        found_variants,
        variant_contributions,
        args.output
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
