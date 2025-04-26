#!/usr/bin/env python3
"""
Analyze Structural Variant Insertions in Genome Data
This script provides detailed analysis of insertion variants from VCF files,
including sequence content analysis, motif detection, and potential functional impact.
"""

import os
import re
import sys
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import seaborn as sns
from Bio import SeqIO, Seq
from Bio.SeqUtils import GC

# File paths
SV_FILE = "/Users/simfish/Downloads/Genome/010625-WGS-C3156486.sv.uncompressed.vcf"
SV_INSERTIONS_FILE = "/Users/simfish/Downloads/Genome/sv_insertions.txt"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_insertion_sequences():
    """
    Extract insertion sequences directly from the VCF file
    Returns a dictionary of position -> sequence
    """
    insertions = {}
    
    with open(SV_FILE, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
                
            fields = line.strip().split('\t')
            info = fields[7]
            
            # Only process insertion variants
            if "SVTYPE=INS" not in info:
                continue
                
            chrom = fields[0]
            pos = int(fields[1])
            key = f"{chrom}:{pos}"
            
            # Extract insertion sequences
            left_seq_match = re.search(r'LEFT_SVINSSEQ=([^;]+)', info)
            right_seq_match = re.search(r'RIGHT_SVINSSEQ=([^;]+)', info)
            
            left_seq = left_seq_match.group(1) if left_seq_match else ""
            right_seq = right_seq_match.group(1) if right_seq_match else ""
            
            if left_seq or right_seq:
                insertions[key] = left_seq + right_seq
    
    return insertions

def load_insertion_data():
    """
    Load insertion data from the processed file
    """
    if not os.path.exists(SV_INSERTIONS_FILE):
        print(f"Error: {SV_INSERTIONS_FILE} not found. Run sv_analysis.sh first.")
        sys.exit(1)
        
    insertions = []
    
    with open(SV_INSERTIONS_FILE, 'r') as f:
        # Skip header lines
        next(f)
        next(f)
        
        for line in f:
            if not line.strip():
                continue
                
            fields = line.strip().split('\t')
            if len(fields) < 7:
                continue
                
            chrom = fields[0]
            pos = int(fields[1])
            length = fields[2] if fields[2] != "unknown" else None
            if length and length.isdigit():
                length = int(length)
            sequence = fields[3] if fields[3] != "unknown" else None
            quality = float(fields[4])
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
    
    return pd.DataFrame(insertions)

def get_full_sequences(df, seq_dict):
    """
    Add full sequences to the dataframe where available
    """
    full_seqs = []
    
    for _, row in df.iterrows():
        key = f"{row['chromosome']}:{row['position']}"
        if key in seq_dict:
            full_seqs.append(seq_dict[key])
        else:
            full_seqs.append(None)
    
    df['full_sequence'] = full_seqs
    # Use full sequence where available, otherwise use the truncated one
    df['best_sequence'] = df.apply(lambda x: x['full_sequence'] if x['full_sequence'] else x['sequence'], axis=1)
    return df

def analyze_sequences(df):
    """
    Analyze sequence content of insertions
    """
    # Filter to rows with sequence data
    seq_df = df[df['best_sequence'].notna() & (df['best_sequence'] != 'unknown')]
    
    if len(seq_df) == 0:
        print("No sequence data available for analysis")
        return
    
    # Calculate GC content for each sequence
    gc_contents = []
    sequence_lengths = []
    
    for seq in seq_df['best_sequence']:
        # Remove ellipsis if present (from truncated sequences)
        clean_seq = seq.replace('...', '')
        if clean_seq:
            gc_contents.append(GC(clean_seq))
            sequence_lengths.append(len(clean_seq))
    
    # Add to dataframe
    seq_df = seq_df.copy()
    seq_df['gc_content'] = gc_contents
    seq_df['seq_length'] = sequence_lengths
    
    # Analyze common motifs
    motifs = []
    for seq in seq_df['best_sequence']:
        clean_seq = seq.replace('...', '')
        # Look for common repeat motifs (2-6 bases)
        for i in range(2, 7):
            for j in range(len(clean_seq) - i + 1):
                motif = clean_seq[j:j+i]
                if clean_seq.count(motif) > 1:
                    motifs.append(motif)
    
    # Count motif occurrences
    motif_counts = Counter(motifs)
    common_motifs = motif_counts.most_common(10)
    
    # Create output directory for plots
    plots_dir = os.path.join(OUTPUT_DIR, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # Plot GC content distribution
    plt.figure(figsize=(10, 6))
    sns.histplot(gc_contents, bins=20, kde=True)
    plt.title('GC Content Distribution in Insertion Sequences')
    plt.xlabel('GC Content (%)')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(plots_dir, 'gc_content_distribution.png'))
    
    # Plot sequence length distribution
    plt.figure(figsize=(10, 6))
    sns.histplot(sequence_lengths, bins=20, kde=True)
    plt.title('Length Distribution of Insertion Sequences')
    plt.xlabel('Sequence Length (bp)')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(plots_dir, 'length_distribution.png'))
    
    # Plot most common motifs
    plt.figure(figsize=(12, 6))
    motif_df = pd.DataFrame(common_motifs, columns=['Motif', 'Count'])
    sns.barplot(x='Motif', y='Count', data=motif_df)
    plt.title('Most Common Sequence Motifs in Insertions')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'common_motifs.png'))
    
    # Return the analysis results
    return {
        'sequence_df': seq_df,
        'gc_content_mean': sum(gc_contents) / len(gc_contents) if gc_contents else 0,
        'gc_content_range': (min(gc_contents), max(gc_contents)) if gc_contents else (0, 0),
        'length_mean': sum(sequence_lengths) / len(sequence_lengths) if sequence_lengths else 0,
        'length_range': (min(sequence_lengths), max(sequence_lengths)) if sequence_lengths else (0, 0),
        'common_motifs': common_motifs
    }

