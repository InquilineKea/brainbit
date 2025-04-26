#!/usr/bin/env python3
"""
Comprehensive Structural Variant Analysis
This script analyzes all types of structural variants (SVs) in a genome,
including deletions, insertions, duplications, inversions, and translocations.
"""

import os
import re
import sys
from collections import Counter, defaultdict

# File paths
SV_DIR = "/Users/simfish/Downloads/Genome"
OUTPUT_DIR = os.path.join(SV_DIR, "sv_analysis")
REPORT_FILE = os.path.join(OUTPUT_DIR, "comprehensive_sv_report.md")

# Input files
SV_FILES = {
    "deletions": os.path.join(SV_DIR, "sv_deletions.txt"),
    "insertions": os.path.join(SV_DIR, "sv_insertions.txt"),
    "duplications": os.path.join(SV_DIR, "sv_duplications.txt"),
    "inversions": os.path.join(SV_DIR, "sv_inversions.txt"),
    "translocations": os.path.join(SV_DIR, "sv_translocations.txt"),
    "large": os.path.join(SV_DIR, "sv_large.txt")
}

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_sv_data():
    """
    Load structural variant data from all files
    """
    sv_data = {}
    
    for sv_type, file_path in SV_FILES.items():
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found. Skipping {sv_type}.")
            continue
        
        variants = []
        
        with open(file_path, 'r') as f:
            # Skip header lines
            for line in f:
                if line.startswith('#'):
                    continue
                if not line.strip():
                    continue
                
                fields = line.strip().split('\t')
                if len(fields) < 3:  # Minimum fields needed
                    continue
                
                # Parse fields based on SV type
                variant = {'chromosome': fields[0]}
                
                if sv_type in ["deletions", "insertions", "duplications", "inversions"]:
                    if len(fields) >= 2:
                        variant['position'] = int(fields[1]) if fields[1].isdigit() else fields[1]
                    if len(fields) >= 3:
                        variant['length'] = int(fields[2]) if fields[2].isdigit() else fields[2]
                    if len(fields) >= 4:
                        variant['sequence'] = fields[3]
                    if len(fields) >= 5:
                        variant['quality'] = fields[4]
                    if len(fields) >= 6:
                        variant['genotype'] = fields[5]
                    if len(fields) >= 7:
                        variant['filter'] = fields[6]
                
                elif sv_type == "translocations":
                    if len(fields) >= 2:
                        variant['position'] = int(fields[1]) if fields[1].isdigit() else fields[1]
                    if len(fields) >= 3:
                        variant['target_chromosome'] = fields[2]
                    if len(fields) >= 4:
                        variant['target_position'] = int(fields[3]) if fields[3].isdigit() else fields[3]
                    if len(fields) >= 5:
                        variant['quality'] = fields[4]
                    if len(fields) >= 6:
                        variant['genotype'] = fields[5]
                    if len(fields) >= 7:
                        variant['filter'] = fields[6]
                
                variants.append(variant)
        
        sv_data[sv_type] = variants
        print(f"Loaded {len(variants)} {sv_type}")
    
    return sv_data

