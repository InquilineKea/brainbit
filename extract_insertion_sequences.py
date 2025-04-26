#!/usr/bin/env python3
"""
Extract and analyze insertion sequences from structural variant VCF file.
This script directly processes the VCF file to extract insertion sequences
and provides basic analysis without requiring complex dependencies.
"""

import os
import re
import sys
from collections import Counter

# File paths
SV_FILE = "/Users/simfish/Downloads/Genome/010625-WGS-C3156486.sv.uncompressed.vcf"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "insertion_sequences.tsv")
REPORT_FILE = os.path.join(OUTPUT_DIR, "insertion_analysis.md")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_insertion_sequences():
    """
    Extract insertion sequences directly from the VCF file
    Returns a list of dictionaries with insertion data
    """
    insertions = []
    
    print(f"Processing VCF file: {SV_FILE}")
    with open(SV_FILE, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
                
            fields = line.strip().split('\t')
            if len(fields) < 8:
                continue
                
            info = fields[7]
            
            # Only process insertion variants
            if "SVTYPE=INS" not in info:
                continue
                
            chrom = fields[0]
            pos = int(fields[1])
            qual = fields[5]
            filter_status = fields[6]
            genotype = fields[9].split(':')[0] if len(fields) > 9 else "unknown"
            
            # Extract insertion sequences
            left_seq_match = re.search(r'LEFT_SVINSSEQ=([^;]+)', info)
            right_seq_match = re.search(r'RIGHT_SVINSSEQ=([^;]+)', info)
            
            left_seq = left_seq_match.group(1) if left_seq_match else ""
            right_seq = right_seq_match.group(1) if right_seq_match else ""
            
            # Extract length if available
            svlen_match = re.search(r'SVLEN=(\d+)', info)
            length = svlen_match.group(1) if svlen_match else None
            
            if not length and (left_seq or right_seq):
                length = len(left_seq) + len(right_seq)
            
            # Only include variants with sequence data
            if left_seq or right_seq:
                insertions.append({
                    'chromosome': chrom,
                    'position': pos,
                    'length': length,
                    'left_sequence': left_seq,
                    'right_sequence': right_seq,
                    'full_sequence': left_seq + right_seq,
                    'quality': qual,
                    'genotype': genotype,
                    'filter': filter_status
                })
    
    print(f"Found {len(insertions)} insertions with sequence data")
    return insertions

def calculate_gc_content(sequence):
    """Calculate GC content of a DNA sequence"""
    if not sequence:
        return 0
    
    gc_count = sequence.count('G') + sequence.count('C')
    return (gc_count / len(sequence)) * 100

def find_common_motifs(sequences, min_length=2, max_length=6, top_n=10):
    """Find common motifs in a list of sequences"""
    all_motifs = []
    
    for seq in sequences:
        # Look for repeat motifs of length min_length to max_length
        for motif_len in range(min_length, max_length + 1):
            for i in range(len(seq) - motif_len + 1):
                motif = seq[i:i+motif_len]
                if seq.count(motif) > 1:  # Only include repeated motifs
                    all_motifs.append(motif)
    
    # Count occurrences of each motif
    motif_counts = Counter(all_motifs)
    
    # Return top N most common motifs
    return motif_counts.most_common(top_n)

def analyze_insertions(insertions):
    """Perform basic analysis on insertion data"""
    # Extract sequences for analysis
    sequences = [ins['full_sequence'] for ins in insertions if ins['full_sequence']]
    
    # Calculate basic statistics
    lengths = [len(seq) for seq in sequences]
    gc_contents = [calculate_gc_content(seq) for seq in sequences]
    
    # Find common motifs
    common_motifs = find_common_motifs(sequences)
    
    # Count insertions per chromosome
    chrom_counts = {}
    for ins in insertions:
        chrom = ins['chromosome']
        if chrom not in chrom_counts:
            chrom_counts[chrom] = 0
        chrom_counts[chrom] += 1
    
    # Count genotypes
    genotype_counts = {}
    for ins in insertions:
        gt = ins['genotype']
        if gt not in genotype_counts:
            genotype_counts[gt] = 0
        genotype_counts[gt] += 1
    
    # Return analysis results
    return {
        'total_insertions': len(insertions),
        'with_sequence': len(sequences),
        'length_stats': {
            'min': min(lengths) if lengths else 0,
            'max': max(lengths) if lengths else 0,
            'avg': sum(lengths) / len(lengths) if lengths else 0
        },
        'gc_stats': {
            'min': min(gc_contents) if gc_contents else 0,
            'max': max(gc_contents) if gc_contents else 0,
            'avg': sum(gc_contents) / len(gc_contents) if gc_contents else 0
        },
        'common_motifs': common_motifs,
        'chromosome_counts': chrom_counts,
        'genotype_counts': genotype_counts
    }

def write_sequences_to_file(insertions, output_file):
    """Write extracted sequences to a TSV file"""
    with open(output_file, 'w') as f:
        # Write header
        f.write("Chromosome\tPosition\tLength\tSequence\tQuality\tGenotype\tFilter\n")
        
        # Write data
        for ins in insertions:
            sequence = ins['full_sequence']
            # Truncate very long sequences for readability
            if len(sequence) > 50:
                sequence = sequence[:47] + "..."
            
            f.write(f"{ins['chromosome']}\t{ins['position']}\t{ins['length']}\t{sequence}\t{ins['quality']}\t{ins['genotype']}\t{ins['filter']}\n")
    
    print(f"Sequences written to {output_file}")

def generate_report(analysis, report_file):
    """Generate a markdown report of the analysis"""
    with open(report_file, 'w') as f:
        f.write("# Structural Variant Insertion Analysis\n\n")
        f.write(f"Analysis Date: {os.popen('date').read().strip()}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Total insertions analyzed: {analysis['total_insertions']}\n")
        f.write(f"Insertions with sequence data: {analysis['with_sequence']}\n\n")
        
        f.write("## Sequence Analysis\n\n")
        f.write("### Length Statistics\n\n")
        f.write(f"- Minimum length: {analysis['length_stats']['min']} bp\n")
        f.write(f"- Maximum length: {analysis['length_stats']['max']} bp\n")
        f.write(f"- Average length: {analysis['length_stats']['avg']:.2f} bp\n\n")
        
        f.write("### GC Content\n\n")
        f.write(f"- Minimum GC content: {analysis['gc_stats']['min']:.2f}%\n")
        f.write(f"- Maximum GC content: {analysis['gc_stats']['max']:.2f}%\n")
        f.write(f"- Average GC content: {analysis['gc_stats']['avg']:.2f}%\n\n")
        
        f.write("### Most Common Sequence Motifs\n\n")
        f.write("| Motif | Count |\n")
        f.write("|-------|-------|\n")
        for motif, count in analysis['common_motifs']:
            f.write(f"| {motif} | {count} |\n")
        f.write("\n")
        
        f.write("## Distribution Analysis\n\n")
        f.write("### Chromosome Distribution\n\n")
        f.write("| Chromosome | Count |\n")
        f.write("|------------|-------|\n")
        for chrom in sorted(analysis['chromosome_counts'].keys()):
            f.write(f"| {chrom} | {analysis['chromosome_counts'][chrom]} |\n")
        f.write("\n")
        
        f.write("### Genotype Distribution\n\n")
        f.write("| Genotype | Count |\n")
        f.write("|----------|-------|\n")
        for gt, count in analysis['genotype_counts'].items():
            f.write(f"| {gt} | {count} |\n")
        f.write("\n")
        
        f.write("## Potential Functional Impact\n\n")
        f.write("To determine the functional impact of these insertions, further analysis is needed:\n\n")
        f.write("1. Annotation with gene coordinates to identify insertions within or near genes\n")
        f.write("2. Analysis of insertion content for potential regulatory elements\n")
        f.write("3. Comparison with known disease-associated variants\n")
        f.write("4. Evaluation of evolutionary conservation at insertion sites\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Integrate with gene annotation data to identify potentially functional variants\n")
        f.write("2. Perform comparative analysis with population databases\n")
        f.write("3. Validate selected insertions with alternative methods\n")
        f.write("4. Investigate potential phenotypic associations\n")
    
    print(f"Analysis report written to {report_file}")

def main():
    print("Starting insertion sequence extraction and analysis...")
    
    # Extract insertion sequences
    insertions = extract_insertion_sequences()
    
    if not insertions:
        print("No insertion sequences found. Exiting.")
        return
    
    # Write sequences to file
    write_sequences_to_file(insertions, OUTPUT_FILE)
    
    # Analyze insertions
    print("Analyzing insertion sequences...")
    analysis = analyze_insertions(insertions)
    
    # Generate report
    generate_report(analysis, REPORT_FILE)
    
    print("Analysis complete!")
    print(f"Results saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
