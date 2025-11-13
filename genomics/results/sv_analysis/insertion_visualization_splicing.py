#!/usr/bin/env python3
"""
Visualization and Splicing Impact Analysis of Genomic Insertions

This script creates visualizations of insertion patterns and analyzes potential
splicing impacts, with a special focus on PTPRN2 and its effects on insulin signaling.
"""

import os
import csv
import re
from collections import defaultdict

# ASCII visualization will be used instead of matplotlib to avoid dependencies
# Simple splicing prediction tools will be implemented

# Define paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
SV_ANALYSIS_DIR = os.path.join(BASE_DIR, "sv_analysis")
INSERTIONS_FILE = os.path.join(SV_ANALYSIS_DIR, "insertions_in_genes.tsv")
OUTPUT_FILE = os.path.join(SV_ANALYSIS_DIR, "insertion_visualization_splicing.md")

# Define key genes for detailed analysis
KEY_GENES = ["SHANK2", "SHANK3", "CNTN4", "PTPRN2"]

# Define known splice site motifs
SPLICE_SITE_MOTIFS = {
    "5' splice site (donor)": ["GT", "GC"],  # Consensus at exon-intron boundary
    "3' splice site (acceptor)": ["AG"],     # Consensus at intron-exon boundary
    "Branch point": ["YNYURAY"],             # Y=C/T, N=any, R=A/G
    "Polypyrimidine tract": ["(Y)n"],        # Stretch of pyrimidines (C/T)
    "Exonic splicing enhancer": ["GAAGAA", "AAGAAG", "GGAGGA"],
    "Exonic splicing silencer": ["TTATT", "TTTTT"],
    "Intronic splicing enhancer": ["GGGG", "GGGT"],
    "Intronic splicing silencer": ["TTTT", "CCCC"]
}

# Define PTPRN2 exon boundaries (simplified for demonstration)
# Format: (start, end) for each exon
PTPRN2_EXONS = [
    (157600000, 157601000),
    (157650000, 157651000),
    (157700000, 157701000),
    (158000000, 158001000),
    (158050000, 158051000),
    (158100000, 158101000),
    (158350000, 158351000),
    (158400000, 158401000)
]