def analyze_insertion_distribution(df):
    """
    Analyze the distribution of insertions across chromosomes
    """
    # Count insertions per chromosome
    chrom_counts = df['chromosome'].value_counts().sort_index()
    
    # Plot chromosome distribution
    plt.figure(figsize=(14, 8))
    sns.barplot(x=chrom_counts.index, y=chrom_counts.values)
    plt.title('Distribution of Insertions Across Chromosomes')
    plt.xlabel('Chromosome')
    plt.ylabel('Number of Insertions')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'plots', 'chromosome_distribution.png'))
    
    # Analyze insertion density
    # Create bins for each chromosome (e.g., 10 Mbp bins)
    bin_size = 10_000_000  # 10 Mbp
    bins = {}
    
    for _, row in df.iterrows():
        chrom = row['chromosome']
        pos = row['position']
        bin_idx = pos // bin_size
        bin_key = f"{chrom}:{bin_idx}"
        
        if bin_key not in bins:
            bins[bin_key] = 0
        bins[bin_key] += 1
    
    # Find hotspots (bins with high insertion counts)
    hotspots = sorted([(k, v) for k, v in bins.items()], key=lambda x: x[1], reverse=True)[:10]
    
    return {
        'chromosome_counts': chrom_counts,
        'insertion_hotspots': hotspots
    }

def analyze_genotypes(df):
    """
    Analyze genotype distribution of insertions
    """
    genotype_counts = df['genotype'].value_counts()
    
    # Plot genotype distribution
    plt.figure(figsize=(8, 6))
    sns.barplot(x=genotype_counts.index, y=genotype_counts.values)
    plt.title('Genotype Distribution of Insertions')
    plt.xlabel('Genotype')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'plots', 'genotype_distribution.png'))
    
    return genotype_counts

