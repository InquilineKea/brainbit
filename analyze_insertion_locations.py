#!/usr/bin/env python3
"""
Analyze Insertion Locations Relative to Genes and Regulatory Regions
This script checks if structural variant insertions are near genes or regulatory elements.
"""

import os
import sys
import csv
from collections import defaultdict

# File paths
INSERTION_FILE = "/Users/simfish/Downloads/Genome/sv_analysis/insertion_sequences.tsv"
REF_GENE_FILE = "/Users/simfish/Downloads/Genome/reference_data/refGene.txt"
CPG_ISLAND_FILE = "/Users/simfish/Downloads/Genome/reference_data/cpgIslandExt.txt"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
LOCATION_REPORT = os.path.join(OUTPUT_DIR, "insertion_locations.md")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define proximity thresholds (in base pairs)
GENE_PROXIMITY = 5000  # 5kb from a gene
PROMOTER_PROXIMITY = 2000  # 2kb from a transcription start site
REGULATORY_PROXIMITY = 1000  # 1kb from a CpG island

def load_insertion_data():
    """
    Load insertion data from the TSV file
    """
    if not os.path.exists(INSERTION_FILE):
        print(f"Error: {INSERTION_FILE} not found.")
        sys.exit(1)
        
    insertions = []
    
    with open(INSERTION_FILE, 'r') as f:
        # Skip header line
        next(f)
        
        for line in f:
            if not line.strip():
                continue
                
            fields = line.strip().split('\t')
            if len(fields) < 7:
                continue
                
            chrom = fields[0]
            pos = int(fields[1])
            length = fields[2]
            sequence = fields[3]
            quality = fields[4]
            genotype = fields[5]
            filter_status = fields[6]
            
            insertions.append({
                'chromosome': chrom,
                'position': pos,
                'length': length,
                'sequence': sequence,
                'quality': quality,
                'genotype': genotype,
                'filter': filter_status
            })
    
    print(f"Loaded {len(insertions)} insertions")
    return insertions

def load_gene_data():
    """
    Load gene data from refGene.txt
    """
    if not os.path.exists(REF_GENE_FILE):
        print(f"Error: {REF_GENE_FILE} not found.")
        sys.exit(1)
        
    genes = []
    
    with open(REF_GENE_FILE, 'r') as f:
        for line in f:
            fields = line.strip().split('\t')
            if len(fields) < 16:
                continue
                
            bin_val = fields[0]
            name = fields[1]
            chrom = fields[2]
            strand = fields[3]
            tx_start = int(fields[4])
            tx_end = int(fields[5])
            cds_start = int(fields[6])
            cds_end = int(fields[7])
            exon_count = int(fields[8])
            exon_starts = [int(x) for x in fields[9].strip(',').split(',') if x]
            exon_ends = [int(x) for x in fields[10].strip(',').split(',') if x]
            gene_name = fields[12]
            
            genes.append({
                'name': name,
                'gene_name': gene_name,
                'chromosome': chrom,
                'strand': strand,
                'tx_start': tx_start,
                'tx_end': tx_end,
                'cds_start': cds_start,
                'cds_end': cds_end,
                'exon_count': exon_count,
                'exon_starts': exon_starts,
                'exon_ends': exon_ends
            })
    
    print(f"Loaded {len(genes)} genes")
    return genes

def load_cpg_islands():
    """
    Load CpG island data from cpgIslandExt.txt
    """
    if not os.path.exists(CPG_ISLAND_FILE):
        print(f"Error: {CPG_ISLAND_FILE} not found.")
        sys.exit(1)
        
    cpg_islands = []
    
    with open(CPG_ISLAND_FILE, 'r') as f:
        for line in f:
            fields = line.strip().split('\t')
            if len(fields) < 6:
                continue
                
            bin_val = fields[0]
            chrom = fields[1]
            start = int(fields[2])
            end = int(fields[3])
            name = fields[4]
            
            cpg_islands.append({
                'name': name,
                'chromosome': chrom,
                'start': start,
                'end': end
            })
    
    print(f"Loaded {len(cpg_islands)} CpG islands")
    return cpg_islands

