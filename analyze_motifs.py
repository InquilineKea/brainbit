#!/usr/bin/env python3
"""
Analyze Common Sequence Motifs in Genome Structural Variant Insertions
This script extracts and analyzes common sequence motifs from insertion sequences.
"""

import os
import re
import sys
from collections import Counter

# File paths
INSERTION_FILE = "/Users/simfish/Downloads/Genome/sv_analysis/insertion_sequences.tsv"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
MOTIFS_REPORT = os.path.join(OUTPUT_DIR, "common_motifs.md")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_sequences():
    """
    Load insertion sequences from the TSV file
    """
    if not os.path.exists(INSERTION_FILE):
        print(f"Error: {INSERTION_FILE} not found.")
        sys.exit(1)
        
    sequences = []
    
    with open(INSERTION_FILE, 'r') as f:
        # Skip header line
        next(f)
        
        for line in f:
            if not line.strip():
                continue
                
            fields = line.strip().split('\t')
            if len(fields) < 4:
                continue
                
            sequence = fields[3]
            
            # Skip entries with unknown sequence or truncated sequences
            if sequence == "unknown" or "..." in sequence:
                continue
            
            sequences.append(sequence)
    
    print(f"Loaded {len(sequences)} complete insertion sequences")
    return sequences

def find_common_motifs(sequences, motif_length=2):
    """
    Find common motifs of specified length in a list of sequences
    """
    motifs = []
    
    for seq in sequences:
        for i in range(len(seq) - motif_length + 1):
            motif = seq[i:i+motif_length]
            motifs.append(motif)
    
    # Count occurrences of each motif
    motif_counts = Counter(motifs)
    
    # Return top 20 most common motifs
    return motif_counts.most_common(20)

def find_longer_motifs(sequences, min_length=3, max_length=6):
    """
    Find common longer motifs in sequences
    """
    all_motifs = {}
    
    for length in range(min_length, max_length + 1):
        motifs = []
        for seq in sequences:
            for i in range(len(seq) - length + 1):
                motif = seq[i:i+length]
                motifs.append(motif)
        
        # Count occurrences of each motif
        motif_counts = Counter(motifs)
        
        # Get top motifs for this length
        all_motifs[length] = motif_counts.most_common(10)
    
    return all_motifs

def find_repeats(sequences):
    """
    Find sequences with repeating patterns
    """
    repeat_types = {
        'Dinucleotide Repeats': r'(TG|CA|GA|TC|CT|AG|AT|TA|GC|CG){5,}',
        'Trinucleotide Repeats': r'(CAG|CTG|GAA|TTC|AAT|ATT|TAA|TTA){4,}',
        'Homopolymers': r'(A){10,}|(T){10,}|(G){10,}|(C){10,}'
    }
    
    repeat_counts = {repeat: 0 for repeat in repeat_types}
    repeat_examples = {repeat: [] for repeat in repeat_types}
    
    for seq in sequences:
        for repeat_name, pattern in repeat_types.items():
            if re.search(pattern, seq):
                repeat_counts[repeat_name] += 1
                # Store up to 3 examples for each repeat type
                if len(repeat_examples[repeat_name]) < 3:
                    repeat_examples[repeat_name].append(seq)
    
    return repeat_counts, repeat_examples

def calculate_gc_content(sequences):
    """
    Calculate GC content distribution
    """
    gc_contents = []
    
    for seq in sequences:
        gc_count = seq.count('G') + seq.count('C')
        gc_content = (gc_count / len(seq)) * 100 if len(seq) > 0 else 0
        gc_contents.append(gc_content)
    
    # Calculate distribution
    gc_ranges = {
        '<30%': 0,
        '30-40%': 0,
        '40-50%': 0,
        '50-60%': 0,
        '60-70%': 0,
        '>70%': 0
    }
    
    for gc in gc_contents:
        if gc < 30:
            gc_ranges['<30%'] += 1
        elif gc < 40:
            gc_ranges['30-40%'] += 1
        elif gc < 50:
            gc_ranges['40-50%'] += 1
        elif gc < 60:
            gc_ranges['50-60%'] += 1
        elif gc < 70:
            gc_ranges['60-70%'] += 1
        else:
            gc_ranges['>70%'] += 1
    
    return gc_ranges

