#!/usr/bin/env python3
"""
FOXO3 Variant Analysis Script
- Extracts FOXO3 variants from VCF file
- Annotates with population frequencies
- Identifies variants that may contribute to longevity scores
- Created: 2025-03-02
"""

import os
import sys
import re
import csv
from collections import defaultdict

# Define constants
FOXO3_REGION = (6, 108554790, 108693686)  # chr6:108554790-108693686
VCF_FILE = "/Users/simfish/Downloads/Genome/filtered_variants.ann.gnomad.vcf"
OUTPUT_DIR = "/Users/simfish/Downloads/Genome/foxo3_analysis"

# Known FOXO3 longevity-associated variants
LONGEVITY_VARIANTS = {
    "rs2802292": {"beneficial_allele": "G", "weight": 0.25, "effect": "Increased longevity"},
    "rs2764264": {"beneficial_allele": "C", "weight": 0.20, "effect": "Increased longevity"},
    "rs13217795": {"beneficial_allele": "C", "weight": 0.15, "effect": "Increased longevity"},
    "rs1935949": {"beneficial_allele": "T", "weight": 0.15, "effect": "Increased longevity"},
    "rs4946935": {"beneficial_allele": "A", "weight": 0.20, "effect": "Increased longevity"},
    "rs9400239": {"beneficial_allele": "C", "weight": 0.15, "effect": "Increased longevity"},
    "rs479744": {"beneficial_allele": "T", "weight": 0.10, "effect": "Increased longevity"}
}

# Potentially damaging variants
DAMAGING_VARIANTS = {
    "rs121908700": {"effect": "Missense variant (p.Arg211Gly)", "impact": "Potentially affects DNA binding"},
    "rs121908701": {"effect": "Missense variant (p.Ser253Asn)", "impact": "Potentially affects phosphorylation"},
    "rs121908702": {"effect": "Missense variant (p.His212Arg)", "impact": "Potentially affects DNA binding"}
}

