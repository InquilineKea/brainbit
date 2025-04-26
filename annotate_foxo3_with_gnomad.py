#!/usr/bin/env python3
"""
Script to annotate FOXO3 variants with gnomAD population frequencies
using the gnomAD browser API.
"""

import sys
import requests
import json
import time
import re

def get_gnomad_region_data(chrom, start, end):
    """Query the gnomAD API for all variants in a region."""
    # Remove 'chr' prefix if present for gnomAD API
    chrom = chrom.replace('chr', '')
    
    # The gnomAD API has a limit on region size, so we'll query in chunks
    chunk_size = 5000
    all_variants = []
    
    for chunk_start in range(start, end, chunk_size):
        chunk_end = min(chunk_start + chunk_size, end)
        
        # Construct the API URL for region query
        url = f"https://gnomad.broadinstitute.org/api/region/{chrom}-{chunk_start}-{chunk_end}?dataset=gnomad_r3"
        print(f"Querying chunk: {url}")
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if 'region_variants' in data:
                    all_variants.extend(data['region_variants'])
                    print(f"  Found {len(data['region_variants'])} variants in this chunk")
                time.sleep(1)  # Be nice to the API
            else:
                print(f"Error: API returned status code {response.status_code} for {url}", file=sys.stderr)
        except Exception as e:
            print(f"Error querying gnomAD API: {e}", file=sys.stderr)
    
    return all_variants

def normalize_variant(chrom, pos, ref, alt):
    """Normalize variant representation for comparison."""
    # Remove 'chr' prefix
    chrom = chrom.replace('chr', '')
    
    # Convert position to integer
    pos = int(pos)
    
    # Handle special cases for complex variants
    if len(ref) > 1 and len(alt) > 1:
        # For complex substitutions, we keep as is
        return chrom, pos, ref, alt
    
    # Left-align and trim common prefixes/suffixes
    # This is a simplified version of variant normalization
    if len(ref) > 1 or len(alt) > 1:
        # Trim common prefix
        while len(ref) > 0 and len(alt) > 0 and ref[0] == alt[0]:
            ref = ref[1:]
            alt = alt[1:]
            pos += 1
        
        # Trim common suffix
        while len(ref) > 0 and len(alt) > 0 and ref[-1] == alt[-1]:
            ref = ref[:-1]
            alt = alt[:-1]
        
        # Handle empty ref or alt
        if len(ref) == 0:
            ref = "-"
        if len(alt) == 0:
            alt = "-"
    
    return chrom, pos, ref, alt

def find_matching_variant(variants, chrom, pos, ref, alt):
    """Find a matching variant in the gnomAD data."""
    chrom = chrom.replace('chr', '')
    pos = int(pos)
    
    # Normalize the query variant
    norm_chrom, norm_pos, norm_ref, norm_alt = normalize_variant(chrom, pos, ref, alt)
    
    for variant in variants:
        gnomad_pos = variant.get('pos')
        gnomad_ref = variant.get('ref')
        gnomad_alt = variant.get('alt')
        
        # Normalize the gnomAD variant
        gnomad_norm_chrom, gnomad_norm_pos, gnomad_norm_ref, gnomad_norm_alt = normalize_variant(
            chrom, gnomad_pos, gnomad_ref, gnomad_alt
        )
        
        # Check if variants match after normalization
        if (norm_pos == gnomad_norm_pos and 
            ((norm_ref == gnomad_norm_ref and norm_alt == gnomad_norm_alt) or
             (norm_ref == gnomad_norm_alt and norm_alt == gnomad_norm_ref))):
            return variant
    
    return None

def extract_variant_info(vcf_line):
    """Extract chromosome, position, reference, and alternate alleles from a VCF line."""
    fields = vcf_line.strip().split('\t')
    chrom = fields[0]
    pos = fields[1]
    ref = fields[3]
    alt = fields[4]
    
    return chrom, pos, ref, alt

