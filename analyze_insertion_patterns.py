#!/usr/bin/env python3
"""
Analyze Insertion Patterns in Genome Structural Variants
This script analyzes insertion sequences for common patterns, repetitive elements,
and potential functional impacts.
"""

import os
import re
import sys
import math
from collections import Counter, defaultdict

# File paths
INSERTION_FILE = "/Users/simfish/Downloads/Genome/sv_analysis/insertion_sequences.tsv"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
PATTERN_REPORT = os.path.join(OUTPUT_DIR, "insertion_patterns.md")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define common repetitive elements to look for
REPEAT_PATTERNS = {
    'Alu': r'GGCCGGGCGC|GCCTGTAATC|TGGGAGGC',
    'LINE': r'GGAGGA.{1,5}GGAGGA|TAACCC.{1,5}TAACCC',
    'SINE': r'AAAAAA.{0,5}AAAAAA',
    'Simple Repeats': r'(TG){3,}|(CA){3,}|(GA){3,}|(TC){3,}|(CT){3,}|(AG){3,}|(AAT){3,}|(ATT){3,}',
    'Microsatellites': r'(A){10,}|(T){10,}|(G){10,}|(C){10,}',
    'Minisatellites': r'(.{10,50})\1{2,}'
}

# Define potential functional elements
FUNCTIONAL_PATTERNS = {
    'Promoter Elements': r'TATA.{1,5}A|CCAAT|GGGCGG',
    'Splice Sites': r'GT.{10,80}AG',
    'Poly-A Signals': r'AATAAA',
    'Transcription Factor Binding': r'GATA.{1,3}|CAAT.{1,3}|CACCC'
}

# Global variables for storing pattern matches
sequences_with_pattern = {}
sequences_with_element = {}

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
            
            # Skip entries with unknown sequence
            if sequence == "unknown" or "..." in sequence:
                continue
            
            insertions.append({
                'chromosome': chrom,
                'position': pos,
                'length': length,
                'sequence': sequence,
                'quality': quality,
                'genotype': genotype,
                'filter': filter_status
            })
    
    print(f"Loaded {len(insertions)} insertions with complete sequence data")
    return insertions

def identify_repeat_patterns(insertions):
    """
    Identify common repeat patterns in insertion sequences
    """
    global sequences_with_pattern
    pattern_counts = {pattern: 0 for pattern in REPEAT_PATTERNS}
    sequences_with_pattern = {pattern: [] for pattern in REPEAT_PATTERNS}
    
    for ins in insertions:
        sequence = ins['sequence']
        for pattern_name, pattern in REPEAT_PATTERNS.items():
            if re.search(pattern, sequence):
                pattern_counts[pattern_name] += 1
                sequences_with_pattern[pattern_name].append({
                    'chromosome': ins['chromosome'],
                    'position': ins['position'],
                    'length': ins['length'],
                    'sequence': sequence
                })
    
    return pattern_counts

def identify_functional_elements(insertions):
    """
    Identify potential functional elements in insertion sequences
    """
    global sequences_with_element
    element_counts = {element: 0 for element in FUNCTIONAL_PATTERNS}
    sequences_with_element = {element: [] for element in FUNCTIONAL_PATTERNS}
    
    for ins in insertions:
        sequence = ins['sequence']
        for element_name, pattern in FUNCTIONAL_PATTERNS.items():
            if re.search(pattern, sequence):
                element_counts[element_name] += 1
                sequences_with_element[element_name].append({
                    'chromosome': ins['chromosome'],
                    'position': ins['position'],
                    'length': ins['length'],
                    'sequence': sequence
                })
    
    return element_counts

def analyze_sequence_complexity(insertions):
    """
    Analyze sequence complexity based on nucleotide diversity
    """
    complexity_categories = {
        'Low': 0,    # Low complexity (dominated by 1-2 nucleotides)
        'Medium': 0, # Medium complexity
        'High': 0    # High complexity (balanced distribution)
    }
    
    for ins in insertions:
        sequence = ins['sequence']
        counts = {
            'A': sequence.count('A'),
            'C': sequence.count('C'),
            'G': sequence.count('G'),
            'T': sequence.count('T')
        }
        
        total = sum(counts.values())
        if total == 0:
            continue
            
        # Calculate nucleotide frequencies
        freqs = {base: count/total for base, count in counts.items()}
        
        # Calculate Shannon entropy as a measure of complexity
        entropy = -sum(freq * (0 if freq == 0 else math.log2(freq)) for freq in freqs.values())
        
        # Categorize based on entropy
        if entropy < 1.5:
            complexity_categories['Low'] += 1
        elif entropy < 1.9:
            complexity_categories['Medium'] += 1
        else:
            complexity_categories['High'] += 1
    
    return complexity_categories

