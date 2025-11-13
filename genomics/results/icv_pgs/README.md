# Intracranial Volume Polygenic Score Analysis

This directory contains tools to calculate a polygenic score (PGS) for intracranial volume based on your personal genome data.

## Background

Intracranial volume (ICV) is a neuroanatomical trait that represents the volume within the cranium, including the brain, meninges, and cerebrospinal fluid. ICV is highly heritable and has been associated with various neurological and cognitive outcomes.

Several genome-wide association studies (GWAS) have identified genetic variants associated with ICV. This analysis uses these variants to calculate a personalized polygenic score that estimates your genetic predisposition for intracranial volume.

## Files

- `icv_significant_snps.txt`: List of genome-wide significant SNPs associated with intracranial volume, including their effect sizes (beta values)
- `calculate_icv_pgs.py`: Python script to calculate your polygenic score based on your genome data
- `icv_pgs_report.txt`: Generated report containing your polygenic score and interpretation (created after running the script)

## Requirements

- Python 3.6+
- pandas
- numpy
- bcftools (for VCF processing)

## Usage

```bash
python calculate_icv_pgs.py
```

The script will:
1. Locate your VCF file in the Genome directory
2. Extract genotypes for the ICV-associated SNPs
3. Calculate your polygenic score
4. Generate a report with your score and interpretation

## Interpretation

The polygenic score represents your genetic predisposition for intracranial volume. Positive scores suggest a genetic tendency toward larger intracranial volume, while negative scores suggest a genetic tendency toward smaller intracranial volume.

## Limitations

- This analysis is based only on genome-wide significant variants and does not include all variants that may influence intracranial volume
- The score is for research and educational purposes only and should not be used for clinical decision-making
- Intracranial volume is influenced by both genetic and environmental factors

## References

1. Adams HHH, et al. Novel genetic loci underlying human intracranial volume identified through genome-wide association. Nat Neurosci. 2016;19(12):1569-1582.
2. Hibar DP, et al. Common genetic variants influence human subcortical brain structures. Nature. 2015;520(7546):224-229.
3. Ikram MA, et al. Common variants at 6q22 and 17q21 are associated with intracranial volume. Nat Genet. 2012;44(5):539-544.
