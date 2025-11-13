#!/usr/bin/env python3
"""
Gene Interaction Visualization Script

This script creates ASCII-based visualizations of the interactions between
SHANK2, SHANK3, CNTN4, and PTPRN2 genes, showing their shared pathways
and potential cumulative effects of the identified insertions.
"""

import os
import csv
from collections import defaultdict

# Define paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
SV_ANALYSIS_DIR = os.path.join(BASE_DIR, "sv_analysis")
INSERTIONS_FILE = os.path.join(SV_ANALYSIS_DIR, "insertions_in_genes.tsv")
OUTPUT_FILE = os.path.join(SV_ANALYSIS_DIR, "gene_interaction_visualization.md")

# Define key genes for analysis
KEY_GENES = ["SHANK2", "SHANK3", "CNTN4", "PTPRN2"]

# Define shared pathways and processes
SHARED_PATHWAYS = {
    "Synaptic Function": ["SHANK2", "SHANK3", "CNTN4"],
    "Neural Development": ["SHANK2", "SHANK3", "CNTN4", "PTPRN2"],
    "Vesicle Trafficking": ["PTPRN2", "SHANK2", "SHANK3"],
    "Metabolic Signaling": ["PTPRN2", "SHANK3"],
    "Cell Adhesion": ["CNTN4", "SHANK3"],
    "Cytoskeletal Regulation": ["SHANK2", "SHANK3"],
    "mTOR Signaling": ["SHANK3", "PTPRN2"]
}

# Define gene functions and domains
GENE_FUNCTIONS = {
    "SHANK2": {
        "Primary Function": "Postsynaptic scaffold protein",
        "Domains": ["ANK repeat", "SH3", "PDZ", "Proline-rich", "SAM"],
        "Expression": "Brain (excitatory synapses)",
        "Associated Conditions": "Autism spectrum disorders, intellectual disability"
    },
    "SHANK3": {
        "Primary Function": "Postsynaptic scaffold protein",
        "Domains": ["ANK repeat", "SH3", "PDZ", "Proline-rich", "SAM"],
        "Expression": "Brain (excitatory synapses)",
        "Associated Conditions": "Autism spectrum disorders, Phelan-McDermid syndrome"
    },
    "CNTN4": {
        "Primary Function": "Axon guidance and neural circuit formation",
        "Domains": ["Ig-like", "Fibronectin type III", "GPI anchor"],
        "Expression": "Developing nervous system, olfactory system",
        "Associated Conditions": "Neurodevelopmental disorders, autism spectrum disorders"
    },
    "PTPRN2": {
        "Primary Function": "Dense-core vesicle protein, insulin secretion",
        "Domains": ["Signal peptide", "Extracellular", "Transmembrane", "Phosphatase-like"],
        "Expression": "Neuroendocrine cells, pancreatic beta cells, brain",
        "Associated Conditions": "Type 1 diabetes autoantigen, metabolic disorders"
    }
}

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

def create_gene_interaction_matrix():
    """Create a matrix visualization of gene interactions."""
    # Create the matrix header
    matrix = ["# Gene Interaction Matrix\n"]
    matrix.append("This matrix shows the shared pathways and processes between the four genes of interest.\n\n")
    
    # Create the header row
    header = "| Pathway/Process |"
    for gene in KEY_GENES:
        header += f" {gene} |"
    matrix.append(header)
    
    # Create the separator row
    separator = "|----------------|"
    for _ in KEY_GENES:
        separator += "---------|"
    matrix.append(separator)
    
    # Create rows for each pathway
    for pathway, genes in SHARED_PATHWAYS.items():
        row = f"| {pathway} |"
        for gene in KEY_GENES:
            if gene in genes:
                row += " ✓ |"
            else:
                row += "   |"
        matrix.append(row)
    
    return "\n".join(matrix)