def analyze_insertion_locations(insertions, genes, cpg_islands):
    """
    Analyze insertion locations relative to genes and regulatory regions
    """
    # Organize genes and CpG islands by chromosome for faster lookup
    genes_by_chrom = defaultdict(list)
    for gene in genes:
        genes_by_chrom[gene['chromosome']].append(gene)
    
    cpg_by_chrom = defaultdict(list)
    for cpg in cpg_islands:
        cpg_by_chrom[cpg['chromosome']].append(cpg)
    
    # Analyze each insertion
    insertion_locations = []
    
    for ins in insertions:
        chrom = ins['chromosome']
        pos = ins['position']
        
        # Initialize location data
        location = {
            'insertion': ins,
            'in_gene': False,
            'gene_name': None,
            'gene_distance': float('inf'),
            'in_exon': False,
            'near_promoter': False,
            'promoter_distance': float('inf'),
            'near_cpg': False,
            'cpg_distance': float('inf')
        }
        
        # Check genes on this chromosome
        for gene in genes_by_chrom[chrom]:
            # Check if insertion is within gene boundaries
            if gene['tx_start'] <= pos <= gene['tx_end']:
                location['in_gene'] = True
                location['gene_name'] = gene['gene_name']
                location['gene_distance'] = 0
                
                # Check if insertion is in an exon
                for i in range(gene['exon_count']):
                    if gene['exon_starts'][i] <= pos <= gene['exon_ends'][i]:
                        location['in_exon'] = True
                        break
            
            # Check distance to gene if not in gene
            elif not location['in_gene']:
                if pos < gene['tx_start']:
                    distance = gene['tx_start'] - pos
                else:
                    distance = pos - gene['tx_end']
                
                if distance < location['gene_distance']:
                    location['gene_distance'] = distance
                    location['gene_name'] = gene['gene_name']
            
            # Check if insertion is near promoter
            # Promoter is defined as 2kb upstream of transcription start site
            if gene['strand'] == '+':
                promoter_start = max(0, gene['tx_start'] - PROMOTER_PROXIMITY)
                promoter_end = gene['tx_start']
            else:
                promoter_start = gene['tx_end']
                promoter_end = gene['tx_end'] + PROMOTER_PROXIMITY
            
            if promoter_start <= pos <= promoter_end:
                location['near_promoter'] = True
                location['promoter_distance'] = 0
            else:
                if pos < promoter_start:
                    distance = promoter_start - pos
                else:
                    distance = pos - promoter_end
                
                if distance < location['promoter_distance']:
                    location['promoter_distance'] = distance
        
        # Check CpG islands on this chromosome
        for cpg in cpg_by_chrom[chrom]:
            if cpg['start'] <= pos <= cpg['end']:
                location['near_cpg'] = True
                location['cpg_distance'] = 0
            else:
                if pos < cpg['start']:
                    distance = cpg['start'] - pos
                else:
                    distance = pos - cpg['end']
                
                if distance < location['cpg_distance']:
                    location['cpg_distance'] = distance
        
        # Set proximity flags based on thresholds
        if not location['in_gene'] and location['gene_distance'] <= GENE_PROXIMITY:
            location['near_gene'] = True
        else:
            location['near_gene'] = False
        
        if not location['near_promoter'] and location['promoter_distance'] <= PROMOTER_PROXIMITY:
            location['near_promoter'] = True
        
        if not location['near_cpg'] and location['cpg_distance'] <= REGULATORY_PROXIMITY:
            location['near_cpg'] = True
        
        insertion_locations.append(location)
    
    return insertion_locations

