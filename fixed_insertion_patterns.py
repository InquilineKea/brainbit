#!/usr/bin/env python3
"""
Fixed Insertion Pattern Analysis for Genome Structural Variants
This script provides a more comprehensive analysis of insertion sequences
for repetitive elements and potential functional impacts.
"""

import os
import re
import sys
from collections import Counter, defaultdict

# File paths
INSERTION_FILE = "/Users/simfish/Downloads/Genome/sv_analysis/insertion_sequences.tsv"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
PATTERN_REPORT = os.path.join(OUTPUT_DIR, "fixed_insertion_patterns.md")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define improved patterns for repetitive elements
REPEAT_PATTERNS = {
    # Alu elements - more comprehensive signature patterns
    'Alu': r'GGCCGGGCGC|GCCTGTAATC|TGGGAGGC|GAGACGGAGT|GAGACAGAGT|GGAGGAT|GAGGCAGG',
    
    # LINE elements - more comprehensive patterns
    'LINE': r'GGAGGA.{1,5}GGAGGA|TAACCC.{1,5}TAACCC|GGGAGG.{1,5}GGGAGG|GGGTCA|GAAATGCC|AGATCAGG',
    
    # SINE elements - more comprehensive patterns including Alu-derived SINEs
    'SINE': r'AAAAAA.{0,5}AAAAAA|TTTTTT.{0,5}TTTTTT|CCCCCC.{0,5}CCCCCC|GGGGGG.{0,5}GGGGGG|AATAAA|TTTTCT|CTTTTT',
    
    # Simple Repeats - expanded to include more types
    'Simple Repeats': r'(TG){3,}|(CA){3,}|(GA){3,}|(TC){3,}|(CT){3,}|(AG){3,}|(AAT){3,}|(ATT){3,}|(TAA){3,}|(TTA){3,}|(CAG){3,}|(CTG){3,}|(GAA){3,}|(TTC){3,}|(ACA){3,}|(GTG){3,}',
    
    # Microsatellites - expanded to include di- and tri-nucleotide repeats
    'Microsatellites': r'(A){8,}|(T){8,}|(G){8,}|(C){8,}|(AT){4,}|(TA){4,}|(GC){4,}|(CG){4,}|(CA){4,}|(TG){4,}|(GA){4,}|(TC){4,}|(AAT){3,}|(ATT){3,}|(TAA){3,}|(TTA){3,}|(CAG){3,}|(CTG){3,}',
    
    # Minisatellites - looking for longer repeating units
    'Minisatellites': r'(.{6,50})\1{2,}'
}

# Define potential functional elements with improved patterns
FUNCTIONAL_PATTERNS = {
    'Promoter Elements': r'TATA.{1,5}A|CCAAT|GGGCGG|CACCC|GGGCGG',
    'Splice Sites': r'GT.{10,80}AG|AG.{10,80}GT',
    'Poly-A Signals': r'AATAAA|ATTAAA',
    'Transcription Factor Binding': r'GATA.{1,3}|CAAT.{1,3}|CACCC|TGACGT|TGASTCA|CCGCCC'
}

def load_insertion_data(max_sequences=None):
    """
    Load insertion data from the TSV file
    Include truncated sequences in the analysis
    """
    if not os.path.exists(INSERTION_FILE):
        print(f"Error: {INSERTION_FILE} not found.")
        sys.exit(1)
        
    insertions = []
    truncated_count = 0
    complete_count = 0
    
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
            
            # Skip entries with completely unknown sequence
            if sequence == "unknown":
                continue
            
            # Process truncated sequences by removing ellipsis
            is_truncated = False
            if "..." in sequence:
                is_truncated = True
                sequence = sequence.replace("...", "")
                truncated_count += 1
            else:
                complete_count += 1
            
            insertions.append({
                'chromosome': chrom,
                'position': pos,
                'length': length,
                'sequence': sequence,
                'quality': quality,
                'genotype': genotype,
                'filter': filter_status,
                'is_truncated': is_truncated
            })
            
            if max_sequences and len(insertions) >= max_sequences:
                break
    
    print(f"Loaded {len(insertions)} insertions ({complete_count} complete, {truncated_count} truncated)")
    return insertions

