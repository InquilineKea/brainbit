#!/usr/bin/env python3
"""
Functional Impact Analysis of Genomic Insertions

This script performs a detailed analysis of the potential functional impacts
of genomic insertions in key neurological and developmental genes.
"""

import os
import csv
import re
from collections import defaultdict

# Define paths
BASE_DIR = "/Users/simfish/Downloads/Genome"
SV_ANALYSIS_DIR = os.path.join(BASE_DIR, "sv_analysis")
INSERTIONS_FILE = os.path.join(SV_ANALYSIS_DIR, "insertions_in_genes.tsv")
OUTPUT_FILE = os.path.join(SV_ANALYSIS_DIR, "functional_impact_analysis.md")

# Define key genes for detailed analysis
KEY_GENES = ["SHANK2", "SHANK3", "CNTN4", "PTPRN2"]

# Define gene regions and their potential impacts
GENE_REGIONS = {
    "5' UTR": "May affect gene expression by altering transcription factor binding sites or mRNA stability",
    "3' UTR": "May affect mRNA stability, localization, and translation efficiency",
    "Exonic": "May directly affect protein structure and function, potentially leading to altered protein activity or loss of function",
    "Intronic": "May affect splicing, introduce cryptic splice sites, or disrupt regulatory elements within introns",
    "Promoter": "May affect gene expression by altering transcription factor binding or promoter activity",
    "Enhancer": "May affect gene expression by disrupting long-range regulatory elements",
    "Unknown": "Impact cannot be determined without additional information about the insertion location"
}