def analyze_chromosome_distribution(insertions):
    """
    Analyze distribution of insertion patterns across chromosomes
    """
    chrom_patterns = defaultdict(lambda: defaultdict(int))
    
    for ins in insertions:
        chrom = ins['chromosome']
        sequence = ins['sequence']
        
        # Check for each repeat pattern
        for pattern_name, pattern in REPEAT_PATTERNS.items():
            if re.search(pattern, sequence):
                chrom_patterns[chrom][pattern_name] += 1
    
    return chrom_patterns

def generate_report(insertions, repeat_counts, functional_counts, chrom_patterns):
    """
    Generate a comprehensive report of the insertion pattern analysis
    """
    global sequences_with_pattern, sequences_with_element
    
    with open(PATTERN_REPORT, 'w') as f:
        f.write("# Insertion Sequence Pattern Analysis\n\n")
        f.write(f"Analysis Date: {os.popen('date').read().strip()}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Total insertions analyzed: {len(insertions)}\n\n")
        
        f.write("## Repetitive Element Analysis\n\n")
        f.write("| Repeat Type | Count | Percentage |\n")
        f.write("|-------------|-------|------------|\n")
        for pattern, count in repeat_counts.items():
            percentage = (count / len(insertions)) * 100
            f.write(f"| {pattern} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Potential Functional Elements\n\n")
        f.write("| Element Type | Count | Percentage |\n")
        f.write("|--------------|-------|------------|\n")
        for element, count in functional_counts.items():
            percentage = (count / len(insertions)) * 100
            f.write(f"| {element} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Chromosome Distribution of Repetitive Elements\n\n")
        f.write("| Chromosome | Alu | LINE | SINE | Simple Repeats | Microsatellites | Minisatellites |\n")
        f.write("|------------|-----|------|------|----------------|-----------------|---------------|\n")
        
        for chrom in sorted(chrom_patterns.keys()):
            patterns = chrom_patterns[chrom]
            f.write(f"| {chrom} | {patterns['Alu']} | {patterns['LINE']} | {patterns['SINE']} | {patterns['Simple Repeats']} | {patterns['Microsatellites']} | {patterns['Minisatellites']} |\n")
        f.write("\n")
        
        f.write("## Examples of Insertions with Repetitive Elements\n\n")
        
        for pattern in REPEAT_PATTERNS:
            examples = sequences_with_pattern[pattern][:3]  # Show up to 3 examples
            if examples:
                f.write(f"### {pattern} Examples\n\n")
                for i, example in enumerate(examples):
                    f.write(f"**Example {i+1}**: {example['chromosome']}:{example['position']} (Length: {example['length']})\n")
                    f.write(f"```\n{example['sequence']}\n```\n\n")
        
        f.write("## Examples of Insertions with Functional Elements\n\n")
        
        for element in FUNCTIONAL_PATTERNS:
            examples = sequences_with_element[element][:3]  # Show up to 3 examples
            if examples:
                f.write(f"### {element} Examples\n\n")
                for i, example in enumerate(examples):
                    f.write(f"**Example {i+1}**: {example['chromosome']}:{example['position']} (Length: {example['length']})\n")
                    f.write(f"```\n{example['sequence']}\n```\n\n")
        
        f.write("## Potential Functional Impact\n\n")
        f.write("The presence of these patterns suggests several potential functional impacts:\n\n")
        f.write("1. **Alu and LINE elements**: May affect gene expression through insertion into regulatory regions\n")
        f.write("2. **Promoter elements**: Could create new transcription start sites or alter existing ones\n")
        f.write("3. **Splice site motifs**: May introduce alternative splicing or disrupt normal splicing\n")
        f.write("4. **Microsatellites**: Could lead to genomic instability if they continue to expand\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Compare these insertions with known gene coordinates to identify those within coding regions\n")
        f.write("2. Perform more detailed analysis of insertions containing functional elements\n")
        f.write("3. Investigate whether any insertions match known disease-associated variants\n")
        f.write("4. Analyze the evolutionary conservation of regions surrounding these insertions\n")
    
    print(f"Report generated: {PATTERN_REPORT}")

def main():
    print("Starting insertion pattern analysis...")
    
    # Load insertion data
    insertions = load_insertion_data()
    
    if not insertions:
        print("No insertion data found. Exiting.")
        return
    
    # Identify repeat patterns
    print("Identifying repetitive elements...")
    repeat_counts = identify_repeat_patterns(insertions)
    
    # Identify functional elements
    print("Identifying potential functional elements...")
    functional_counts = identify_functional_elements(insertions)
    
    # Analyze chromosome distribution
    print("Analyzing chromosome distribution of patterns...")
    chrom_patterns = analyze_chromosome_distribution(insertions)
    
    # Generate report
    print("Generating comprehensive report...")
    generate_report(insertions, repeat_counts, functional_counts, chrom_patterns)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