def identify_repeat_patterns(insertions):
    """
    Identify common repeat patterns in insertion sequences
    """
    pattern_counts = {pattern: 0 for pattern in REPEAT_PATTERNS}
    sequences_with_pattern = {pattern: [] for pattern in REPEAT_PATTERNS}
    
    for ins in insertions:
        sequence = ins['sequence']
        for pattern_name, pattern in REPEAT_PATTERNS.items():
            if re.search(pattern, sequence, re.IGNORECASE):  # Make case-insensitive
                pattern_counts[pattern_name] += 1
                sequences_with_pattern[pattern_name].append({
                    'chromosome': ins['chromosome'],
                    'position': ins['position'],
                    'length': ins['length'],
                    'sequence': sequence,
                    'is_truncated': ins['is_truncated']
                })
    
    return pattern_counts, sequences_with_pattern

def identify_functional_elements(insertions):
    """
    Identify potential functional elements in insertion sequences
    """
    element_counts = {element: 0 for element in FUNCTIONAL_PATTERNS}
    sequences_with_element = {element: [] for element in FUNCTIONAL_PATTERNS}
    
    for ins in insertions:
        sequence = ins['sequence']
        for element_name, pattern in FUNCTIONAL_PATTERNS.items():
            if re.search(pattern, sequence, re.IGNORECASE):  # Make case-insensitive
                element_counts[element_name] += 1
                sequences_with_element[element_name].append({
                    'chromosome': ins['chromosome'],
                    'position': ins['position'],
                    'length': ins['length'],
                    'sequence': sequence,
                    'is_truncated': ins['is_truncated']
                })
    
    return element_counts, sequences_with_element

def analyze_chromosome_distribution(pattern_sequences, element_sequences):
    """
    Analyze distribution of insertion patterns across chromosomes
    """
    chrom_patterns = defaultdict(lambda: defaultdict(int))
    chrom_elements = defaultdict(lambda: defaultdict(int))
    
    # Process repeat patterns
    for pattern_name, sequences in pattern_sequences.items():
        for seq in sequences:
            chrom = seq['chromosome']
            chrom_patterns[chrom][pattern_name] += 1
    
    # Process functional elements
    for element_name, sequences in element_sequences.items():
        for seq in sequences:
            chrom = seq['chromosome']
            chrom_elements[chrom][element_name] += 1
    
    return chrom_patterns, chrom_elements

