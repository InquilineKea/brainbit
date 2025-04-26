#!/usr/bin/env python3
"""
Improved Repetitive Element Analysis for Genome Structural Variants
This script uses more comprehensive patterns to detect repetitive elements in insertion sequences.
"""

import os
import re
import sys
from collections import Counter, defaultdict

# File paths
INSERTION_FILE = "/Users/simfish/Downloads/Genome/sv_insertions.txt"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/sv_analysis"
REPORT_FILE = os.path.join(OUTPUT_DIR, "improved_repeat_analysis.md")

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

def load_insertion_data(max_sequences=1000):
    """
    Load insertion sequences from the TSV file
    Include truncated sequences and analyze a larger sample
    """
    if not os.path.exists(INSERTION_FILE):
        print(f"Error: {INSERTION_FILE} not found.")
        sys.exit(1)
        
    complete_sequences = []
    truncated_sequences = []
    
    with open(INSERTION_FILE, 'r') as f:
        # Skip header lines
        for line in f:
            if line.startswith('#'):
                continue
            break
        
        # Process data lines
        count = 0
        for line in f:
            if not line.strip() or count >= max_sequences:
                continue
                
            fields = line.strip().split('\t')
            if len(fields) < 4:
                continue
                
            chrom = fields[0]
            pos = fields[1]
            length = fields[2] if len(fields) > 2 else "unknown"
            sequence = fields[3] if len(fields) > 3 else "unknown"
            
            if sequence == "unknown":
                continue
                
            variant = {
                'chromosome': chrom,
                'position': pos,
                'length': length,
                'sequence': sequence,
                'is_truncated': "..." in sequence
            }
            
            if "..." in sequence:
                # Clean up the sequence by removing the ellipsis
                variant['sequence'] = sequence.replace("...", "")
                truncated_sequences.append(variant)
            else:
                complete_sequences.append(variant)
            
            count += 1
    
    print(f"Loaded {len(complete_sequences)} complete sequences and {len(truncated_sequences)} truncated sequences")
    return complete_sequences, truncated_sequences

def identify_repeat_patterns(variants):
    """
    Identify repetitive elements in variant sequences
    """
    pattern_counts = {pattern: 0 for pattern in REPEAT_PATTERNS}
    sequences_with_pattern = {pattern: [] for pattern in REPEAT_PATTERNS}
    
    for variant in variants:
        sequence = variant['sequence']
        for pattern_name, pattern in REPEAT_PATTERNS.items():
            if re.search(pattern, sequence):
                pattern_counts[pattern_name] += 1
                sequences_with_pattern[pattern_name].append(variant)
    
    return pattern_counts, sequences_with_pattern

def analyze_chromosome_distribution(variants_with_patterns):
    """
    Analyze distribution of repetitive elements across chromosomes
    """
    chrom_patterns = defaultdict(lambda: defaultdict(int))
    
    for pattern_name, variants in variants_with_patterns.items():
        for variant in variants:
            chrom = variant['chromosome']
            chrom_patterns[chrom][pattern_name] += 1
    
    return chrom_patterns