def generate_report(sequences, common_motifs, longer_motifs, repeat_counts, repeat_examples, gc_ranges):
    """
    Generate a report of the motif analysis
    """
    with open(MOTIFS_REPORT, 'w') as f:
        f.write("# Common Sequence Motifs in Structural Variant Insertions\n\n")
        f.write(f"Analysis Date: {os.popen('date').read().strip()}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Total sequences analyzed: {len(sequences)}\n\n")
        
        f.write("## Most Common Dinucleotide Motifs\n\n")
        f.write("| Motif | Count |\n")
        f.write("|-------|-------|\n")
        for motif, count in common_motifs:
            f.write(f"| {motif} | {count} |\n")
        f.write("\n")
        
        f.write("## Longer Common Motifs\n\n")
        for length, motifs in longer_motifs.items():
            f.write(f"### {length}-base Motifs\n\n")
            f.write("| Motif | Count |\n")
            f.write("|-------|-------|\n")
            for motif, count in motifs:
                f.write(f"| {motif} | {count} |\n")
            f.write("\n")
        
        f.write("## Repeat Patterns\n\n")
        f.write("| Repeat Type | Count | Percentage |\n")
        f.write("|-------------|-------|------------|\n")
        for repeat, count in repeat_counts.items():
            percentage = (count / len(sequences)) * 100
            f.write(f"| {repeat} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Examples of Repeat Patterns\n\n")
        for repeat, examples in repeat_examples.items():
            if examples:
                f.write(f"### {repeat} Examples\n\n")
                for i, example in enumerate(examples):
                    # Truncate very long sequences
                    if len(example) > 100:
                        display_seq = example[:97] + "..."
                    else:
                        display_seq = example
                    f.write(f"**Example {i+1}**:\n```\n{display_seq}\n```\n\n")
        
        f.write("## GC Content Distribution\n\n")
        f.write("| GC Content Range | Count | Percentage |\n")
        f.write("|------------------|-------|------------|\n")
        for gc_range, count in gc_ranges.items():
            percentage = (count / len(sequences)) * 100
            f.write(f"| {gc_range} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Biological Significance\n\n")
        f.write("The motifs and patterns identified in these insertion sequences may have biological significance:\n\n")
        f.write("1. **Dinucleotide repeats**: TG/CA repeats are often found in Z-DNA forming regions\n")
        f.write("2. **Trinucleotide repeats**: Some, like CAG repeats, are associated with various neurological disorders when expanded\n")
        f.write("3. **GC-rich regions**: May indicate CpG islands or other regulatory elements\n")
        f.write("4. **Homopolymers**: Long stretches of a single nucleotide can cause replication slippage\n\n")
        
        f.write("## Potential Impact on Genome Function\n\n")
        f.write("These insertions could impact genome function through several mechanisms:\n\n")
        f.write("1. Disruption of coding sequences\n")
        f.write("2. Alteration of regulatory elements\n")
        f.write("3. Creation of new splice sites\n")
        f.write("4. Introduction of unstable repeat sequences\n")
        f.write("5. Changes in local chromatin structure\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Compare identified motifs with known functional elements\n")
        f.write("2. Analyze the genomic context of insertions containing specific motifs\n")
        f.write("3. Investigate whether any motifs are enriched in specific chromosomal regions\n")
        f.write("4. Correlate motif patterns with insertion size and other properties\n")
    
    print(f"Report generated: {MOTIFS_REPORT}")

def main():
    print("Starting motif analysis of insertion sequences...")
    
    # Load sequences
    sequences = load_sequences()
    
    if not sequences:
        print("No sequences found. Exiting.")
        return
    
    # Find common dinucleotide motifs
    print("Finding common dinucleotide motifs...")
    common_motifs = find_common_motifs(sequences, 2)
    
    # Find longer motifs
    print("Finding longer common motifs...")
    longer_motifs = find_longer_motifs(sequences, 3, 6)
    
    # Find repeat patterns
    print("Identifying repeat patterns...")
    repeat_counts, repeat_examples = find_repeats(sequences)
    
    # Calculate GC content distribution
    print("Calculating GC content distribution...")
    gc_ranges = calculate_gc_content(sequences)
    
    # Generate report
    print("Generating comprehensive report...")
    generate_report(sequences, common_motifs, longer_motifs, repeat_counts, repeat_examples, gc_ranges)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