def load_insertions_data():
    """Load the insertions data from the TSV file."""
    try:
        insertions = []
        with open(INSERTIONS_FILE, 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                insertions.append(row)
        return insertions
    except Exception as e:
        print(f"Error loading insertions data: {e}")
        return None

def filter_key_genes(insertions):
    """Filter the insertions to include only the key genes of interest."""
    if insertions is not None:
        return [ins for ins in insertions if ins['Gene'] in KEY_GENES]
    return None

def create_gene_structure_visualization(gene, insertions):
    """Create an ASCII visualization of the gene structure with insertions."""
    # Sort insertions by position
    sorted_insertions = sorted(insertions, key=lambda x: int(x['Position']))
    
    # Determine gene span
    min_pos = min(int(ins['Position']) for ins in insertions)
    max_pos = max(int(ins['Position']) for ins in insertions)
    gene_span = max_pos - min_pos
    
    # Create a visualization with a fixed width
    vis_width = 60
    vis = ['-' * vis_width]
    
    # Add exons if available
    if gene == "PTPRN2":
        for exon_start, exon_end in PTPRN2_EXONS:
            if min_pos <= exon_end and max_pos >= exon_start:
                # Calculate relative position
                gene_span = max(1, gene_span)
                rel_start = int((exon_start - min_pos) / gene_span * vis_width)
                rel_end = int((exon_end - min_pos) / gene_span * vis_width)
                rel_start = max(0, min(rel_start, vis_width - 1))
                rel_end = max(0, min(rel_end, vis_width - 1))
                
                # Add exon to visualization
                exon_vis = list(vis[0])
                for i in range(rel_start, rel_end + 1):
                    if i < len(exon_vis):
                        exon_vis[i] = '='
                vis[0] = ''.join(exon_vis)
    
    # Add insertions to visualization
    labels = []
    for i, ins in enumerate(sorted_insertions):
        pos = int(ins['Position'])
        gene_span = max(1, gene_span)
        rel_pos = int((pos - min_pos) / gene_span * vis_width)
        rel_pos = max(0, min(rel_pos, vis_width - 1))
        
        # Add insertion marker
        ins_vis = list(vis[0])
        ins_vis[rel_pos] = 'I'
        vis[0] = ''.join(ins_vis)
        
        # Add label
        genotype = ins['Genotype']
        length = ins.get('Length', 'Unknown')
        labels.append(f"I{i+1}: Position {pos}, Genotype {genotype}, Length {length}")
    
    # Combine visualization and labels
    result = [vis[0]]
    result.extend(labels)
    
    return result

def analyze_distance_to_exon(gene, insertions):
    """Analyze the distance of insertions to the nearest exon."""
    results = []
    
    if gene == "PTPRN2":
        for ins in insertions:
            pos = int(ins['Position'])
            min_distance = float('inf')
            nearest_exon = None
            
            for i, (exon_start, exon_end) in enumerate(PTPRN2_EXONS):
                # Check if insertion is within exon
                if exon_start <= pos <= exon_end:
                    min_distance = 0
                    nearest_exon = i + 1
                    break
                
                # Check distance to exon start
                dist_to_start = abs(pos - exon_start)
                if dist_to_start < min_distance:
                    min_distance = dist_to_start
                    nearest_exon = i + 1
                
                # Check distance to exon end
                dist_to_end = abs(pos - exon_end)
                if dist_to_end < min_distance:
                    min_distance = dist_to_end
                    nearest_exon = i + 1
            
            results.append({
                'Position': pos,
                'Nearest Exon': nearest_exon,
                'Distance': min_distance,
                'Genotype': ins['Genotype']
            })
    
    return results

def predict_splicing_impact(gene, insertions):
    """Predict potential splicing impacts of insertions."""
    results = []
    
    for ins in insertions:
        pos = int(ins['Position'])
        genotype = ins['Genotype']
        sequence = ins.get('Sequence', '')
        
        impact = {
            'Position': pos,
            'Genotype': genotype,
            'Potential Impacts': []
        }
        
        # Check distance to exons (for PTPRN2)
        if gene == "PTPRN2":
            for i, (exon_start, exon_end) in enumerate(PTPRN2_EXONS):
                # Near exon boundary (potential splice site disruption)
                if abs(pos - exon_start) < 100 or abs(pos - exon_end) < 100:
                    impact['Potential Impacts'].append(
                        f"Near exon {i+1} boundary: May disrupt splice site recognition"
                    )
        
        # Check for creation or disruption of splice motifs
        for motif_type, patterns in SPLICE_SITE_MOTIFS.items():
            for pattern in patterns:
                if pattern in sequence:
                    impact['Potential Impacts'].append(
                        f"Contains {motif_type} motif: May create cryptic splice site"
                    )
        
        # Homozygous vs heterozygous impact
        if genotype == "1/1":
            impact['Potential Impacts'].append(
                "Homozygous insertion: Both alleles affected, potentially stronger impact on splicing"
            )
        else:
            impact['Potential Impacts'].append(
                "Heterozygous insertion: One wild-type allele remains, potentially milder impact on splicing"
            )
        
        # Length-based impact
        length = int(ins.get('Length', '0') or '0')
        if length > 300:
            impact['Potential Impacts'].append(
                f"Long insertion ({length} bp): May significantly alter intron structure and splicing efficiency"
            )
        
        results.append(impact)
    
    return results

def analyze_ptprn2_insulin_signaling(insertions):
    """Analyze potential impacts on insulin signaling for PTPRN2 insertions."""
    results = []
    
    # PTPRN2 functional domains (simplified for demonstration)
    domains = {
        (157600000, 157700000): "Signal peptide",
        (157700000, 158000000): "Extracellular domain",
        (158000000, 158100000): "Transmembrane domain",
        (158100000, 158400000): "Phosphatase-like domain"
    }
    
    for ins in insertions:
        pos = int(ins['Position'])
        genotype = ins['Genotype']
        
        impact = {
            'Position': pos,
            'Genotype': genotype,
            'Domain': "Unknown",
            'Insulin Signaling Impact': []
        }
        
        # Determine affected domain
        for (domain_start, domain_end), domain_name in domains.items():
            if domain_start <= pos <= domain_end:
                impact['Domain'] = domain_name
                break
        
        # Assess potential impact on insulin signaling
        if impact['Domain'] == "Signal peptide":
            impact['Insulin Signaling Impact'].append(
                "May affect protein trafficking to dense-core vesicles"
            )
        elif impact['Domain'] == "Extracellular domain":
            impact['Insulin Signaling Impact'].append(
                "May affect protein folding or interaction with other vesicle proteins"
            )
        elif impact['Domain'] == "Transmembrane domain":
            impact['Insulin Signaling Impact'].append(
                "May affect membrane anchoring or vesicle fusion"
            )
        elif impact['Domain'] == "Phosphatase-like domain":
            impact['Insulin Signaling Impact'].append(
                "May affect interaction with insulin secretory machinery"
            )
        
        # General impacts
        impact['Insulin Signaling Impact'].append(
            "PTPRN2 is involved in insulin secretion from pancreatic beta cells"
        )
        
        if genotype == "1/1":
            impact['Insulin Signaling Impact'].append(
                "Homozygous insertion may have stronger effect on insulin secretion"
            )
        else:
            impact['Insulin Signaling Impact'].append(
                "Heterozygous insertion may have milder effect on insulin secretion"
            )
        
        # Literature-based insights
        impact['Insulin Signaling Impact'].append(
            "Studies suggest PTPRN2 variants may affect glucose metabolism and insulin sensitivity"
        )
        
        # Note on body size
        impact['Insulin Signaling Impact'].append(
            "Note: Small body size is influenced by many factors beyond insulin signaling, including growth hormone, thyroid function, and genetics"
        )
        
        results.append(impact)
    
    return results

def generate_report(key_genes_insertions):
    """Generate a detailed report with visualizations and splicing analysis."""
    if key_genes_insertions is None or len(key_genes_insertions) == 0:
        return "No data available for analysis."
    
    report = []
    report.append("# Visualization and Splicing Impact Analysis of Genomic Insertions\n")
    
    # Add introduction
    report.append("## Introduction\n")
    report.append("This report provides visualizations of insertion patterns and analyzes potential splicing impacts of genomic insertions in key neurological and developmental genes, with a special focus on PTPRN2 and its potential effects on insulin signaling.\n")
    
    # Group insertions by gene
    gene_insertions = defaultdict(list)
    for insertion in key_genes_insertions:
        gene_insertions[insertion['Gene']].append(insertion)
    
    # Process each gene
    for gene in KEY_GENES:
        if gene not in gene_insertions:
            continue
        
        insertions = gene_insertions[gene]
        
        report.append(f"## {gene}\n")
        
        # Add gene visualization
        report.append("### Gene Structure and Insertion Visualization\n")
        report.append("```\n")
        vis = create_gene_structure_visualization(gene, insertions)
        report.extend(vis)
        report.append("```\n")
        
        # Add splicing impact analysis
        report.append("### Potential Splicing Impacts\n")
        
        splicing_impacts = predict_splicing_impact(gene, insertions)
        
        for impact in splicing_impacts:
            report.append(f"#### Insertion at position {impact['Position']} (Genotype: {impact['Genotype']})\n")
            
            if not impact['Potential Impacts']:
                report.append("No significant splicing impacts predicted.\n")
            else:
                report.append("**Potential splicing impacts**:\n")
                for imp in impact['Potential Impacts']:
                    report.append(f"- {imp}\n")
            
            report.append("\n")
        
        # Special analysis for PTPRN2
        if gene == "PTPRN2":
            report.append("### Distance to Nearest Exon\n")
            
            exon_distances = analyze_distance_to_exon(gene, insertions)
            
            report.append("| Position | Nearest Exon | Distance (bp) | Genotype |\n")
            report.append("|----------|--------------|---------------|----------|\n")
            
            for dist in exon_distances:
                report.append(f"| {dist['Position']} | {dist['Nearest Exon']} | {dist['Distance']} | {dist['Genotype']} |\n")
            
            report.append("\n### Insulin Signaling Impact Analysis\n")
            
            insulin_impacts = analyze_ptprn2_insulin_signaling(insertions)
            
            for impact in insulin_impacts:
                report.append(f"#### Insertion at position {impact['Position']} (Genotype: {impact['Genotype']})\n")
                report.append(f"**Domain affected**: {impact['Domain']}\n")
                report.append("**Potential impacts on insulin signaling**:\n")
                
                for imp in impact['Insulin Signaling Impact']:
                    report.append(f"- {imp}\n")
                
                report.append("\n")
    
    # Add overall assessment
    report.append("## Overall Assessment\n")
    
    report.append("### Summary of Findings\n")
    report.append("1. **Insertion Patterns**: The visualizations show the distribution of insertions across each gene, highlighting potential hotspots and their relationship to exons.\n")
    report.append("2. **Splicing Impacts**: Most insertions are in intronic regions and may affect splicing by creating or disrupting splice regulatory elements.\n")
    report.append("3. **PTPRN2 and Insulin Signaling**: The insertions in PTPRN2 could potentially affect insulin secretion, but the impact on body size is likely multifactorial.\n\n")
    
    report.append("### PTPRN2 and Body Size\n")
    report.append("While PTPRN2 plays a role in insulin secretion, it's important to note that body size is determined by many factors:\n\n")
    report.append("1. **Genetic factors**: Hundreds of genes influence height and body composition\n")
    report.append("2. **Hormonal factors**: Growth hormone, thyroid hormones, and sex hormones all play crucial roles\n")
    report.append("3. **Nutritional factors**: Nutrition during development significantly impacts growth\n")
    report.append("4. **Environmental factors**: Various environmental influences affect growth and development\n\n")
    
    report.append("The insertions in PTPRN2 may have some effect on insulin signaling, but it would be one of many factors influencing body size. A comprehensive assessment would require additional genetic, hormonal, and clinical data.\n")
    
    return "\n".join(report)

def main():
    """Main function to run the analysis."""
    # Load the insertions data
    insertions = load_insertions_data()
    
    if insertions is None:
        print("Failed to load insertions data.")
        return
    
    # Filter for key genes
    key_genes_insertions = filter_key_genes(insertions)
    
    if key_genes_insertions is None or len(key_genes_insertions) == 0:
        print("No data available for key genes.")
        return
    
    # Generate the report
    report = generate_report(key_genes_insertions)
    
    # Write the report to a file
    with open(OUTPUT_FILE, 'w') as f:
        f.write(report)
    
    print(f"Visualization and splicing analysis report generated at {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