def generate_report(insertion_locations):
    """
    Generate a comprehensive report of insertion locations
    """
    # Count insertions in different genomic contexts
    total_insertions = len(insertion_locations)
    in_gene_count = sum(1 for loc in insertion_locations if loc['in_gene'])
    in_exon_count = sum(1 for loc in insertion_locations if loc['in_exon'])
    near_gene_count = sum(1 for loc in insertion_locations if not loc['in_gene'] and loc['near_gene'])
    near_promoter_count = sum(1 for loc in insertion_locations if loc['near_promoter'])
    near_cpg_count = sum(1 for loc in insertion_locations if loc['near_cpg'])
    
    # Count insertions with repetitive elements in different genomic contexts
    with open(LOCATION_REPORT, 'w') as f:
        f.write("# Insertion Location Analysis\n\n")
        
        # Overview
        f.write("## Overview\n\n")
        f.write(f"Total insertions analyzed: {total_insertions}\n\n")
        
        # Location summary
        f.write("## Genomic Context of Insertions\n\n")
        f.write("| Location | Count | Percentage |\n")
        f.write("|----------|-------|------------|\n")
        f.write(f"| Within genes | {in_gene_count} | {(in_gene_count/total_insertions)*100:.2f}% |\n")
        f.write(f"| Within exons | {in_exon_count} | {(in_exon_count/total_insertions)*100:.2f}% |\n")
        f.write(f"| Near genes (≤{GENE_PROXIMITY/1000}kb) | {near_gene_count} | {(near_gene_count/total_insertions)*100:.2f}% |\n")
        f.write(f"| Near promoters (≤{PROMOTER_PROXIMITY/1000}kb) | {near_promoter_count} | {(near_promoter_count/total_insertions)*100:.2f}% |\n")
        f.write(f"| Near CpG islands (≤{REGULATORY_PROXIMITY/1000}kb) | {near_cpg_count} | {(near_cpg_count/total_insertions)*100:.2f}% |\n")
        f.write("\n")
        
        # Examples of insertions in genes
        f.write("## Examples of Insertions Within Genes\n\n")
        in_gene_examples = [loc for loc in insertion_locations if loc['in_gene']][:10]
        if in_gene_examples:
            f.write("| Chromosome | Position | Gene | In Exon |\n")
            f.write("|------------|----------|------|--------|\n")
            for loc in in_gene_examples:
                ins = loc['insertion']
                f.write(f"| {ins['chromosome']} | {ins['position']} | {loc['gene_name']} | {'Yes' if loc['in_exon'] else 'No'} |\n")
        else:
            f.write("No insertions found within genes.\n")
        f.write("\n")
        
        # Examples of insertions near promoters
        f.write("## Examples of Insertions Near Promoters\n\n")
        near_promoter_examples = [loc for loc in insertion_locations if loc['near_promoter']][:10]
        if near_promoter_examples:
            f.write("| Chromosome | Position | Gene | Distance to Promoter |\n")
            f.write("|------------|----------|------|---------------------|\n")
            for loc in near_promoter_examples:
                ins = loc['insertion']
                f.write(f"| {ins['chromosome']} | {ins['position']} | {loc['gene_name']} | {loc['promoter_distance']} bp |\n")
        else:
            f.write("No insertions found near promoters.\n")
        f.write("\n")
        
        # Examples of insertions near CpG islands
        f.write("## Examples of Insertions Near CpG Islands\n\n")
        near_cpg_examples = [loc for loc in insertion_locations if loc['near_cpg']][:10]
        if near_cpg_examples:
            f.write("| Chromosome | Position | Distance to CpG Island |\n")
            f.write("|------------|----------|------------------------|\n")
            for loc in near_cpg_examples:
                ins = loc['insertion']
                f.write(f"| {ins['chromosome']} | {ins['position']} | {loc['cpg_distance']} bp |\n")
        else:
            f.write("No insertions found near CpG islands.\n")
        f.write("\n")
        
        # Potential functional impact
        f.write("## Potential Functional Impact\n\n")
        f.write("Insertions in different genomic contexts can have varying functional impacts:\n\n")
        f.write("1. **Insertions within genes** may disrupt gene function, particularly if they occur within exons.\n")
        f.write("2. **Insertions near promoters** may affect gene expression by altering transcription factor binding or chromatin structure.\n")
        f.write("3. **Insertions near CpG islands** may impact epigenetic regulation of nearby genes.\n\n")
        
        f.write("The analysis shows that:\n\n")
        f.write(f"- {in_gene_count} insertions ({(in_gene_count/total_insertions)*100:.2f}%) are within genes, potentially affecting gene function\n")
        f.write(f"- {in_exon_count} insertions ({(in_exon_count/total_insertions)*100:.2f}%) are within exons, which could directly impact protein coding\n")
        f.write(f"- {near_promoter_count} insertions ({(near_promoter_count/total_insertions)*100:.2f}%) are near promoters, potentially affecting gene expression\n")
        f.write(f"- {near_cpg_count} insertions ({(near_cpg_count/total_insertions)*100:.2f}%) are near CpG islands, which could impact epigenetic regulation\n\n")
        
        # Conclusion
        f.write("## Conclusion\n\n")
        f.write("This analysis provides insights into the potential functional impact of structural variant insertions in your genome. ")
        f.write("A significant proportion of insertions are located in or near functionally important regions, suggesting they may have biological consequences. ")
        f.write("Further analysis, including detailed examination of specific genes affected and the types of repetitive elements involved, would provide deeper insights into the potential phenotypic effects of these variants.\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Examine specific genes affected by insertions for their biological functions and disease associations\n")
        f.write("2. Correlate repetitive element types with genomic locations to identify patterns\n")
        f.write("3. Compare your insertion profile with population databases to identify rare or common variants\n")
        f.write("4. Consider functional validation of insertions in genes of interest\n")
    
    print(f"Location analysis report generated: {LOCATION_REPORT}")

def main():
    print("Starting insertion location analysis...")
    
    # Load insertion data
    insertions = load_insertion_data()
    
    if not insertions:
        print("No insertion data found. Exiting.")
        return
    
    # Load reference data
    genes = load_gene_data()
    cpg_islands = load_cpg_islands()
    
    # Analyze insertion locations
    print("Analyzing insertion locations...")
    insertion_locations = analyze_insertion_locations(insertions, genes, cpg_islands)
    
    # Generate report
    print("Generating location analysis report...")
    generate_report(insertion_locations)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