def generate_report(complete_sequences, truncated_sequences, complete_pattern_counts, truncated_pattern_counts, 
                   complete_with_patterns, truncated_with_patterns, chrom_distribution):
    """
    Generate a comprehensive report of the repetitive element analysis
    """
    with open(REPORT_FILE, 'w') as f:
        f.write("# Improved Repetitive Element Analysis in Structural Variant Insertions\n\n")
        f.write(f"Analysis Date: {os.popen('date').read().strip()}\n\n")
        
        f.write("## Overview\n\n")
        f.write(f"Total complete sequences analyzed: {len(complete_sequences)}\n")
        f.write(f"Total truncated sequences analyzed: {len(truncated_sequences)}\n")
        f.write(f"Total sequences analyzed: {len(complete_sequences) + len(truncated_sequences)}\n\n")
        
        f.write("## Repetitive Element Analysis - Complete Sequences\n\n")
        f.write("| Repeat Type | Count | Percentage |\n")
        f.write("|-------------|-------|------------|\n")
        for pattern, count in complete_pattern_counts.items():
            percentage = (count / len(complete_sequences)) * 100 if complete_sequences else 0
            f.write(f"| {pattern} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Repetitive Element Analysis - Truncated Sequences\n\n")
        f.write("| Repeat Type | Count | Percentage |\n")
        f.write("|-------------|-------|------------|\n")
        for pattern, count in truncated_pattern_counts.items():
            percentage = (count / len(truncated_sequences)) * 100 if truncated_sequences else 0
            f.write(f"| {pattern} | {count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Combined Repetitive Element Analysis\n\n")
        f.write("| Repeat Type | Complete | Truncated | Total | Overall Percentage |\n")
        f.write("|-------------|----------|-----------|-------|-------------------|\n")
        total_sequences = len(complete_sequences) + len(truncated_sequences)
        for pattern in REPEAT_PATTERNS:
            complete_count = complete_pattern_counts[pattern]
            truncated_count = truncated_pattern_counts[pattern]
            total_count = complete_count + truncated_count
            percentage = (total_count / total_sequences) * 100 if total_sequences else 0
            f.write(f"| {pattern} | {complete_count} | {truncated_count} | {total_count} | {percentage:.2f}% |\n")
        f.write("\n")
        
        f.write("## Chromosome Distribution of Repetitive Elements\n\n")
        f.write("| Chromosome | Alu | LINE | SINE | Simple Repeats | Microsatellites | Minisatellites |\n")
        f.write("|------------|-----|------|------|----------------|-----------------|---------------|\n")
        
        # Sort chromosomes naturally
        def chrom_key(chrom):
            if chrom.startswith('chr'):
                chrom = chrom[3:]
            if chrom.isdigit():
                return int(chrom)
            return float('inf')  # Put non-numeric at the end
        
        for chrom in sorted(chrom_distribution.keys(), key=chrom_key):
            patterns = chrom_distribution[chrom]
            f.write(f"| {chrom} | {patterns['Alu']} | {patterns['LINE']} | {patterns['SINE']} | {patterns['Simple Repeats']} | {patterns['Microsatellites']} | {patterns['Minisatellites']} |\n")
        f.write("\n")
        
        f.write("## Examples of Insertions with Repetitive Elements\n\n")
        
        # Combine complete and truncated sequences for examples
        combined_with_patterns = {}
        for pattern in REPEAT_PATTERNS:
            combined_with_patterns[pattern] = complete_with_patterns[pattern] + truncated_with_patterns[pattern]
        
        for pattern in REPEAT_PATTERNS:
            examples = combined_with_patterns[pattern][:3]  # Show up to 3 examples
            if examples:
                f.write(f"### {pattern} Examples\n\n")
                for i, example in enumerate(examples):
                    f.write(f"**Example {i+1}**: {example['chromosome']}:{example['position']} (Length: {example['length']})\n")
                    
                    # Truncate very long sequences for readability
                    sequence = example['sequence']
                    if len(sequence) > 100:
                        display_seq = sequence[:97] + "..."
                    else:
                        display_seq = sequence
                    
                    f.write(f"```\n{display_seq}\n```\n")
                    f.write(f"*{'Truncated sequence' if example.get('is_truncated') else 'Complete sequence'}*\n\n")
        
        f.write("## Why Previous Analysis Showed Low Representation\n\n")
        f.write("The previous analysis showed low representation of SINE elements, simple repeats, and satellites for several reasons:\n\n")
        f.write("1. **Limited Sample Size**: The previous analysis only examined 10 complete sequences, which is too small to capture the diversity of repetitive elements.\n\n")
        f.write("2. **Exclusion of Truncated Sequences**: Sequences containing '...' were excluded, which likely removed many longer insertions that would contain repetitive elements.\n\n")
        f.write("3. **Narrow Pattern Definitions**: The previous patterns used to identify repetitive elements were too specific and missed many variants.\n\n")
        f.write("4. **Focus on Complete Matches**: The previous approach may have required more complete matches of repetitive element signatures.\n\n")
        
        f.write("## Biological Significance\n\n")
        f.write("Repetitive elements in structural variant insertions have important biological implications:\n\n")
        f.write("1. **Alu and LINE elements**: Mobile elements that can cause insertional mutagenesis and genomic instability\n")
        f.write("2. **SINE elements**: Can affect gene expression when inserted near genes\n")
        f.write("3. **Simple repeats and microsatellites**: Associated with genomic instability and certain genetic disorders\n")
        f.write("4. **Minisatellites**: Can influence recombination rates and chromosome stability\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Compare the distribution of repetitive elements in your genome with population databases\n")
        f.write("2. Analyze the genomic context of insertions containing specific repetitive elements\n")
        f.write("3. Investigate whether any repetitive element insertions are associated with genes or regulatory regions\n")
        f.write("4. Consider more detailed analysis of specific repetitive element families of interest\n")
    
    print(f"Improved repetitive element analysis report generated: {REPORT_FILE}")

def main():
    print("Starting improved repetitive element analysis...")
    
    # Load insertion data
    complete_sequences, truncated_sequences = load_insertion_data()
    
    if not complete_sequences and not truncated_sequences:
        print("No insertion data found. Exiting.")
        return
    
    # Analyze complete sequences
    print("Analyzing complete sequences...")
    complete_pattern_counts, complete_with_patterns = identify_repeat_patterns(complete_sequences)
    
    # Analyze truncated sequences
    print("Analyzing truncated sequences...")
    truncated_pattern_counts, truncated_with_patterns = identify_repeat_patterns(truncated_sequences)
    
    # Combine for chromosome distribution analysis
    all_with_patterns = {}
    for pattern in REPEAT_PATTERNS:
        all_with_patterns[pattern] = complete_with_patterns[pattern] + truncated_with_patterns[pattern]
    
    # Analyze chromosome distribution
    print("Analyzing chromosome distribution...")
    chrom_distribution = analyze_chromosome_distribution(all_with_patterns)
    
    # Generate report
    print("Generating comprehensive report...")
    generate_report(complete_sequences, truncated_sequences, 
                   complete_pattern_counts, truncated_pattern_counts,
                   complete_with_patterns, truncated_with_patterns,
                   chrom_distribution)
    
    print("Analysis complete!")

if __name__ == "__main__":
    main()