def generate_report(insertions, pattern_counts, element_counts, 
                   pattern_sequences, element_sequences, 
                   chrom_patterns, chrom_elements):
    """
    Generate a comprehensive report of the insertion pattern analysis
    """
    with open(PATTERN_REPORT, 'w') as f:
        f.write("# Improved Insertion Pattern Analysis\n\n")
        
        # Overview
        total_insertions = len(insertions)
        truncated_insertions = sum(1 for ins in insertions if ins['is_truncated'])
        complete_insertions = total_insertions - truncated_insertions
        
        f.write("## Overview\n\n")
        f.write(f"Total insertions analyzed: {total_insertions}\n")
        f.write(f"Complete sequences: {complete_insertions}\n")
        f.write(f"Truncated sequences: {truncated_insertions}\n\n")
        
        # Repetitive Element Analysis
        f.write("## Repetitive Element Analysis\n\n")
        f.write("| Repeat Type | Count | Percentage |\n")
        f.write("|-------------|-------|------------|\n")
        for pattern, count in pattern_counts.items():
            percentage = (count / total_insertions) * 100 if total_insertions > 0 else 0
            f.write(f"| {pattern} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        # Potential Functional Elements
        f.write("## Potential Functional Elements\n\n")
        f.write("| Element Type | Count | Percentage |\n")
        f.write("|--------------|-------|------------|\n")
        for element, count in element_counts.items():
            percentage = (count / total_insertions) * 100 if total_insertions > 0 else 0
            f.write(f"| {element} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        # Chromosome Distribution
        f.write("## Chromosome Distribution of Repetitive Elements\n\n")
        f.write("| Chromosome | " + " | ".join(REPEAT_PATTERNS.keys()) + " |\n")
        f.write("|------------|-" + "-|-".join(["-----" for _ in REPEAT_PATTERNS]) + "-|\n")
        
        # Sort chromosomes naturally
        def chrom_key(chrom):
            if chrom.startswith('chr'):
                chrom = chrom[3:]
            if chrom.isdigit():
                return int(chrom)
            return float('inf')  # Put non-numeric at the end
        
        for chrom in sorted(chrom_patterns.keys(), key=chrom_key):
            patterns = chrom_patterns[chrom]
            f.write(f"| {chrom} | " + " | ".join([str(patterns[pattern]) for pattern in REPEAT_PATTERNS]) + " |\n")
        f.write("\n")
        
        # Examples of insertions with repetitive elements
        f.write("## Examples of Insertions with Repetitive Elements\n\n")
        for pattern, sequences in pattern_sequences.items():
            if sequences:
                f.write(f"### {pattern} Examples\n\n")
                for i, seq in enumerate(sequences[:3]):  # Show up to 3 examples
                    f.write(f"**Example {i+1}**: {seq['chromosome']}:{seq['position']} (Length: {seq['length']})\n")
                    
                    # Truncate very long sequences for readability
                    sequence = seq['sequence']
                    if len(sequence) > 100:
                        display_seq = sequence[:97] + "..."
                    else:
                        display_seq = sequence
                    
                    f.write(f"```\n{display_seq}\n```\n")
                    f.write(f"*{'Truncated sequence' if seq['is_truncated'] else 'Complete sequence'}*\n\n")
        
        # Examples of insertions with functional elements
        f.write("## Examples of Insertions with Functional Elements\n\n")
        for element, sequences in element_sequences.items():
            if sequences:
                f.write(f"### {element} Examples\n\n")
                for i, seq in enumerate(sequences[:3]):  # Show up to 3 examples
                    f.write(f"**Example {i+1}**: {seq['chromosome']}:{seq['position']} (Length: {seq['length']})\n")
                    
                    # Truncate very long sequences for readability
                    sequence = seq['sequence']
                    if len(sequence) > 100:
                        display_seq = sequence[:97] + "..."
                    else:
                        display_seq = sequence
                    
                    f.write(f"```\n{display_seq}\n```\n")
                    f.write(f"*{'Truncated sequence' if seq['is_truncated'] else 'Complete sequence'}*\n\n")
        
        # Conclusion and next steps
        f.write("## Conclusion\n\n")
        f.write("This analysis has identified a variety of repetitive elements and potential functional elements in the insertion sequences. ")
        f.write("The most common repetitive elements are " + ", ".join([pattern for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:3]]) + ". ")
        f.write("The most common functional elements are " + ", ".join([element for element, count in sorted(element_counts.items(), key=lambda x: x[1], reverse=True)[:3]]) + ".\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Compare the distribution of repetitive elements with population databases\n")
        f.write("2. Analyze the genomic context of insertions containing specific repetitive elements\n")
        f.write("3. Investigate whether any repetitive element insertions are associated with genes or regulatory regions\n")
        f.write("4. Consider more detailed analysis of specific repetitive element families of interest\n")
    
    print(f"Report generated: {PATTERN_REPORT}")

def main():
    print("Starting improved insertion pattern analysis...")
    
    # Load insertion data - analyze all available data
    insertions = load_insertion_data()
    
    if not insertions:
        print("No insertion data found. Exiting.")
        return
    
    # Identify repetitive elements
    print("Identifying repetitive elements...")
    pattern_counts, pattern_sequences = identify_repeat_patterns(insertions)
    
    # Identify functional elements
    print("Identifying potential functional elements...")
    element_counts, element_sequences = identify_functional_elements(insertions)
    
    # Analyze chromosome distribution
    print("Analyzing chromosome distribution...")
    chrom_patterns, chrom_elements = analyze_chromosome_distribution(pattern_sequences, element_sequences)
    
    # Generate report
    print("Generating comprehensive report...")
    generate_report(insertions, pattern_counts, element_counts, 
                   pattern_sequences, element_sequences,
                   chrom_patterns, chrom_elements)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
