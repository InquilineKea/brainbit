#!/usr/bin/env python3
"""
Extract high-impact collagen variants from VCF file
Focuses on COL1 and COL7 genes, but includes all collagen genes
"""

import os
import re
import csv
from collections import defaultdict

# Define file paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
VCF_FILE = os.path.join(BASE_DIR, "filtered_variants.ann.vcf")
OUTPUT_FILE = os.path.join(BASE_DIR, "collagen_variants.tsv")
HIGH_IMPACT_FILE = os.path.join(BASE_DIR, "collagen_high_impact_variants.tsv")

# Define collagen genes of interest
# COL1 has multiple genes (COL1A1, COL1A2)
PRIMARY_COLLAGEN_GENES = {
    "COL1A1", "COL1A2",  # Type I collagen
    "COL7A1"             # Type VII collagen
}

# All collagen genes to search for
COLLAGEN_PATTERN = r'\bCOL\d+A\d+\b'

def extract_collagen_variants():
    """Extract collagen variants from VCF file"""
    print(f"Searching for collagen variants in {VCF_FILE}...")
    
    # Initialize counters and storage
    total_variants = 0
    collagen_variants = 0
    primary_collagen_variants = 0
    high_impact_variants = 0
    
    # Dictionary to store variants by gene
    variants_by_gene = defaultdict(list)
    high_impact_by_gene = defaultdict(list)
    
    # Impact categories to consider as high impact
    high_impact_categories = {'HIGH', 'MODERATE'}
    
    # Process the VCF file
    with open(VCF_FILE, 'r') as vcf:
        for line in vcf:
            # Skip header lines
            if line.startswith('#'):
                continue
                
            total_variants += 1
            
            # Show progress every 100,000 variants
            if total_variants % 100000 == 0:
                print(f"Processed {total_variants} variants...")
            
            # Parse the line
            fields = line.strip().split('\t')
            if len(fields) < 8:
                continue
                
            # Check for ANN field in INFO column
            info = fields[7]
            if "ANN=" not in info:
                continue
                
            # Extract annotation
            ann_match = re.search(r'ANN=([^;]+)', info)
            if not ann_match:
                continue
                
            ann_field = ann_match.group(1)
            annotations = ann_field.split(',')
            
            # Check each annotation for collagen genes
            for annotation in annotations:
                ann_parts = annotation.split('|')
                if len(ann_parts) < 10:
                    continue
                    
                # Extract gene name and impact
                gene = ann_parts[3]
                impact = ann_parts[2]
                
                # Check if it's a collagen gene
                if re.search(COLLAGEN_PATTERN, gene):
                    collagen_variants += 1
                    
                    # Extract variant details
                    chrom = fields[0]
                    pos = fields[1]
                    ref = fields[3]
                    alt = fields[4]
                    
                    # Extract genotype
                    format_field = fields[8].split(':')
                    sample_data = fields[9].split(':')
                    
                    gt_idx = None
                    for i, field in enumerate(format_field):
                        if field == 'GT':
                            gt_idx = i
                            break
                    
                    genotype = sample_data[gt_idx] if gt_idx is not None and gt_idx < len(sample_data) else './.'
                    
                    # Extract effect and feature
                    effect = ann_parts[1]
                    feature = ann_parts[6]  # Transcript ID
                    
                    # Extract HGVS notation if available
                    hgvs_c = ann_parts[9]  # cDNA change
                    hgvs_p = ann_parts[10]  # Protein change
                    
                    # Store variant information
                    variant_info = {
                        'CHROM': chrom,
                        'POS': pos,
                        'REF': ref,
                        'ALT': alt,
                        'GENE': gene,
                        'IMPACT': impact,
                        'EFFECT': effect,
                        'FEATURE': feature,
                        'HGVS_C': hgvs_c,
                        'HGVS_P': hgvs_p,
                        'GENOTYPE': genotype
                    }
                    
                    variants_by_gene[gene].append(variant_info)
                    
                    # Check if it's a primary collagen gene
                    if gene in PRIMARY_COLLAGEN_GENES:
                        primary_collagen_variants += 1
                    
                    # Check if it's a high impact variant
                    if impact in high_impact_categories:
                        high_impact_variants += 1
                        high_impact_by_gene[gene].append(variant_info)
                    
                    # We found a collagen gene, no need to check other annotations for this variant
                    break
    
    # Write all collagen variants to file
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        
        # Write header
        writer.writerow(['CHROM', 'POS', 'REF', 'ALT', 'GENE', 'IMPACT', 'EFFECT', 
                         'FEATURE', 'HGVS_C', 'HGVS_P', 'GENOTYPE'])
        
        # Write variants sorted by gene
        for gene in sorted(variants_by_gene.keys()):
            for variant in variants_by_gene[gene]:
                writer.writerow([
                    variant['CHROM'],
                    variant['POS'],
                    variant['REF'],
                    variant['ALT'],
                    variant['GENE'],
                    variant['IMPACT'],
                    variant['EFFECT'],
                    variant['FEATURE'],
                    variant['HGVS_C'],
                    variant['HGVS_P'],
                    variant['GENOTYPE']
                ])
    
    # Write high impact variants to file
    with open(HIGH_IMPACT_FILE, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        
        # Write header
        writer.writerow(['CHROM', 'POS', 'REF', 'ALT', 'GENE', 'IMPACT', 'EFFECT', 
                         'FEATURE', 'HGVS_C', 'HGVS_P', 'GENOTYPE'])
        
        # Write high impact variants sorted by gene
        for gene in sorted(high_impact_by_gene.keys()):
            for variant in high_impact_by_gene[gene]:
                writer.writerow([
                    variant['CHROM'],
                    variant['POS'],
                    variant['REF'],
                    variant['ALT'],
                    variant['GENE'],
                    variant['IMPACT'],
                    variant['EFFECT'],
                    variant['FEATURE'],
                    variant['HGVS_C'],
                    variant['HGVS_P'],
                    variant['GENOTYPE']
                ])
    
    # Print summary
    print("\nCollagen Variant Analysis Complete")
    print(f"Total variants processed: {total_variants}")
    print(f"Total collagen variants found: {collagen_variants}")
    print(f"Primary collagen gene variants (COL1A1, COL1A2, COL7A1): {primary_collagen_variants}")
    print(f"High impact collagen variants: {high_impact_variants}")
    
    # Print gene-specific counts
    print("\nVariants by gene:")
    for gene, variants in sorted(variants_by_gene.items()):
        high_impact_count = len(high_impact_by_gene.get(gene, []))
        print(f"  {gene}: {len(variants)} variants ({high_impact_count} high impact)")
    
    print(f"\nResults saved to:")
    print(f"  All collagen variants: {OUTPUT_FILE}")
    print(f"  High impact variants: {HIGH_IMPACT_FILE}")
    
    # Create a detailed report for COL1 and COL7 genes
    create_primary_collagen_report(variants_by_gene, high_impact_by_gene)
    
    return variants_by_gene, high_impact_by_gene

def create_primary_collagen_report(variants_by_gene, high_impact_by_gene):
    """Create a detailed report for primary collagen genes (COL1 and COL7)"""
    report_file = os.path.join(BASE_DIR, "collagen_primary_genes_report.md")
    
    with open(report_file, 'w') as f:
        f.write("# Primary Collagen Genes Variant Report\n\n")
        f.write("This report focuses on variants in COL1 (COL1A1, COL1A2) and COL7 (COL7A1) genes.\n\n")
        
        f.write("## Overview\n\n")
        
        # Count variants in primary genes
        primary_counts = {gene: len(variants_by_gene.get(gene, [])) for gene in PRIMARY_COLLAGEN_GENES}
        primary_high_impact = {gene: len(high_impact_by_gene.get(gene, [])) for gene in PRIMARY_COLLAGEN_GENES}
        
        f.write("| Gene | Total Variants | High Impact Variants |\n")
        f.write("|------|---------------|----------------------|\n")
        
        for gene in sorted(PRIMARY_COLLAGEN_GENES):
            f.write(f"| {gene} | {primary_counts.get(gene, 0)} | {primary_high_impact.get(gene, 0)} |\n")
        
        # Write detailed sections for each primary gene
        for gene in sorted(PRIMARY_COLLAGEN_GENES):
            f.write(f"\n## {gene} Variants\n\n")
            
            variants = variants_by_gene.get(gene, [])
            if not variants:
                f.write(f"No variants found in {gene}.\n\n")
                continue
            
            # Write high impact variants first
            high_impact = high_impact_by_gene.get(gene, [])
            if high_impact:
                f.write("### High Impact Variants\n\n")
                f.write("| Position | Change | Effect | Impact | Protein Change | Genotype |\n")
                f.write("|----------|--------|--------|--------|----------------|----------|\n")
                
                for variant in high_impact:
                    position = f"{variant['CHROM']}:{variant['POS']}"
                    change = f"{variant['REF']}>{variant['ALT']}"
                    effect = variant['EFFECT']
                    impact = variant['IMPACT']
                    protein = variant['HGVS_P'] if variant['HGVS_P'] else '-'
                    genotype = variant['GENOTYPE']
                    
                    f.write(f"| {position} | {change} | {effect} | {impact} | {protein} | {genotype} |\n")
                
                f.write("\n")
            
            # Write all variants
            f.write("### All Variants\n\n")
            f.write("| Position | Change | Effect | Impact | Protein Change | Genotype |\n")
            f.write("|----------|--------|--------|--------|----------------|----------|\n")
            
            for variant in variants:
                position = f"{variant['CHROM']}:{variant['POS']}"
                change = f"{variant['REF']}>{variant['ALT']}"
                effect = variant['EFFECT']
                impact = variant['IMPACT']
                protein = variant['HGVS_P'] if variant['HGVS_P'] else '-'
                genotype = variant['GENOTYPE']
                
                f.write(f"| {position} | {change} | {effect} | {impact} | {protein} | {genotype} |\n")
        
        # Add information about collagen-related conditions
        f.write("\n## Collagen-Related Conditions\n\n")
        
        f.write("### COL1-Related Conditions\n\n")
        f.write("Variants in COL1A1 and COL1A2 genes are associated with:\n\n")
        f.write("- **Osteogenesis Imperfecta**: A group of genetic disorders that mainly affect the bones, causing them to break easily\n")
        f.write("- **Ehlers-Danlos Syndrome (Classical Type)**: Affects connective tissue, leading to skin hyperextensibility, joint hypermobility, and tissue fragility\n")
        f.write("- **Caffey Disease**: An infantile disorder characterized by bone changes, soft tissue swelling, and irritability\n\n")
        
        f.write("### COL7-Related Conditions\n\n")
        f.write("Variants in COL7A1 gene are associated with:\n\n")
        f.write("- **Dystrophic Epidermolysis Bullosa**: A genetic condition that causes the skin to be fragile and blister easily\n")
        f.write("- **Epidermolysis Bullosa Acquisita**: An autoimmune disorder causing skin fragility and blistering\n\n")
        
        f.write("## Disclaimer\n\n")
        f.write("This report is for research purposes only and should not be used for clinical decision-making. ")
        f.write("Consult with a healthcare professional for interpretation of genetic variants and their potential health implications.\n")
    
    print(f"Detailed report for primary collagen genes created: {report_file}")

if __name__ == "__main__":
    extract_collagen_variants()