def generate_report(df, seq_analysis, dist_analysis, genotype_analysis):
    """
    Generate a comprehensive report of the insertion analysis
    """
    report_path = os.path.join(OUTPUT_DIR, 'insertion_analysis_report.md')
    
    with open(report_path, 'w') as f:
        f.write("# Structural Variant Insertion Analysis Report\n\n")
        f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Total insertions analyzed: {len(df)}\n")
        f.write(f"Insertions with sequence data: {len(df[df['best_sequence'].notna() & (df['best_sequence'] != 'unknown')])}\n")
        f.write(f"Insertions with known length: {len(df[df['length'].notna()])}\n\n")
        
        f.write("## Sequence Content Analysis\n\n")
        if seq_analysis:
            f.write(f"Average GC content: {seq_analysis['gc_content_mean']:.2f}%\n")
            f.write(f"GC content range: {seq_analysis['gc_content_range'][0]:.2f}% - {seq_analysis['gc_content_range'][1]:.2f}%\n")
            f.write(f"Average sequence length: {seq_analysis['length_mean']:.2f} bp\n")
            f.write(f"Sequence length range: {seq_analysis['length_range'][0]} - {seq_analysis['length_range'][1]} bp\n\n")
            
            f.write("### Most Common Sequence Motifs\n\n")
            f.write("| Motif | Count |\n")
            f.write("|-------|-------|\n")
            for motif, count in seq_analysis['common_motifs']:
                f.write(f"| {motif} | {count} |\n")
            f.write("\n")
        else:
            f.write("No sequence data available for analysis.\n\n")
        
        f.write("## Insertion Distribution\n\n")
        f.write("### Chromosome Distribution\n\n")
        f.write("| Chromosome | Insertion Count |\n")
        f.write("|------------|----------------|\n")
        for chrom, count in dist_analysis['chromosome_counts'].items():
            f.write(f"| {chrom} | {count} |\n")
        f.write("\n")
        
        f.write("### Insertion Hotspots (10 Mbp bins)\n\n")
        f.write("| Region | Count |\n")
        f.write("|--------|-------|\n")
        for region, count in dist_analysis['insertion_hotspots']:
            chrom, bin_idx = region.split(':')
            start = int(bin_idx) * 10_000_000
            end = start + 10_000_000
            f.write(f"| {chrom}:{start:,}-{end:,} | {count} |\n")
        f.write("\n")
        
        f.write("## Genotype Analysis\n\n")
        f.write("| Genotype | Count |\n")
        f.write("|----------|-------|\n")
        for genotype, count in genotype_analysis.items():
            f.write(f"| {genotype} | {count} |\n")
        f.write("\n")
        
        f.write("## Potential Functional Impact\n\n")
        f.write("To determine the functional impact of these insertions, further analysis is needed:\n\n")
        f.write("1. Annotation with gene coordinates to identify insertions within or near genes\n")
        f.write("2. Analysis of insertion content for potential regulatory elements\n")
        f.write("3. Comparison with known disease-associated variants\n")
        f.write("4. Evaluation of evolutionary conservation at insertion sites\n\n")
        
        f.write("## Visualization\n\n")
        f.write("Plots have been generated in the 'plots' directory:\n\n")
        f.write("- GC content distribution\n")
        f.write("- Sequence length distribution\n")
        f.write("- Common sequence motifs\n")
        f.write("- Chromosome distribution\n")
        f.write("- Genotype distribution\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Integrate with gene annotation data to identify potentially functional variants\n")
        f.write("2. Perform comparative analysis with population databases\n")
        f.write("3. Validate selected insertions with alternative methods\n")
        f.write("4. Investigate potential phenotypic associations\n")
    
    print(f"Report generated: {report_path}")
    return report_path

def main():
    print("Extracting insertion sequences from VCF file...")
    seq_dict = extract_insertion_sequences()
    print(f"Found {len(seq_dict)} insertion sequences")
    
    print("Loading insertion data from processed file...")
    df = load_insertion_data()
    print(f"Loaded {len(df)} insertion variants")
    
    print("Adding full sequences to dataframe...")
    df = get_full_sequences(df, seq_dict)
    
    print("Analyzing sequence content...")
    seq_analysis = analyze_sequences(df)
    
    print("Analyzing insertion distribution...")
    dist_analysis = analyze_insertion_distribution(df)
    
    print("Analyzing genotype distribution...")
    genotype_analysis = analyze_genotypes(df)
    
    print("Generating comprehensive report...")
    report_path = generate_report(df, seq_analysis, dist_analysis, genotype_analysis)
    
    print("Analysis complete!")
    print(f"Results saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