def ensure_output_dir(directory):
    """Create output directory if it doesn't exist"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def parse_info_field(info_str):
    """Parse VCF INFO field into a dictionary"""
    info_dict = {}
    for item in info_str.split(';'):
        if '=' in item:
            key, value = item.split('=', 1)
            info_dict[key] = value
        else:
            info_dict[item] = True
    return info_dict

def get_gnomad_frequencies(info_dict):
    """Extract gnomAD population frequencies from INFO field"""
    frequencies = {}
    
    # Look for gnomAD frequencies
    for key in info_dict:
        if key.startswith('gnomAD_AF') or key.startswith('AF_') or key == 'AF':
            frequencies[key] = info_dict[key]
    
    return frequencies

def get_genotype(format_str, sample_str):
    """Parse genotype information"""
    format_fields = format_str.split(':')
    sample_fields = sample_str.split(':')
    
    gt_dict = {}
    for i, field in enumerate(format_fields):
        if i < len(sample_fields):
            gt_dict[field] = sample_fields[i]
    
    return gt_dict

def calculate_longevity_score(variants):
    """Calculate a simple longevity score based on known variants"""
    max_score = sum(var["weight"] for var in LONGEVITY_VARIANTS.values())
    actual_score = 0
    missing_variants = []
    negative_variants = []
    
    for rsid, info in LONGEVITY_VARIANTS.items():
        if rsid in variants:
            variant = variants[rsid]
            beneficial_allele = info["beneficial_allele"]
            
            # Check if beneficial allele is present
            has_beneficial = False
            if variant["ref"] == beneficial_allele and "0" in variant["genotype"]["GT"]:
                has_beneficial = True
            elif beneficial_allele in variant["alt"].split(',') and str(variant["alt"].split(',').index(beneficial_allele) + 1) in variant["genotype"]["GT"]:
                has_beneficial = True
                
            if has_beneficial:
                actual_score += info["weight"]
            else:
                negative_variants.append((rsid, info["effect"], info["weight"]))
        else:
            missing_variants.append((rsid, info["effect"], info["weight"]))
    
    return {
        "max_score": max_score,
        "actual_score": actual_score,
        "percentage": (actual_score / max_score) * 100 if max_score > 0 else 0,
        "missing_variants": missing_variants,
        "negative_variants": negative_variants
    }

def extract_foxo3_variants():
    """Extract FOXO3 variants from VCF file"""
    print(f"Analyzing FOXO3 variants from {VCF_FILE}...")
    
    foxo3_variants = {}
    total_variants = 0
    
    try:
        with open(VCF_FILE, 'r') as vcf:
            for line in vcf:
                if line.startswith('#'):
                    continue
                    
                total_variants += 1
                if total_variants % 100000 == 0:
                    print(f"Processed {total_variants} variants...")
                
                fields = line.strip().split('\t')
                if len(fields) < 10:  # Need at least 10 fields for a valid VCF entry with genotype
                    continue
                
                # Parse chromosome
                chrom = fields[0]
                if chrom.startswith('chr'):
                    chrom = chrom[3:]  # Remove 'chr' prefix if present
                
                # Check if in FOXO3 region
                try:
                    chrom_num = int(chrom)
                    pos = int(fields[1])
                    
                    if chrom_num == FOXO3_REGION[0] and FOXO3_REGION[1] <= pos <= FOXO3_REGION[2]:
                        variant_id = fields[2]
                        ref = fields[3]
                        alt = fields[4]
                        qual = fields[5]
                        filter_status = fields[6]
                        info_str = fields[7]
                        format_str = fields[8]
                        sample_str = fields[9]
                        
                        # Parse INFO field
                        info_dict = parse_info_field(info_str)
                        
                        # Get population frequencies
                        frequencies = get_gnomad_frequencies(info_dict)
                        
                        # Get genotype information
                        genotype = get_genotype(format_str, sample_str)
                        
                        # Store variant information
                        foxo3_variants[variant_id if variant_id != '.' else f"{chrom}:{pos}_{ref}>{alt}"] = {
                            "chrom": chrom,
                            "pos": pos,
                            "ref": ref,
                            "alt": alt,
                            "qual": qual,
                            "filter": filter_status,
                            "info": info_dict,
                            "frequencies": frequencies,
                            "genotype": genotype,
                            "line": line.strip()
                        }
                except ValueError:
                    continue  # Skip non-numeric chromosomes
    
    except FileNotFoundError:
        print(f"Error: VCF file {VCF_FILE} not found.")
        sys.exit(1)
    
    print(f"Found {len(foxo3_variants)} FOXO3 variants out of {total_variants} total variants processed.")
    return foxo3_variants

def write_variant_report(variants, score_info):
    """Write comprehensive variant report"""
    output_dir = ensure_output_dir(OUTPUT_DIR)
    
    # Write detailed variant report
    with open(os.path.join(output_dir, "foxo3_variants_detailed.tsv"), 'w') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow([
            "Variant ID", "Position", "Reference", "Alternate", "Genotype", 
            "Quality", "Filter", "gnomAD Global AF", "gnomAD European AF", 
            "Longevity Association", "Effect"
        ])
        
        for variant_id, data in sorted(variants.items(), key=lambda x: x[1]["pos"]):
            # Determine if this is a known longevity variant
            longevity_info = ""
            effect = ""
            
            if variant_id in LONGEVITY_VARIANTS:
                beneficial_allele = LONGEVITY_VARIANTS[variant_id]["beneficial_allele"]
                has_beneficial = False
                
                if data["ref"] == beneficial_allele and "0" in data["genotype"]["GT"]:
                    has_beneficial = True
                elif beneficial_allele in data["alt"].split(',') and str(data["alt"].split(',').index(beneficial_allele) + 1) in data["genotype"]["GT"]:
                    has_beneficial = True
                
                longevity_info = "Beneficial" if has_beneficial else "Non-beneficial"
                effect = LONGEVITY_VARIANTS[variant_id]["effect"]
            elif variant_id in DAMAGING_VARIANTS:
                longevity_info = "Potentially Damaging"
                effect = DAMAGING_VARIANTS[variant_id]["effect"] + " - " + DAMAGING_VARIANTS[variant_id]["impact"]
            
            # Get population frequencies
            global_af = data["frequencies"].get("AF", "N/A")
            european_af = data["frequencies"].get("AF_eur", data["frequencies"].get("gnomAD_AF_nfe", "N/A"))
            
            writer.writerow([
                variant_id,
                f"{data['chrom']}:{data['pos']}",
                data["ref"],
                data["alt"],
                data["genotype"].get("GT", "N/A"),
                data["qual"],
                data["filter"],
                global_af,
                european_af,
                longevity_info,
                effect
            ])
    
    # Write summary report
    with open(os.path.join(output_dir, "foxo3_longevity_summary.md"), 'w') as f:
        f.write("# FOXO3 Longevity Analysis Summary\n\n")
        f.write(f"Generated: {os.popen('date').read().strip()}\n\n")
        
        f.write("## Background\n")
        f.write("FOXO3 (Forkhead Box O3) is a transcription factor that plays important roles in regulating longevity, stress resistance, and metabolism. Variants in FOXO3 have been associated with increased human longevity in multiple populations.\n\n")
        
        f.write("## Longevity Score\n")
        f.write(f"Your FOXO3 longevity score: {score_info['actual_score']:.2f} out of {score_info['max_score']:.2f} ({score_info['percentage']:.1f}%)\n\n")
        
        f.write("### Missing Beneficial Variants\n")
        if score_info["missing_variants"]:
            for rsid, effect, weight in score_info["missing_variants"]:
                f.write(f"* {rsid}: Not found in your genome data (weight: {weight:.2f})\n")
                f.write(f"  - {effect}\n")
        else:
            f.write("* None - all known longevity variants were found in your data\n")
        f.write("\n")
        
        f.write("### Non-Beneficial Alleles\n")
        if score_info["negative_variants"]:
            for rsid, effect, weight in score_info["negative_variants"]:
                variant = variants.get(rsid, {})
                genotype = variant.get("genotype", {}).get("GT", "N/A")
                ref = variant.get("ref", "N/A")
                alt = variant.get("alt", "N/A")
                
                f.write(f"* {rsid}: You have the non-beneficial allele (weight: {weight:.2f})\n")
                f.write(f"  - Genotype: {genotype} (Ref: {ref}, Alt: {alt})\n")
                f.write(f"  - Beneficial allele: {LONGEVITY_VARIANTS[rsid]['beneficial_allele']}\n")
                f.write(f"  - {effect}\n")
        else:
            f.write("* None - you have all the beneficial alleles for known longevity variants\n")
        f.write("\n")
        
        f.write("## Potentially Damaging Variants\n")
        damaging_found = False
        for rsid, info in DAMAGING_VARIANTS.items():
            if rsid in variants:
                damaging_found = True
                variant = variants[rsid]
                genotype = variant["genotype"].get("GT", "N/A")
                
                f.write(f"* {rsid}: Found - Genotype: {genotype}\n")
                f.write(f"  - {info['effect']}\n")
                f.write(f"  - {info['impact']}\n")
        
        if not damaging_found:
            f.write("* No known damaging FOXO3 variants were found in your genome (good)\n")
        f.write("\n")
        
        f.write("## Interpretation\n")
        if score_info["percentage"] >= 75:
            f.write("Your FOXO3 genetic profile is favorable for longevity. You carry most of the beneficial alleles associated with increased lifespan.\n\n")
        elif score_info["percentage"] >= 50:
            f.write("Your FOXO3 genetic profile is moderately favorable for longevity. While you have some beneficial variants, you're missing others.\n\n")
        elif score_info["percentage"] >= 25:
            f.write("Your FOXO3 genetic profile shows limited benefit for longevity. You're missing several beneficial variants or have non-beneficial alleles at important positions.\n\n")
        else:
            f.write("Your FOXO3 genetic profile is less favorable for longevity based on currently known variants. You're missing most of the beneficial alleles associated with increased lifespan.\n\n")
        
        f.write("## Recommendations\n")
        f.write("While genetics play a role in longevity, lifestyle factors are equally if not more important. Consider:\n\n")
        f.write("1. Regular physical activity\n")
        f.write("2. Balanced nutrition with adequate protein and plant-based foods\n")
        f.write("3. Stress management techniques\n")
        f.write("4. Adequate sleep\n")
        f.write("5. Social connections\n\n")
        
        f.write("## Limitations\n")
        f.write("This analysis is based on currently known variants and may not be comprehensive. Many variants have unknown effects, and the impact of specific combinations of variants is not well understood. This information is for research purposes only and should not be used for medical decisions.\n")
    
    print(f"Analysis complete. Results saved to {output_dir}/")
    print(f"- Detailed variant report: {output_dir}/foxo3_variants_detailed.tsv")
    print(f"- Longevity summary: {output_dir}/foxo3_longevity_summary.md")

def main():
    """Main function"""
    # Extract FOXO3 variants
    foxo3_variants = extract_foxo3_variants()
    
    # Calculate longevity score
    longevity_score = calculate_longevity_score(foxo3_variants)
    
    # Write reports
    write_variant_report(foxo3_variants, longevity_score)

if __name__ == "__main__":
    main()