def analyze_size_distribution(sv_data):
    """
    Analyze size distribution of structural variants
    """
    size_distributions = {}
    
    for sv_type, variants in sv_data.items():
        if sv_type == "translocations":
            continue  # Translocations don't have a simple size
        
        sizes = []
        for variant in variants:
            if 'length' in variant and variant['length'] != "unknown":
                try:
                    size = int(variant['length'])
                    sizes.append(size)
                except (ValueError, TypeError):
                    pass
        
        if sizes:
            size_distributions[sv_type] = {
                'min': min(sizes),
                'max': max(sizes),
                'avg': sum(sizes) / len(sizes),
                'median': sorted(sizes)[len(sizes) // 2],
                'count': len(sizes),
                'size_ranges': {
                    '<100bp': sum(1 for s in sizes if s < 100),
                    '100-500bp': sum(1 for s in sizes if 100 <= s < 500),
                    '500-1kb': sum(1 for s in sizes if 500 <= s < 1000),
                    '1-5kb': sum(1 for s in sizes if 1000 <= s < 5000),
                    '5-10kb': sum(1 for s in sizes if 5000 <= s < 10000),
                    '>10kb': sum(1 for s in sizes if s >= 10000)
                }
            }
    
    return size_distributions

def analyze_chromosome_distribution(sv_data):
    """
    Analyze distribution of variants across chromosomes
    """
    chrom_distributions = {}
    
    for sv_type, variants in sv_data.items():
        chrom_counts = defaultdict(int)
        
        for variant in variants:
            if 'chromosome' in variant:
                chrom_counts[variant['chromosome']] += 1
        
        chrom_distributions[sv_type] = dict(chrom_counts)
    
    return chrom_distributions

def analyze_genotype_distribution(sv_data):
    """
    Analyze genotype distribution of variants
    """
    genotype_distributions = {}
    
    for sv_type, variants in sv_data.items():
        genotype_counts = defaultdict(int)
        
        for variant in variants:
            if 'genotype' in variant:
                genotype_counts[variant['genotype']] += 1
        
        genotype_distributions[sv_type] = dict(genotype_counts)
    
    return genotype_distributions

def analyze_filter_status(sv_data):
    """
    Analyze filter status of variants
    """
    filter_distributions = {}
    
    for sv_type, variants in sv_data.items():
        filter_counts = defaultdict(int)
        
        for variant in variants:
            if 'filter' in variant:
                filter_counts[variant['filter']] += 1
        
        filter_distributions[sv_type] = dict(filter_counts)
    
    return filter_distributions

def generate_report(sv_data, size_distributions, chrom_distributions, genotype_distributions, filter_distributions):
    """
    Generate a comprehensive report of the structural variant analysis
    """
    with open(REPORT_FILE, 'w') as f:
        f.write("# Comprehensive Structural Variant Analysis Report\n\n")
        f.write(f"Analysis Date: {os.popen('date').read().strip()}\n\n")
        
        # Overview section
        f.write("## Overview\n\n")
        f.write("| Variant Type | Count |\n")
        f.write("|--------------|-------|\n")
        total_variants = 0
        for sv_type, variants in sv_data.items():
            count = len(variants)
            total_variants += count
            f.write(f"| {sv_type.capitalize()} | {count} |\n")
        f.write(f"| **Total** | **{total_variants}** |\n\n")
        
        # Size distribution section
        f.write("## Size Distribution\n\n")
        for sv_type, stats in size_distributions.items():
            f.write(f"### {sv_type.capitalize()}\n\n")
            f.write(f"- **Count**: {stats['count']}\n")
            f.write(f"- **Minimum Size**: {stats['min']} bp\n")
            f.write(f"- **Maximum Size**: {stats['max']} bp\n")
            f.write(f"- **Average Size**: {stats['avg']:.2f} bp\n")
            f.write(f"- **Median Size**: {stats['median']} bp\n\n")
            
            f.write("| Size Range | Count | Percentage |\n")
            f.write("|------------|-------|------------|\n")
            for size_range, count in stats['size_ranges'].items():
                percentage = (count / stats['count']) * 100
                f.write(f"| {size_range} | {count} | {percentage:.2f}% |\n")
            f.write("\n")
        
        # Chromosome distribution section
        f.write("## Chromosome Distribution\n\n")
        
        # Get all chromosomes across all variant types
        all_chroms = set()
        for chrom_dist in chrom_distributions.values():
            all_chroms.update(chrom_dist.keys())
        
        # Sort chromosomes naturally
        def chrom_key(chrom):
            if chrom.startswith('chr'):
                chrom = chrom[3:]
            if chrom.isdigit():
                return int(chrom)
            return float('inf')  # Put non-numeric at the end
        
        sorted_chroms = sorted(all_chroms, key=chrom_key)
        
        # Create table header
        f.write("| Chromosome | " + " | ".join(sv_type.capitalize() for sv_type in sv_data.keys()) + " | Total |\n")
        f.write("|------------| " + " | ".join("-" * len(sv_type) for sv_type in sv_data.keys()) + " | ----- |\n")
        
        # Fill in the table
        for chrom in sorted_chroms:
            f.write(f"| {chrom} | ")
            chrom_total = 0
            for sv_type in sv_data.keys():
                count = chrom_distributions[sv_type].get(chrom, 0)
                chrom_total += count
                f.write(f"{count} | ")
            f.write(f"{chrom_total} |\n")
        f.write("\n")
        
        # Genotype distribution section
        f.write("## Genotype Distribution\n\n")
        
        # Get all genotypes across all variant types
        all_genotypes = set()
        for gt_dist in genotype_distributions.values():
            all_genotypes.update(gt_dist.keys())
        
        # Create table header
        f.write("| Genotype | " + " | ".join(sv_type.capitalize() for sv_type in sv_data.keys()) + " |\n")
        f.write("|----------| " + " | ".join("-" * len(sv_type) for sv_type in sv_data.keys()) + " |\n")
        
        # Fill in the table
        for gt in sorted(all_genotypes):
            f.write(f"| {gt} | ")
            for sv_type in sv_data.keys():
                count = genotype_distributions[sv_type].get(gt, 0)
                f.write(f"{count} | ")
            f.write("\n")
        f.write("\n")
        
        # Filter status section
        f.write("## Filter Status\n\n")
        
        # Get all filter statuses across all variant types
        all_filters = set()
        for filter_dist in filter_distributions.values():
            all_filters.update(filter_dist.keys())
        
        # Create table header
        f.write("| Filter | " + " | ".join(sv_type.capitalize() for sv_type in sv_data.keys()) + " |\n")
        f.write("|--------| " + " | ".join("-" * len(sv_type) for sv_type in sv_data.keys()) + " |\n")
        
        # Fill in the table
        for filter_status in sorted(all_filters):
            f.write(f"| {filter_status} | ")
            for sv_type in sv_data.keys():
                count = filter_distributions[sv_type].get(filter_status, 0)
                f.write(f"{count} | ")
            f.write("\n")
        f.write("\n")
        
        # Potential functional impact section
        f.write("## Potential Functional Impact\n\n")
        f.write("The structural variants identified in this analysis may have various functional impacts on the genome:\n\n")
        
        f.write("### Deletions\n\n")
        f.write("- Loss of genetic material, potentially including coding sequences\n")
        f.write("- Disruption of regulatory elements\n")
        f.write("- Creation of fusion genes if breakpoints occur within genes\n")
        f.write("- Potential impact on gene dosage\n\n")
        
        f.write("### Insertions\n\n")
        f.write("- Introduction of new genetic material\n")
        f.write("- Disruption of coding sequences or regulatory elements\n")
        f.write("- Potential introduction of repetitive elements\n")
        f.write("- Creation of novel splice sites\n\n")
        
        f.write("### Duplications\n\n")
        f.write("- Increased copy number of genetic material\n")
        f.write("- Potential gene dosage effects\n")
        f.write("- Creation of chimeric genes\n")
        f.write("- Substrate for future genomic rearrangements\n\n")
        
        f.write("### Inversions\n\n")
        f.write("- Reorientation of genetic material\n")
        f.write("- Potential disruption of genes at breakpoints\n")
        f.write("- Altered gene regulation\n")
        f.write("- Suppression of recombination in heterozygotes\n\n")
        
        f.write("### Translocations\n\n")
        f.write("- Exchange of genetic material between chromosomes\n")
        f.write("- Creation of fusion genes\n")
        f.write("- Disruption of gene regulation\n")
        f.write("- Potential impact on chromosome pairing during meiosis\n\n")
        
        # Next steps section
        f.write("## Next Steps\n\n")
        f.write("1. **Gene Annotation**: Integrate these structural variants with gene coordinates to identify variants affecting coding regions\n")
        f.write("2. **Functional Analysis**: Perform pathway analysis on genes affected by structural variants\n")
        f.write("3. **Population Comparison**: Compare these variants with population databases to identify rare or novel variants\n")
        f.write("4. **Phenotype Association**: Investigate potential associations with phenotypic traits or disease risk\n")
        f.write("5. **Validation**: Consider experimental validation of high-impact variants\n")
    
    print(f"Comprehensive report generated: {REPORT_FILE}")

def main():
    print("Starting comprehensive structural variant analysis...")
    
    # Load structural variant data
    sv_data = load_sv_data()
    
    if not sv_data:
        print("No structural variant data found. Exiting.")
        return
    
    # Analyze size distribution
    print("Analyzing size distribution...")
    size_distributions = analyze_size_distribution(sv_data)
    
    # Analyze chromosome distribution
    print("Analyzing chromosome distribution...")
    chrom_distributions = analyze_chromosome_distribution(sv_data)
    
    # Analyze genotype distribution
    print("Analyzing genotype distribution...")
    genotype_distributions = analyze_genotype_distribution(sv_data)
    
    # Analyze filter status
    print("Analyzing filter status...")
    filter_distributions = analyze_filter_status(sv_data)
    
    # Generate comprehensive report
    print("Generating comprehensive report...")
    generate_report(sv_data, size_distributions, chrom_distributions, genotype_distributions, filter_distributions)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