def format_gnomad_info(variant_data):
    """Format gnomAD data for inclusion in the VCF INFO field."""
    if not variant_data:
        return "gnomAD_AF=.;gnomAD_AF_popmax=.;gnomAD_popmax=."
    
    # Extract frequency data
    af = variant_data.get('genome', {}).get('af', '.')
    
    # Extract population-specific frequencies
    populations = variant_data.get('genome', {}).get('populations', [])
    pop_freqs = {}
    for pop in populations:
        pop_id = pop.get('id')
        pop_af = pop.get('af')
        if pop_id and pop_af is not None:
            pop_freqs[pop_id] = pop_af
    
    # Find population with maximum frequency
    popmax = '.'
    af_popmax = '.'
    if pop_freqs:
        popmax = max(pop_freqs.items(), key=lambda x: x[1] if x[1] is not None else 0)[0]
        af_popmax = pop_freqs[popmax]
    
    return f"gnomAD_AF={af};gnomAD_AF_popmax={af_popmax};gnomAD_popmax={popmax}"

def process_vcf_file(input_file, output_file):
    """Process the VCF file and annotate FOXO3 variants with gnomAD data."""
    # First, collect all FOXO3 variants
    foxo3_variants = []
    with open(input_file, 'r') as infile:
        for line in infile:
            if not line.startswith('#') and '|FOXO3|FOXO3|' in line:
                foxo3_variants.append(line.strip())
    
    if not foxo3_variants:
        print("No FOXO3 variants found in the input file.")
        return
    
    # Get the range of FOXO3 gene
    first_var = foxo3_variants[0]
    last_var = foxo3_variants[-1]
    first_chrom, first_pos, _, _ = extract_variant_info(first_var)
    last_chrom, last_pos, _, _ = extract_variant_info(last_var)
    
    # Add some padding around the gene (5kb on each side)
    start_pos = max(1, int(first_pos) - 5000)
    end_pos = int(last_pos) + 5000
    
    print(f"Querying gnomAD for variants in region {first_chrom}:{start_pos}-{end_pos}...")
    
    # Get all gnomAD variants in the FOXO3 region
    gnomad_variants = get_gnomad_region_data(first_chrom, start_pos, end_pos)
    
    if not gnomad_variants:
        print("Failed to retrieve gnomAD data for the FOXO3 region.")
        return
    
    print(f"Retrieved {len(gnomad_variants)} variants from gnomAD in the FOXO3 region.")
    
    # Process the VCF file and annotate variants
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            if line.startswith('#'):
                # Add new INFO fields to the header
                if line.startswith('##INFO') and '##INFO=<ID=gnomAD_AF' not in line:
                    outfile.write('##INFO=<ID=gnomAD_AF,Number=A,Type=Float,Description="Alternate allele frequency in gnomAD">\n')
                    outfile.write('##INFO=<ID=gnomAD_AF_popmax,Number=A,Type=Float,Description="Maximum alternate allele frequency across populations in gnomAD">\n')
                    outfile.write('##INFO=<ID=gnomAD_popmax,Number=A,Type=String,Description="Population with maximum alternate allele frequency in gnomAD">\n')
                outfile.write(line)
            else:
                # Check if this is a FOXO3 variant
                if '|FOXO3|FOXO3|' in line:
                    chrom, pos, ref, alt = extract_variant_info(line)
                    
                    # Find matching variant in gnomAD data
                    matching_variant = find_matching_variant(gnomad_variants, chrom, pos, ref, alt)
                    
                    if matching_variant:
                        gnomad_info = format_gnomad_info(matching_variant)
                        print(f"Found gnomAD match for {chrom}:{pos} {ref}>{alt}: {gnomad_info}")
                    else:
                        gnomad_info = "gnomAD_AF=.;gnomAD_AF_popmax=.;gnomAD_popmax=."
                        print(f"No gnomAD match found for {chrom}:{pos} {ref}>{alt}")
                    
                    # Add gnomAD info to the INFO field
                    fields = line.strip().split('\t')
                    info_field = fields[7]
                    fields[7] = f"{info_field};{gnomad_info}"
                    
                    # Write the modified line
                    outfile.write('\t'.join(fields) + '\n')
                else:
                    outfile.write(line)

if __name__ == "__main__":
    input_vcf = "filtered_variants.ann.vcf"
    output_vcf = "filtered_variants.ann.gnomad.vcf"
    
    print(f"Annotating FOXO3 variants with gnomAD frequencies...")
    process_vcf_file(input_vcf, output_vcf)
    print(f"Annotation complete. Results written to {output_vcf}")
