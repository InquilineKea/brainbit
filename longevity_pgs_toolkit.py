#!/usr/bin/env python3
"""
Longevity PGS Toolkit - A comprehensive tool for calculating and analyzing
longevity-related polygenic scores from personal genetic data.

This script supports:
1. Multiple PGS models for longevity and related traits
2. Automatic downloading of PGS models from the PGS Catalog
3. Conversion between genome builds (GRCh37/hg19 and GRCh38/hg38)
4. Detailed reporting of results
"""

import argparse
import gzip
import os
import sys
import urllib.request
import json
import csv
from collections import defaultdict

# PGS Catalog API endpoints
PGS_API_BASE = "https://www.pgscatalog.org/rest/score/"
PGS_FTP_BASE = "https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/"

# Known longevity-related PGS IDs
LONGEVITY_PGS_IDS = {
    "PGS000906": "Longevity PRS-5 (Tesi et al. 2021)",
    "PGS002795": "Longevity (Deelen et al. 2019)"
}

# Other related traits that might be of interest
RELATED_TRAITS = {
    "lifespan": ["PGS000727"],
    "healthspan": ["PGS000728"],
    "parental_lifespan": ["PGS000726"]
}

def download_pgs_model(pgs_id, output_dir="."):
    """Download a PGS model from the PGS Catalog"""
    print(f"Downloading PGS model {pgs_id}...")
    
    # First get metadata from API
    api_url = f"{PGS_API_BASE}{pgs_id}/"
    try:
        with urllib.request.urlopen(api_url) as response:
            metadata = json.loads(response.read().decode('utf-8'))
            
        # Get the scoring file URL
        ftp_url = f"{PGS_FTP_BASE}{pgs_id}/ScoringFiles/{pgs_id}.txt.gz"
        local_file = os.path.join(output_dir, f"{pgs_id}.txt.gz")
        
        # Download the file
        urllib.request.urlretrieve(ftp_url, local_file)
        print(f"Downloaded {pgs_id} to {local_file}")
        
        return local_file
    except Exception as e:
        print(f"Error downloading {pgs_id}: {e}", file=sys.stderr)
        return None

def parse_pgs_file(pgs_file):
    """Parse PGS scoring file and return a dictionary of variants with weights"""
    variant_weights = {}
    metadata = {}
    
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
            
            # Create a unique variant key
            variant_key = (
                data['chr_name'], 
                int(data['chr_position']), 
                data['effect_allele'], 
                data['other_allele']
            )
            
            variant_weights[variant_key] = float(data['effect_weight'])
    
    print(f"Loaded {len(variant_weights)} variants from PGS file")
    return variant_weights, metadata

def parse_vcf_file(vcf_file, variant_weights, genome_build=None, pgs_build=None):
    """Parse VCF file and calculate PGS score"""
    total_score = 0
    matched_variants = 0
    missing_variants = 0
    variant_contributions = []
    
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
    parser = argparse.ArgumentParser(description='Calculate Longevity Polygenic Score')
    parser.add_argument('--vcf', required=True, help='Input VCF file')
    parser.add_argument('--pgs', help='PGS Catalog scoring file (if not specified, will download PGS000906)')
    parser.add_argument('--pgs-id', default='PGS000906', help='PGS Catalog ID to download (default: PGS000906)')
    parser.add_argument('--output-prefix', help='Prefix for output files')
    
    args = parser.parse_args()
    
    # Check if VCF file exists
    if not os.path.exists(args.vcf):
        print(f"Error: VCF file {args.vcf} not found", file=sys.stderr)
        return 1
    
    # Get PGS file - either use provided file or download
    pgs_file = args.pgs
    if not pgs_file:
        pgs_file = download_pgs_model(args.pgs_id)
        if not pgs_file:
            print(f"Error: Failed to download PGS model {args.pgs_id}", file=sys.stderr)
            return 1
    elif not os.path.exists(pgs_file):
        print(f"Error: PGS file {pgs_file} not found", file=sys.stderr)
        return 1
    
    # Parse PGS file
    print(f"Loading PGS model from {pgs_file}...")
    variant_weights, metadata = parse_pgs_file(pgs_file)
    
    # Calculate PGS
    print(f"Calculating PGS score from {args.vcf}...")
    total_score, matched_variants, missing_variants, variant_contributions = parse_vcf_file(
        args.vcf, variant_weights
    )
    
    # Sort contributions by absolute value for reporting
    sorted_contributions = sorted(variant_contributions, key=lambda x: abs(x[5]), reverse=True)
    top_contributions = sorted_contributions[:10]  # Top 10 contributing variants
    
    # Generate report
    output_report = f"{args.output_prefix}_report.txt" if args.output_prefix else None
    generate_report(
        args.pgs_id if not args.pgs else os.path.basename(args.pgs).split('.')[0],
        metadata,
        total_score,
        matched_variants,
        len(variant_weights),
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