def create_insertion_summary(key_genes_insertions):
    """Create a summary of insertions for each gene."""
    if key_genes_insertions is None:
        return "No insertion data available."
    
    # Group insertions by gene
    gene_insertions = defaultdict(list)
    for insertion in key_genes_insertions:
        gene_insertions[insertion['Gene']].append(insertion)
    
    # Create summary
    summary = ["# Insertion Summary by Gene\n"]
    summary.append("This table summarizes the insertions found in each gene and their characteristics.\n\n")
    
    # Create table header
    summary.append("| Gene | Insertions | Homozygous | Heterozygous | Average Length | Potential Impact |\n")
    summary.append("|------|------------|------------|--------------|----------------|------------------|\n")
    
    # Add rows for each gene
    for gene in KEY_GENES:
        insertions = gene_insertions.get(gene, [])
        if not insertions:
            continue
        
        num_insertions = len(insertions)
        homozygous = sum(1 for ins in insertions if ins['Genotype'] == "1/1")
        heterozygous = num_insertions - homozygous
        
        # Calculate average length
        lengths = []
        for ins in insertions:
            length_str = ins.get('Length', '0')
            if length_str and length_str.isdigit():
                lengths.append(int(length_str))
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        
        # Determine potential impact
        impact = get_potential_impact(gene, homozygous, heterozygous, avg_length)
        
        # Add row
        summary.append(f"| {gene} | {num_insertions} | {homozygous} | {heterozygous} | {avg_length:.0f} bp | {impact} |\n")
    
    return "\n".join(summary)

def get_potential_impact(gene, homozygous, heterozygous, avg_length):
    """Determine the potential impact based on insertion characteristics."""
    impact_level = []
    
    # Impact based on zygosity
    if homozygous > 0:
        impact_level.append("Homozygous variants")
    
    # Impact based on length
    if avg_length > 300:
        impact_level.append("Long insertions")
    
    # Gene-specific impacts
    if gene == "SHANK2" or gene == "SHANK3":
        impact_level.append("Synaptic organization")
    elif gene == "CNTN4":
        impact_level.append("Neural circuit formation")
    elif gene == "PTPRN2":
        impact_level.append("Insulin signaling")
    
    return ", ".join(impact_level)

def create_pathway_visualization():
    """Create a visualization of shared pathways between genes."""
    vis = ["# Shared Pathway Visualization\n"]
    vis.append("This diagram illustrates the shared biological pathways and processes between the four genes.\n\n")
    vis.append("```\n")
    
    # Create a simple network diagram
    vis.append("                   Neural Development                  ")
    vis.append("                          |                            ")
    vis.append("                          v                            ")
    vis.append("  +-------------+     +-------+     +--------------+   ")
    vis.append("  |             |     |       |     |              |   ")
    vis.append("  |   SHANK2    |<--->| CNTN4 |     |    PTPRN2    |   ")
    vis.append("  |             |     |       |     |              |   ")
    vis.append("  +------^------+     +---^---+     +------^-------+   ")
    vis.append("         |                |                |           ")
    vis.append("         |                |                |           ")
    vis.append("         v                v                v           ")
    vis.append("  +------+----------------+----------------+------+    ")
    vis.append("  |                                               |    ")
    vis.append("  |                    SHANK3                     |    ")
    vis.append("  |                                               |    ")
    vis.append("  +-----------------------------------------------+    ")
    vis.append("         |                |                |           ")
    vis.append("         v                v                v           ")
    vis.append("  Synaptic Function  Cell Adhesion  Metabolic Signaling")
    vis.append("```\n")
    
    return "\n".join(vis)

def create_cumulative_effect_visualization():
    """Create a visualization of potential cumulative effects."""
    vis = ["# Potential Cumulative Effects Visualization\n"]
    vis.append("This diagram illustrates how insertions in multiple genes might lead to cumulative effects on phenotype.\n\n")
    vis.append("```\n")
    vis.append("  GENOMIC INSERTIONS                 AFFECTED PATHWAYS                 POTENTIAL PHENOTYPIC EFFECTS  ")
    vis.append("  ------------------                 -----------------                 ----------------------------  ")
    vis.append("                                                                                                     ")
    vis.append("  +----------------+                +------------------+                                             ")
    vis.append("  | SHANK2         |--------------->| Synaptic         |                                             ")
    vis.append("  | 1 homozygous   |                | Organization     |----+                                        ")
    vis.append("  +----------------+                +------------------+    |                                        ")
    vis.append("                                                            |                                        ")
    vis.append("  +----------------+                +------------------+    |         +------------------------+     ")
    vis.append("  | SHANK3         |--------------->| Synaptic         |    +-------->| Neurological &        |     ")
    vis.append("  | 1 homozygous   |                | Plasticity       |----+         | Cognitive Function    |     ")
    vis.append("  +----------------+                +------------------+    |         +------------------------+     ")
    vis.append("                                                            |                                        ")
    vis.append("  +----------------+                +------------------+    |                                        ")
    vis.append("  | CNTN4          |--------------->| Neural Circuit   |----+                                        ")
    vis.append("  | 2 homozygous   |                | Formation        |                                             ")
    vis.append("  | 2 heterozygous |                +------------------+                                             ")
    vis.append("  +----------------+                                                                                 ")
    vis.append("                                    +------------------+              +------------------------+     ")
    vis.append("  +----------------+                | Insulin          |              | Metabolic Function &   |     ")
    vis.append("  | PTPRN2         |--------------->| Signaling        |------------->| Growth Regulation      |     ")
    vis.append("  | 4 homozygous   |                +------------------+              +------------------------+     ")
    vis.append("  | 1 heterozygous |                                                                                 ")
    vis.append("  +----------------+                +------------------+                                             ")
    vis.append("                                    | Vesicle          |                                             ")
    vis.append("                                    | Trafficking      |                                             ")
    vis.append("                                    +------------------+                                             ")
    vis.append("```\n")
    
    return "\n".join(vis)