# Define sequence motifs and their potential impacts
SEQUENCE_MOTIFS = {
    r"(A{10,})": "Poly-A tract: May affect DNA structure and stability, potentially leading to replication errors",
    r"(T{10,})": "Poly-T tract: May affect DNA structure and stability, potentially leading to replication errors",
    r"(G{10,})": "Poly-G tract: May form G-quadruplex structures that can affect replication and transcription",
    r"(C{10,})": "Poly-C tract: May form unusual DNA structures that can affect replication and transcription",
    r"(AT){5,}": "AT-rich region: May affect DNA melting and binding of regulatory proteins",
    r"(GC){5,}": "GC-rich region: May affect DNA methylation patterns and gene expression",
    r"(CAG){4,}": "CAG repeat: Associated with trinucleotide repeat disorders when expanded",
    r"(CTG){4,}": "CTG repeat: Associated with trinucleotide repeat disorders when expanded",
    r"(CGG){4,}": "CGG repeat: Associated with trinucleotide repeat disorders when expanded",
    r"(CCG){4,}": "CCG repeat: Associated with trinucleotide repeat disorders when expanded",
    r"TATA": "TATA box-like sequence: May create or disrupt promoter elements",
    r"CCAAT": "CCAAT box-like sequence: May create or disrupt promoter elements",
    r"GGGCGG": "GC box-like sequence: May create or disrupt promoter elements",
    r"AATAAA": "Polyadenylation signal-like sequence: May affect mRNA processing"
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

def analyze_sequence_motifs(sequence):
    """Analyze the sequence for known motifs that might have functional impacts."""
    motifs_found = []
    
    if not sequence or sequence == "":
        return motifs_found
    
    for pattern, description in SEQUENCE_MOTIFS.items():
        if re.search(pattern, sequence):
            motifs_found.append(description)
    
    return motifs_found

def determine_region_type(position, gene):
    """
    Placeholder function to determine the region type of the insertion.
    In a real-world scenario, this would use genomic annotation databases.
    For this example, we'll use a simple mapping based on position ranges.
    """
    position = int(position)
    
    # Define region ranges for each gene
    region_ranges = {
        "SHANK2": [
            ((70800000, 70805000), "Intronic"),
            ((70805000, 70810000), "Exonic"),
        ],
        "SHANK3": [
            ((50695000, 50700000), "Intronic"),
            ((50700000, 50705000), "Exonic"),
        ],
        "CNTN4": [
            ((2120000, 2130000), "Intronic"),
            ((2260000, 2270000), "Intronic"),
            ((2340000, 2350000), "Intronic"),
            ((2920000, 2930000), "Intronic"),
        ],
        "PTPRN2": [
            ((157650000, 157660000), "Intronic"),
            ((158045000, 158050000), "Intronic"),
            ((158385000, 158390000), "Intronic"),
        ]
    }
    
    if gene in region_ranges:
        for (start, end), region in region_ranges[gene]:
            if start <= position <= end:
                return region
    
    return "Unknown"

def assess_functional_impact(gene, region_type, motifs, genotype):
    """
    Assess the potential functional impact of an insertion based on:
    1. The gene affected
    2. The region type (exonic, intronic, etc.)
    3. The sequence motifs present
    4. The genotype (homozygous vs. heterozygous)
    """
    impact_level = "Low"
    impact_details = []
    
    # Impact based on region type
    if region_type in GENE_REGIONS:
        impact_details.append(f"Region impact: {GENE_REGIONS[region_type]}")
    
    # Impact based on sequence motifs
    if motifs:
        impact_details.append("Sequence motif impacts:")
        for motif in motifs:
            impact_details.append(f"  - {motif}")
    
    # Impact based on genotype
    if genotype == "1/1":  # Homozygous
        impact_details.append("Homozygous insertion: Potentially stronger effect as both alleles are affected")
        if region_type == "Exonic":
            impact_level = "High"
        elif region_type in ["5' UTR", "3' UTR", "Promoter", "Enhancer"]:
            impact_level = "Medium to High"
        else:
            impact_level = "Medium"
    else:  # Heterozygous
        impact_details.append("Heterozygous insertion: Potentially milder effect as one wild-type allele remains")
        if region_type == "Exonic":
            impact_level = "Medium to High"
        elif region_type in ["5' UTR", "3' UTR", "Promoter", "Enhancer"]:
            impact_level = "Medium"
        else:
            impact_level = "Low to Medium"
    
    # Gene-specific considerations
    gene_specific_impacts = {
        "SHANK2": "Insertions may affect scaffolding at excitatory synapses, potentially impacting synaptic development and function",
        "SHANK3": "Insertions may disrupt the master scaffolding protein in postsynaptic density, potentially affecting synaptic signaling",
        "CNTN4": "Insertions may affect axon guidance and neural circuit formation, potentially impacting neurodevelopment",
        "PTPRN2": "Insertions may affect insulin secretion and neurological function, potentially impacting both metabolic and neurological processes"
    }
    
    if gene in gene_specific_impacts:
        impact_details.append(f"Gene-specific impact: {gene_specific_impacts[gene]}")
    
    return impact_level, impact_details

def generate_report(key_genes_insertions):
    """Generate a detailed report of the functional impact analysis."""
    if key_genes_insertions is None or len(key_genes_insertions) == 0:
        return "No data available for analysis."
    
    report = []
    report.append("# Functional Impact Analysis of Genomic Insertions in Key Neurological Genes\n")
    
    # Add introduction
    report.append("## Introduction\n")
    report.append("This report provides a detailed analysis of the potential functional impacts of genomic insertions in key neurological and developmental genes. The analysis considers the insertion location, sequence characteristics, and genotype to assess the potential impact on gene function and related phenotypes.\n")
    
    # Add methodology
    report.append("## Methodology\n")
    report.append("The functional impact analysis was performed using the following approach:\n")
    report.append("1. **Gene selection**: Four key genes (SHANK2, SHANK3, CNTN4, and PTPRN2) were selected based on their importance in neurological development and association with neurodevelopmental disorders.\n")
    report.append("2. **Region analysis**: The genomic region of each insertion was determined to assess whether it affects coding sequences, regulatory elements, or other functional regions.\n")
    report.append("3. **Sequence motif analysis**: The inserted sequences were analyzed for known motifs that might have functional implications.\n")
    report.append("4. **Impact assessment**: The potential functional impact was assessed based on the gene affected, the region type, sequence motifs, and genotype.\n\n")
    
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
        
        # Add gene description
        gene_descriptions = {
            "SHANK2": "SHANK2 is a scaffolding protein found in the postsynaptic density of excitatory synapses. It plays a crucial role in synapse formation and function by connecting neurotransmitter receptors, ion channels, and other membrane proteins to the actin cytoskeleton and signaling pathways.",
            "SHANK3": "SHANK3 is a master scaffolding protein in the postsynaptic density of excitatory synapses. It is critical for proper synapse formation, maturation, and function. SHANK3 connects various synaptic proteins and signaling molecules to the actin cytoskeleton.",
            "CNTN4": "CNTN4 is a member of the contactin family of neural cell adhesion molecules. It plays important roles in axon guidance, neuronal network formation, and the development of functional neural circuits.",
            "PTPRN2": "PTPRN2 (also known as IA-2β or phogrin) is a member of the protein tyrosine phosphatase family. Despite its name, it lacks phosphatase activity. It is a transmembrane protein primarily found in dense-core secretory vesicles and plays a role in insulin secretion from pancreatic beta cells."
        }
        
        if gene in gene_descriptions:
            report.append(f"### Gene Description\n")
            report.append(f"{gene_descriptions[gene]}\n")
        
        # Add insertion summary
        report.append(f"### Insertion Summary\n")
        report.append(f"Total insertions: {len(insertions)}\n")
        homozygous = sum(1 for ins in insertions if ins['Genotype'] == '1/1')
        heterozygous = sum(1 for ins in insertions if ins['Genotype'] == '0/1')
        report.append(f"Homozygous insertions: {homozygous}\n")
        report.append(f"Heterozygous insertions: {heterozygous}\n\n")
        
        # Add insertion details
        report.append(f"### Insertion Details and Functional Impact\n")
        report.append("| Position | Length | Genotype | Region | Impact Level | Key Impact Factors |\n")
        report.append("|----------|--------|----------|--------|--------------|-------------------|\n")
        
        for insertion in insertions:
            position = insertion['Position']
            length = insertion['Length']
            genotype = insertion['Genotype']
            sequence = insertion.get('Sequence', '')
            
            # Determine region type
            region_type = determine_region_type(position, gene)
            
            # Analyze sequence motifs
            motifs = analyze_sequence_motifs(sequence)
            
            # Assess functional impact
            impact_level, impact_details = assess_functional_impact(gene, region_type, motifs, genotype)
            
            # Create a summary of key impact factors
            key_factors = "; ".join([detail.split(":")[0] for detail in impact_details if ":" in detail])
            
            # Add to report
            report.append(f"| {position} | {length} | {genotype} | {region_type} | {impact_level} | {key_factors} |\n")
        
        # Add detailed impact assessment
        report.append(f"\n### Detailed Impact Assessment\n")
        
        for insertion in insertions:
            position = insertion['Position']
            genotype = insertion['Genotype']
            sequence = insertion.get('Sequence', '')
            
            region_type = determine_region_type(position, gene)
            motifs = analyze_sequence_motifs(sequence)
            impact_level, impact_details = assess_functional_impact(gene, region_type, motifs, genotype)
            
            report.append(f"#### Insertion at position {position} (Genotype: {genotype})\n")
            report.append(f"**Impact Level**: {impact_level}\n")
            report.append("**Impact Details**:\n")
            
            for detail in impact_details:
                report.append(f"- {detail}\n")
            
            report.append("\n")
    
    # Add overall assessment
    report.append("## Overall Assessment and Implications\n")
    report.append("The analysis of genomic insertions in SHANK2, SHANK3, CNTN4, and PTPRN2 reveals several potential functional impacts:\n\n")
    
    report.append("1. **Synaptic Function**: Insertions in SHANK2 and SHANK3 may affect the organization and function of excitatory synapses, potentially impacting synaptic transmission and plasticity.\n")
    report.append("2. **Neural Circuit Development**: Insertions in CNTN4 may affect axon guidance and neural circuit formation, potentially impacting brain connectivity and function.\n")
    report.append("3. **Metabolic and Neurological Processes**: Insertions in PTPRN2 may affect both insulin secretion and neurological function, potentially leading to metabolic and neurological phenotypes.\n")
    report.append("4. **Cumulative Effects**: Multiple insertions in genes like CNTN4 and PTPRN2 may have cumulative effects on gene function, potentially leading to more pronounced phenotypes.\n\n")
    
    report.append("These findings highlight the potential impact of genomic insertions on neurological development and function, and suggest possible mechanisms by which these insertions may contribute to neurodevelopmental disorders.\n")
    
    # Add limitations and future directions
    report.append("## Limitations and Future Directions\n")
    report.append("This analysis has several limitations that should be considered:\n\n")
    
    report.append("1. **Region Annotation**: The determination of insertion regions is based on simplified genomic coordinates and may not accurately reflect the true genomic context.\n")
    report.append("2. **Functional Validation**: Computational predictions of functional impact require experimental validation to confirm their biological relevance.\n")
    report.append("3. **Incomplete Information**: The analysis is based on limited information about the insertions and may not capture all potential functional impacts.\n\n")
    
    report.append("Future studies should address these limitations by:\n\n")
    
    report.append("1. **Improved Annotation**: Using more detailed genomic annotation databases to accurately determine the functional regions affected by insertions.\n")
    report.append("2. **Experimental Validation**: Conducting functional assays to validate the predicted impacts of insertions on gene function.\n")
    report.append("3. **Integration with Other Data**: Integrating insertion data with other genomic, transcriptomic, and proteomic data to provide a more comprehensive understanding of their functional impacts.\n")
    
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
    
    print(f"Functional impact analysis report generated at {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