def generate_report(key_genes_insertions):
    """Generate a comprehensive report with visualizations."""
    report = []
    
    # Add title and introduction
    report.append("# Gene Interaction and Cumulative Effect Visualization\n")
    report.append("## Introduction\n")
    report.append("This report provides visualizations of the potential interactions between SHANK2, SHANK3, CNTN4, and PTPRN2 genes, and how the identified insertions might collectively impact biological pathways and processes.\n\n")
    
    # Add gene information
    report.append("## Gene Information\n")
    for gene in KEY_GENES:
        info = GENE_FUNCTIONS.get(gene, {})
        report.append(f"### {gene}\n")
        report.append(f"**Primary Function:** {info.get('Primary Function', 'Unknown')}\n")
        report.append(f"**Key Domains:** {', '.join(info.get('Domains', ['Unknown']))}\n")
        report.append(f"**Expression Pattern:** {info.get('Expression', 'Unknown')}\n")
        report.append(f"**Associated Conditions:** {info.get('Associated Conditions', 'Unknown')}\n\n")
    
    # Add insertion summary
    report.append(create_insertion_summary(key_genes_insertions))
    report.append("\n\n")
    
    # Add interaction matrix
    report.append(create_gene_interaction_matrix())
    report.append("\n\n")
    
    # Add pathway visualization
    report.append(create_pathway_visualization())
    report.append("\n\n")
    
    # Add cumulative effect visualization
    report.append(create_cumulative_effect_visualization())
    report.append("\n\n")
    
    # Add key findings
    report.append("## Key Findings\n")
    report.append("1. **Multiple Affected Pathways:** The four genes participate in several shared biological pathways, suggesting potential for cumulative effects.\n\n")
    report.append("2. **Predominance of Homozygous Insertions:** 8 out of 11 insertions are homozygous, potentially resulting in stronger functional impacts.\n\n")
    report.append("3. **Synaptic Function Impact:** SHANK2, SHANK3, and CNTN4 all contribute to synaptic development and function, suggesting a potential cumulative effect on neural circuit formation and function.\n\n")
    report.append("4. **Metabolic-Neuronal Interface:** PTPRN2 and SHANK3 share involvement in metabolic signaling pathways, suggesting a potential link between insulin signaling and neuronal function.\n\n")
    report.append("5. **Potential Phenotypic Convergence:** Despite affecting different primary pathways, the cumulative effects may converge on related phenotypic outcomes in neurological function and metabolic regulation.\n\n")
    
    # Add conclusion
    report.append("## Conclusion\n")
    report.append("The visualizations and analyses presented in this report highlight the interconnected nature of SHANK2, SHANK3, CNTN4, and PTPRN2 genes. The insertions identified in these genes may have cumulative effects on shared biological pathways, potentially resulting in more significant impacts than would be expected from any single gene disruption.\n\n")
    report.append("The predominance of homozygous insertions suggests potentially stronger functional impacts, particularly in pathways related to synaptic function, neural circuit formation, and insulin signaling. These cumulative effects may contribute to a distinctive profile of neurological, developmental, and metabolic characteristics.\n\n")
    report.append("Further functional studies would be valuable to validate these predicted interactions and cumulative effects, and to better understand how they may manifest phenotypically.\n")
    
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
    
    print(f"Gene interaction visualization report generated at {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
